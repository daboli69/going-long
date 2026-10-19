"""Offline, immutable player-line archive from the authorized GOING JSON/history."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict

import pandas as pd

from ..archive10 import ARCHIVE, save, temporal, utc
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


def player_map(players=None):
    """Only exact normalized full-name aliases in existing map; ambiguous names stay unmatched."""
    players = pd.read_parquet(RAW_DIR / "players.parquet") if players is None else players
    mapping = defaultdict(set)
    for r in players.dropna(subset=["gsis_id"]).to_dict("records"):
        for key in ("display_name", "football_name"):
            if isinstance(r.get(key), str):
                mapping[normalized_name(r[key])].add(r["gsis_id"])
        if isinstance(r.get("first_name"), str) and isinstance(r.get("last_name"), str):
            mapping[normalized_name(r["first_name"] + " " + r["last_name"])].add(r["gsis_id"])
    return {k: next(iter(v)) for k, v in mapping.items() if len(v) == 1}


def line_rows(data, mapping):
    rows, unknown = [], set()
    props = data.get("props") or []
    if not isinstance(props, list):
        return [], ["unsupported props container: " + type(props).__name__]
    for q in props:
        stat = MARKETS.get(q.get("market"))
        if stat is None:
            unknown.add(str(q.get("market")))
            continue
        name = q.get("player") or q.get("description")
        pid = mapping.get(normalized_name(name))
        rows.append({"event_id": q.get("eventId"), "player": name, "gsis_id": pid,
                     "home": NAME_TO_ABBR.get(q.get("homeName"), q.get("homeName")),
                     "away": NAME_TO_ABBR.get(q.get("awayName"), q.get("awayName")),
                     "team": q.get("team"), "stat": stat, "market_raw": q.get("market"),
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
            time = temporal(r.get("quote_time"), d.get("available_at"), r.get("kickoff"))
            if asof is not None and (not time["available_at"] or pd.Timestamp(time["available_at"]) > pd.Timestamp(asof)):
                continue
            rows.append(r | time | {"pregame_verified": time["pregame_verified"] and not r["in_play"],
                                    "archive": path.name, "generated_at": d.get("generated_at")})
    return pd.DataFrame(rows)
