#!/usr/bin/env python3
"""
build_pipeline.py — consolidated nightly ETL, one data.json out.

Every source here is free and keyless. None require signup or an API key.
KeepTradeCut is the one exception to "official API" — it has no public API
at all, so this scrapes an embedded JSON blob off its rankings pages. That
makes it the most fragile piece by a wide margin: a front-end redesign on
KTC's end can silently break extraction with zero warning from their side.
Everything here is written so that a KTC failure degrades the output
(dynasty values missing) rather than crashing the whole pipeline.

    SOURCE           AUTH    STABILITY   WHAT IT GIVES US
    Sleeper          none    high        player metadata, team, years_exp
    nflverse         none    high        weekly production, 3 seasons
    DynastyProcess   none    high        cross-site ID crosswalk, draft capital
    FantasyCalc      none    high        redraft + dynasty market value
    KeepTradeCut     none    LOW         dynasty SF + 1QB consensus values
                                          (scraped, no API — see caveat above)

Usage:
    pip install -r requirements.txt
    python build_pipeline.py

Env vars (all optional, defaults match a 12-team 1QB PPR redraft league):
    SEASON, TEAMS, SCORING (ppr|half|standard), NUM_QBS (1|2),
    HISTORY_SEASONS (default 3), SKIP_KTC (set to skip the fragile step)
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("This script needs `requests` — pip install -r requirements.txt", file=sys.stderr)
    raise

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
SEASON = int(os.environ.get("SEASON", "2026"))
TEAMS = int(os.environ.get("TEAMS", "12"))
SCORING = os.environ.get("SCORING", "ppr")            # ppr | half | standard
NUM_QBS = int(os.environ.get("NUM_QBS", "1"))          # 2 = superflex
HISTORY_SEASONS = int(os.environ.get("HISTORY_SEASONS", "3"))
SKIP_KTC = os.environ.get("SKIP_KTC", "").lower() in ("1", "true", "yes")
LAST_WEEK = 17                                          # guide drops the final week

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "data.json"

KEEP_POS = {"QB", "RB", "WR", "TE"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
TEAM_FIXES = {"JAC": "JAX", "WSH": "WAS", "LAR": "LA", "OAK": "LV", "SD": "LAC", "STL": "LA"}
PPR_MAP = {"ppr": 1, "half": 0.5, "standard": 0}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "going-long-pipeline/1.0 (personal fantasy tool, non-commercial)"})


def get_json(url: str, tries: int = 3, pause: float = 2.0, timeout: int = 60) -> Any:
    last_exc = None
    for attempt in range(tries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001 — genuinely want to catch and retry anything here
            last_exc = exc
            if attempt < tries - 1:
                time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last_exc}")


def get_text(url: str, tries: int = 3, pause: float = 2.0, timeout: int = 60) -> str:
    last_exc = None
    for attempt in range(tries):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return r.text
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < tries - 1:
                time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last_exc}")


def normalize(name: str | None) -> str:
    """'A.J. Brown Jr.' -> 'ajbrown'. Same rule the front end uses — keep in sync."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower().replace("'", "").replace("\u2019", "").replace(".", "").replace("-", " ")
    parts = [p for p in re.split(r"\s+", name) if p and p not in SUFFIXES]
    return re.sub(r"[^a-z0-9]", "", "".join(parts))


def fix_team(team: str | None) -> str | None:
    if not team:
        return None
    team = team.upper()
    return TEAM_FIXES.get(team, team)


# --------------------------------------------------------------------------
# 1. Sleeper — player metadata
# --------------------------------------------------------------------------
def fetch_sleeper_players() -> dict[str, dict]:
    raw = get_json("https://api.sleeper.app/v1/players/nfl", timeout=90)
    players = {}
    for pid, p in raw.items():
        pos = p.get("position") or (p.get("fantasy_positions") or [None])[0]
        if pos not in KEEP_POS:
            continue
        if not p.get("active"):
            continue
        name = p.get("full_name") or f"{p.get('first_name','')} {p.get('last_name','')}".strip()
        if not name:
            continue
        players[pid] = {
            "sleeper_id": pid,
            "name": name,
            "pos": pos,
            "team": fix_team(p.get("team")),
            "age": p.get("age"),
            "years_exp": p.get("years_exp"),   # 0 = rookie season, straight from Sleeper
            "injury_status": p.get("injury_status"),
            "key": normalize(name),
        }
    print(f"[sleeper] {len(players)} active fantasy-relevant players")
    return players


# --------------------------------------------------------------------------
# 2. DynastyProcess — the crosswalk everything else joins through
# --------------------------------------------------------------------------
def fetch_crosswalk() -> tuple[dict[str, str], dict[str, dict]]:
    """Returns (gsis_id -> sleeper_id, sleeper_id -> draft capital dict)."""
    text = get_text("https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    gsis_to_sleeper: dict[str, str] = {}
    draft_capital: dict[str, dict] = {}
    for r in rows:
        gsis, sleeper = (r.get("gsis_id") or "").strip(), (r.get("sleeper_id") or "").strip()
        if gsis and sleeper:
            gsis_to_sleeper[gsis] = sleeper
        if sleeper:
            try:
                dy = int(float(r.get("draft_year") or 0))
                if 1980 < dy < 2100:
                    def _int(col):
                        try:
                            v = int(float(r.get(col) or 0))
                            return v if v > 0 else None
                        except ValueError:
                            return None
                    draft_capital[sleeper] = {
                        "year": dy, "round": _int("draft_round"),
                        "pick": _int("draft_pick"), "ovr": _int("draft_ovr"),
                        "pos": (r.get("position") or "").upper(),
                    }
            except ValueError:
                pass
    print(f"[crosswalk] {len(gsis_to_sleeper)} gsis pairs, {len(draft_capital)} with draft capital")
    return gsis_to_sleeper, draft_capital


# --------------------------------------------------------------------------
# 3. nflverse — weekly production, aggregated to per-game rates
# --------------------------------------------------------------------------
def fantasy_points(row: dict, rec_pts: float) -> float:
    def n(key):
        v = row.get(key)
        if v in (None, "", "NA", "NaN"):
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0
    fumbles_lost = n("sack_fumbles_lost") + n("rushing_fumbles_lost") + n("receiving_fumbles_lost")
    passing = 0.04 * n("passing_yards") + 4 * n("passing_tds") - 2 * n("passing_interceptions")
    rushing = 0.1 * n("rushing_yards") + 6 * n("rushing_tds")
    receiving = 0.1 * n("receiving_yards") + 6 * n("receiving_tds") + rec_pts * n("receptions")
    return passing + rushing + receiving - 2 * fumbles_lost


def fetch_season_stats(season: int, gsis_to_sleeper: dict[str, str]) -> dict[str, dict]:
    url = f"https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"
    try:
        text = get_text(url, timeout=120)
    except RuntimeError as exc:
        print(f"  ! {season} weekly stats unavailable: {exc}")
        return {}
    rows = list(csv.DictReader(io.StringIO(text)))

    def n(row, key):
        v = row.get(key)
        if v in (None, "", "NA", "NaN"):
            return 0.0
        try:
            return float(v)
        except ValueError:
            return 0.0

    agg: dict[str, dict] = {}
    for r in rows:
        if (r.get("season_type") or "").upper() != "REG":
            continue
        try:
            week = int(float(r.get("week") or 0))
        except ValueError:
            continue
        if not (1 <= week <= LAST_WEEK):
            continue
        pos = (r.get("position") or "").upper()
        if pos not in KEEP_POS:
            continue
        sid = gsis_to_sleeper.get((r.get("player_id") or "").strip())
        if not sid:
            continue
        a = agg.setdefault(sid, {"pos": pos, "g": 0, "ppr": 0.0, "rush_fp": 0.0,
                                  "tgt": 0.0, "car": 0.0, "tgt_share": 0.0, "share_n": 0})
        a["g"] += 1
        a["ppr"] += fantasy_points(r, 1.0)
        a["rush_fp"] += 0.1 * n(r, "rushing_yards") + 6 * n(r, "rushing_tds")
        a["tgt"] += n(r, "targets")
        a["car"] += n(r, "carries")
        ts = n(r, "target_share")
        if ts:
            a["tgt_share"] += ts
            a["share_n"] += 1

    out = {}
    for sid, a in agg.items():
        g = a["g"]
        if g < 1:
            continue
        out[sid] = {
            "pos": a["pos"], "g": g,
            "ppg": round(a["ppr"] / g, 2),
            "rush_fp_pg": round(a["rush_fp"] / g, 2),
            "tgt_pg": round(a["tgt"] / g, 2), "car_pg": round(a["car"] / g, 2),
            "tgt_share": round(a["tgt_share"] / a["share_n"], 3) if a["share_n"] else None,
        }
    print(f"[nflverse] {season}: {len(out)} players from {len(rows)} rows")
    return out


# --------------------------------------------------------------------------
# 4. FantasyCalc — redraft + dynasty market value
# --------------------------------------------------------------------------
def fetch_fantasycalc(is_dynasty: bool) -> dict[str, dict]:
    url = (
        "https://api.fantasycalc.com/values/current"
        f"?isDynasty={'true' if is_dynasty else 'false'}&numQbs={NUM_QBS}&numTeams={TEAMS}"
        f"&ppr={PPR_MAP.get(SCORING, 1)}"
    )
    try:
        rows = get_json(url)
    except RuntimeError as exc:
        print(f"  ! FantasyCalc ({'dynasty' if is_dynasty else 'redraft'}) unavailable: {exc}")
        return {}
    out = {}
    for r in rows:
        p = r.get("player") or {}
        sid = p.get("sleeperId")
        if not sid:
            continue
        out[str(sid)] = {
            "value": r.get("redraftValue") or r.get("value"),
            "overall_rank": r.get("overallRank"),
            "trend_30d": r.get("trend30Day"),
        }
    kind = "dynasty" if is_dynasty else "redraft"
    print(f"[fantasycalc:{kind}] {len(out)} players matched by sleeperId")
    return out


# --------------------------------------------------------------------------
# 5. KeepTradeCut — scraped, no API, the fragile one
# --------------------------------------------------------------------------
def _extract_ktc_json_blob(html: str) -> list[dict] | None:
    """
    KTC has no API. Historically its rankings pages ship the full player
    array embedded in the page — either inside a Next.js `__NEXT_DATA__`
    script tag, or as a bare `var playersArray = [...]` assignment. Both
    patterns are tried, in order, and this returns None (not an exception)
    if neither matches, so the caller can degrade gracefully instead of
    dying. This is the one piece of the pipeline that can silently start
    returning None after a KTC front-end redesign with zero notice on
    their end — if it stops working, that's the first place to look.
    """
    # Strategy 1: Next.js __NEXT_DATA__ (App Router / modern Next sites)
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S
    )
    if m:
        try:
            blob = json.loads(m.group(1))
            # the players array lives somewhere under props — walk it rather
            # than hardcode a brittle exact path, since Next's prop shape
            # shifts between KTC deploys.
            found = _find_player_array(blob)
            if found:
                return found
        except (json.JSONDecodeError, KeyError):
            pass

    # Strategy 2: a bare JS variable assignment some KTC pages use instead
    m = re.search(r"var\s+playersArray\s*=\s*(\[.*?\]);", html, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _find_player_array(obj: Any, depth: int = 0) -> list[dict] | None:
    """Walk an arbitrary nested dict/list looking for what's plausibly the
    KTC player list: a list of dicts each carrying both a name-like and a
    value-like key. Depth-capped so a malformed blob can't recurse forever."""
    if depth > 12:
        return None
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = {k.lower() for k in obj[0].keys()}
        name_like = keys & {"playername", "name", "fullname"}
        value_like = keys & {"value", "sfvalue", "onepvalue", "sfvalue1qb"}
        if name_like and value_like:
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_player_array(v, depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_player_array(v, depth + 1)
            if found:
                return found
    return None


def fetch_ktc(page_url: str, label: str) -> dict[str, dict]:
    try:
        html = get_text(page_url, timeout=45)
    except RuntimeError as exc:
        print(f"  ! KTC {label} fetch failed: {exc}")
        return {}
    blob = _extract_ktc_json_blob(html)
    if not blob:
        print(f"  ! KTC {label}: page fetched but no recognizable player data found in it. "
              f"KTC's markup has likely changed — this needs a human to open the page, "
              f"view source, and update _extract_ktc_json_blob's patterns.")
        return {}
    out = {}
    for p in blob:
        name = p.get("playerName") or p.get("name") or p.get("fullName")
        val = p.get("value") or p.get("sfValue") or p.get("oneQBValue")
        if not name or val is None:
            continue
        out[normalize(name)] = {
            "ktc_value": val,
            "ktc_rank": p.get("rank") or p.get("superflexRank") or p.get("oneQBRank"),
            "ktc_pos": (p.get("position") or "").upper() or None,
            "ktc_team": fix_team(p.get("team")),
        }
    print(f"[ktc:{label}] {len(out)} players extracted")
    return out


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------
def build():
    players = fetch_sleeper_players()
    gsis_to_sleeper, draft_capital = fetch_crosswalk()

    seasons = [SEASON - i for i in range(1, HISTORY_SEASONS + 1)]
    season_stats = {s: fetch_season_stats(s, gsis_to_sleeper) for s in seasons}

    fc_redraft = fetch_fantasycalc(is_dynasty=False)
    fc_dynasty = fetch_fantasycalc(is_dynasty=True)

    ktc_sf, ktc_1qb = {}, {}
    if not SKIP_KTC:
        # These URLs are current to my best knowledge, not verified live —
        # I could not reach keeptradecut.com from the environment this
        # script was written in. Check them by hand before relying on them.
        ktc_sf = fetch_ktc("https://keeptradecut.com/dynasty-rankings?filters=SF", "superflex")
        ktc_1qb = fetch_ktc("https://keeptradecut.com/dynasty-rankings", "1qb")
    else:
        print("[ktc] skipped (SKIP_KTC set)")

    out_players = {}
    matched = {"history": 0, "fc_redraft": 0, "fc_dynasty": 0, "ktc_sf": 0, "ktc_1qb": 0}

    for sid, p in players.items():
        rec = dict(p)

        # n1: most recent qualifying season (8+ games), guide's own bar
        n1 = None
        for s in seasons:
            h = season_stats.get(s, {}).get(sid)
            if h and h["g"] >= 8:
                n1 = {"season": s, **h}
                matched["history"] += 1
                break
        rec["n1"] = n1

        cap = draft_capital.get(sid)
        if cap:
            rec["draft_year"] = cap["year"]
            rec["draft_round"] = cap["round"]
            rec["draft_pick"] = cap["pick"]
            rec["draft_ovr"] = cap["ovr"]
            rec["career_year"] = (SEASON - cap["year"] + 1) if cap["year"] else None
        else:
            rec["draft_year"] = rec["draft_round"] = rec["draft_pick"] = None
            rec["draft_ovr"] = rec["career_year"] = None

        if sid in fc_redraft:
            rec["fc_redraft"] = fc_redraft[sid]; matched["fc_redraft"] += 1
        if sid in fc_dynasty:
            rec["fc_dynasty"] = fc_dynasty[sid]; matched["fc_dynasty"] += 1

        key = p["key"]
        if key in ktc_sf:
            rec["ktc_sf"] = ktc_sf[key]; matched["ktc_sf"] += 1
        if key in ktc_1qb:
            rec["ktc_1qb"] = ktc_1qb[key]; matched["ktc_1qb"] += 1

        # Only ship players the market has actually heard of — keeps the
        # file from bloating with practice-squad names nobody will look up.
        if n1 or sid in fc_redraft or key in ktc_sf or key in ktc_1qb or cap:
            out_players[sid] = rec

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON, "teams": TEAMS, "scoring": SCORING, "num_qbs": NUM_QBS,
        "seasons_covered": seasons,
        "sources": {
            "sleeper": True, "nflverse": True, "dynastyprocess": True,
            "fantasycalc": bool(fc_redraft or fc_dynasty),
            "ktc": bool(ktc_sf or ktc_1qb),
        },
        "counts": {"players": len(out_players), **matched},
        "players": out_players,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"\nwrote {OUT} — {len(out_players)} players, {kb:.0f}KB")
    print(f"  matched: {matched}")
    if not (fc_redraft or fc_dynasty):
        print("  WARNING: FantasyCalc returned nothing — market value will be absent this run.")
    if not (ktc_sf or ktc_1qb) and not SKIP_KTC:
        print("  WARNING: KTC returned nothing — see the extraction warning above. "
              "Pipeline continuing without dynasty values rather than failing the build.")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001 — top-level: fail the Action clearly, don't hang
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
