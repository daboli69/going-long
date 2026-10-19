"""Offline, immutable player-line archive from the authorized GOING JSON/history."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache

import pandas as pd

from ..archive10 import ARCHIVE, save, temporal, utc, freshness
from ..config import RAW_DIR
from ..market81 import NAME_TO_ABBR

MARKETS = {
    "pass_yds": "pass_yds", "player_pass_yds": "pass_yds", "passing_yards": "pass_yds",
    "pass_tds": "pass_tds", "player_pass_tds": "pass_tds", "passing_tds": "pass_tds",
    "rec": "rec", "receptions": "rec", "player_receptions": "rec",
    "rec_yds": "rec_yds", "receiving_yards": "rec_yds", "player_reception_yds": "rec_yds",
    "rush_yds": "rush_yds", "rushing_yards": "rush_yds", "player_rush_yds": "rush_yds",
    "atd": "anytime_td", "anytime_td": "anytime_td", "player_anytime_td": "anytime_td",
    "first_td": "first_td", "first_td_scorer": "first_td", "player_1st_td": "first_td",
}


def normalized_name(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


@lru_cache(maxsize=20000)
def player_label(label):
    """Remove only explicit, recognized source team/period decorations; no fuzzy names."""
    raw = str(label or "").strip()
    name, period, team = raw, "FULL", None
    match = re.search(r"\s*-\s*(1H|1Q)$", name, flags=re.I)
    if match:
        period, name = match[1].upper(), name[:match.start()].strip()
    match = re.search(r"\s*\(([A-Z]{2,3})\)$", name)
    if match:
        code = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX"}.get(match[1], match[1])
        if code in set(NAME_TO_ABBR.values()):
            team, name = code, name[:match.start()].strip()
    return name, period, team


def player_map(players=None, eligible_ids=None):
    """Only exact normalized full-name aliases in existing map; ambiguous names stay unmatched."""
    players = pd.read_parquet(RAW_DIR / "players.parquet") if players is None else players
    if eligible_ids is not None:
        players = players[players["gsis_id"].isin(eligible_ids)]
    mapping = defaultdict(set)
    for r in players.dropna(subset=["gsis_id"]).to_dict("records"):
        if isinstance(r.get("display_name"), str) and len(r["display_name"].split()) >= 2:
            mapping[normalized_name(r["display_name"])].add(r["gsis_id"])
        if isinstance(r.get("last_name"), str):
            # nflverse football_name is a FIRST-name alias, not a full name.
            # Never map a one-token quote to a player just because it is unique.
            for key in ("first_name", "common_first_name", "football_name"):
                if isinstance(r.get(key), str):
                    mapping[normalized_name(r[key] + " " + r["last_name"])].add(r["gsis_id"])
    return {k: next(iter(v)) for k, v in mapping.items() if len(v) == 1}


def line_rows(data, mapping):
    rows, unknown = [], set()
    props = data.get("props") or []
    if not isinstance(props, list):
        return [], ["unsupported props container: " + type(props).__name__]
    for q in props:
        market_key = str(q.get("market") or "")
        suffix = re.search(r"_(1h|1q)$", market_key, flags=re.I)
        market_period = suffix[1].upper() if suffix else "FULL"
        base_market = market_key[:suffix.start()] if suffix else market_key
        stat = MARKETS.get(base_market)
        if stat is None:
            unknown.add(str(q.get("market")))
            continue
        raw_name = q.get("player") or q.get("description")
        name, label_period, team = player_label(raw_name)
        period = market_period if market_period != "FULL" else label_period
        if market_period != "FULL" and label_period != "FULL" and market_period != label_period:
            period = "conflict"
        pid = mapping.get(normalized_name(name))
        rows.append({"event_id": q.get("eventId"), "player": name, "player_raw": raw_name, "gsis_id": pid, "period": period,
                     "home": NAME_TO_ABBR.get(q.get("homeName"), q.get("homeName")),
                     "away": NAME_TO_ABBR.get(q.get("awayName"), q.get("awayName")),
                     "team": q.get("team") or team, "stat": stat, "market_raw": q.get("market"),
                     "line": q.get("line"), "over_odds": q.get("overOdds"), "under_odds": q.get("underOdds"),
                     "book": q.get("bookKey") or q.get("book"), "source": q.get("source"),
                     "quote_time": utc(q.get("updatedAt")), "kickoff": utc(q.get("kickoff")),
                     "dfs": bool(q.get("dfs", False)), "in_play": bool(q.get("inPlay", False))})
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True)), sorted(unknown)


def archive_lines(data, metadata, mapping=None, *, root=ARCHIVE):
    rows, unknown = line_rows(data, player_map() if mapping is None else mapping)
    report = {"rows": len(rows), "markets": sorted({r["stat"] for r in rows}),
              "unmatched": sorted({r["player"] for r in rows if r["gsis_id"] is None and r["player"]}),
              "unknown_markets": unknown}
    if not rows:
        return {"new": False} | report
    return save("props", "going", rows, metadata | report | {"generated_at": data.get("generated_at"),
                "timestamp_policy": "T1 only when quote and observation predate kickoff; no inferred T2/T3"}, root=root) | report


def archived_lines(*, root=ARCHIVE, asof=None):
    """Include unverified rows for audit; only pregame_verified may benchmark forecasts."""
    rows = []
    for path in sorted((root / "props").glob("going_*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        for r in d["content"]:
            rows.append(r | {"available_at": d.get("available_at"), "archive": path.name,
                             "generated_at": d.get("generated_at")})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    # Improve interpretation of older immutable records without modifying them.
    # Decorations are parsed exactly; ambiguous/unknown identities remain null.
    labels = frame["player"].fillna("").map(player_label)
    if "period" not in frame:
        frame["period"] = labels.map(lambda x: x[1])
    else:
        frame["period"] = frame["period"].fillna(labels.map(lambda x: x[1]))
    if (RAW_DIR / "players.parquet").exists():
        mapping = player_map()
        recovered = labels.map(lambda x: mapping.get(normalized_name(x[0])))
        frame["gsis_id"] = recovered
        frame["identity_mapping_source"] = "existing full-name player-map alias"
    frame["player_raw"] = frame["player_raw"].fillna(frame["player"]) if "player_raw" in frame else frame["player"]
    frame["player"] = labels.map(lambda x: x[0])
    q = pd.to_datetime(frame["quote_time"], utc=True, errors="coerce", format="mixed")
    av = pd.to_datetime(frame["available_at"], utc=True, errors="coerce", format="mixed")
    ko = pd.to_datetime(frame["kickoff"], utc=True, errors="coerce", format="mixed")
    frame["pregame_verified"] = q.notna() & av.notna() & ko.notna() & (q <= av) & (av < ko) & ~frame["in_play"]
    frame["timestamp_class"] = frame["pregame_verified"].map({True: "T1", False: "unverified"})
    decision = pd.Timestamp.now(tz="UTC") if asof is None else pd.Timestamp(asof)
    roster_path = RAW_DIR / "roster_weekly_2026.parquet"
    if asof is not None and roster_path.exists() and (RAW_DIR / "players.parquet").exists():
        observed = pd.Timestamp(roster_path.stat().st_mtime, unit="s", tz="UTC")
        if observed <= decision:
            roster = pd.read_parquet(roster_path, columns=["gsis_id", "status", "team"])
            # A unique exact alias within the as-of 2026 roster resolves retired
            # namesakes. No fuzzy spelling, initials or position guesses.
            ids = set(roster.loc[roster["status"] == "ACT", "gsis_id"].dropna())
            live_map = player_map(eligible_ids=ids)
            mapped = labels.map(lambda x: live_map.get(normalized_name(x[0])))
            valid = frame["gsis_id"].isna() & (ko > decision) & ko.dt.year.eq(2026) & mapped.notna()
            frame.loc[valid, "gsis_id"] = mapped[valid]
            frame.loc[valid, "identity_mapping_source"] = "unique exact full-name alias among locally observed 2026 ACT roster IDs"
            frame.loc[valid, "identity_roster_observed_at"] = observed.isoformat()
    frame["line_age_hours"] = (decision - q).dt.total_seconds() / 3600
    frame["line_status"] = "current"
    frame.loc[frame["line_age_hours"] > 24, "line_status"] = "stale"
    frame.loc[frame["line_age_hours"] < 0, "line_status"] = "future timestamp"
    frame.loc[q.isna(), "line_status"] = "unknown timestamp"
    if asof is not None:
        frame = frame[av.notna() & (av <= decision)]
    return frame
