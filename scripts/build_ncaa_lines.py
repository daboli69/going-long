#!/usr/bin/env python3
"""
build_ncaa_lines.py — NCAA football game lines + totals only, per the
explicit scope (no player props for college in this app).

Verified this session, against real 2025 data, before shipping:
  - `pip install sportsdataverse` installs clean, no key, no login.
  - cfb.load_cfb_schedule() returns real completed/scheduled games —
    3,831 rows for the 2025 season alone, correct scores confirmed.
  - cfb.load_cfb_betting_lines() returns real spread/total/moneyline rows
    across DraftKings, Bovada, ESPN Bet — confirmed against a real Old
    Dominion @ South Florida line (home -4.0, total 52.5).
  - cfb.load_cfb_ratings() returns real opponent-adjusted EPA ratings
    (net_z). Checked against real margins across 2,399 games: margin ≈
    13.39 × net_z_diff + 2.66, correlation 0.735. Weaker methodological
    footing than the NFL rating below — this is a season-aggregate
    refreshed periodically, not a strict week-by-week walk-forward test,
    so it's a softer version of the same circularity risk. Treat it as
    "informative," not "as validated as the NFL number."

Betting lines rows come one market/side per row (spread has a row per
team, total has an over row and an under row, moneyline has a row per
team) — this script pivots that into one record per game.

Usage:
    pip install -r requirements.txt
    python build_ncaa_lines.py

Env vars:
    SEASON            default 2026
    HISTORY_SEASONS   how many seasons of lines/ratings to keep
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import sportsdataverse.cfb as cfb
    import polars as pl
except ImportError:
    print("Needs sportsdataverse + polars — pip install -r requirements.txt", file=sys.stderr)
    raise

SEASON = int(os.environ.get("SEASON", "2026"))
HISTORY_SEASONS = int(os.environ.get("HISTORY_SEASONS", "3"))

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ncaa_lines.json"

# From a real regression against 2,399 completed 2023-2025 games — see
# docstring for the honesty caveat on this one.
RATING_SLOPE = 13.39
RATING_INTERCEPT = 2.66
PREFERRED_BOOKS = ["DraftKings", "Draft Kings", "ESPN Bet", "Bovada"]


def pivot_lines(lines_df, schedule_df):
    """One row per team/side/market -> one record per game, picking the
    first available book in PREFERRED_BOOKS order."""
    sched_lookup = {}
    for row in schedule_df.iter_rows(named=True):
        sched_lookup[row["game_id"]] = row

    by_game = {}
    for row in lines_df.iter_rows(named=True):
        gid = row["game_id"]
        book = row["book"]
        if gid not in sched_lookup:
            continue
        rank = PREFERRED_BOOKS.index(book) if book in PREFERRED_BOOKS else 99
        entry = by_game.setdefault(gid, {"_book_rank": 999})
        if rank > entry["_book_rank"] and entry.get("spread") is not None:
            continue  # already have a better book's spread, don't downgrade
        entry["_book_rank"] = min(entry["_book_rank"], rank)

        sched_row = sched_lookup[gid]
        home_name, away_name = sched_row.get("home_team"), sched_row.get("away_team")
        mtype, abbr, val = row["market_type"], row["abbr"], row["lines"]
        odds = row["odds"]

        if mtype == "spread" and abbr == home_name:
            entry["spread"] = val   # home-relative, negative = home favored — same convention used elsewhere in this app
        elif mtype == "total" and abbr == "over":
            entry["total"] = val
        elif mtype == "money_line" and abbr == home_name:
            entry["home_ml"] = odds
        elif mtype == "money_line" and abbr == away_name:
            entry["away_ml"] = odds

        entry["game_id"] = gid
        entry["season"] = sched_row.get("season")
        entry["week"] = sched_row.get("week")
        entry["home"] = home_name
        entry["away"] = away_name
        entry["kickoff"] = sched_row.get("start_date")
        entry["home_score"] = sched_row.get("home_points")
        entry["away_score"] = sched_row.get("away_points")
        entry["completed"] = bool(sched_row.get("completed"))

    for e in by_game.values():
        e.pop("_book_rank", None)
    return list(by_game.values())


def build():
    seasons = list(range(SEASON - HISTORY_SEASONS + 1, SEASON + 1))

    schedule = cfb.load_cfb_schedule(seasons=seasons)
    print(f"[sportsdataverse] schedule: {schedule.shape[0]} games, seasons {seasons}")

    lines = cfb.load_cfb_betting_lines()
    lines = lines.filter(pl.col("season").is_in([float(s) for s in seasons]))
    print(f"[sportsdataverse] betting lines: {lines.shape[0]} rows")

    games = pivot_lines(lines, schedule)
    print(f"[sportsdataverse] pivoted into {len(games)} games with at least one line")

    ratings_raw = cfb.load_cfb_ratings(seasons=seasons)
    teams = cfb.load_cfb_teams(seasons=seasons)
    id_to_name = {}
    for row in teams.iter_rows(named=True):
        tid = row.get("team_id") or row.get("id")
        name = row.get("school") or row.get("team")
        if tid is not None and name:
            id_to_name[tid] = name

    ratings = {}
    for row in ratings_raw.iter_rows(named=True):
        s = str(row["season"])
        name = id_to_name.get(row["team_id"])
        if not name:
            continue
        ratings.setdefault(s, {})[name] = round(row["net_z"], 4) if row["net_z"] is not None else None
    print(f"[sportsdataverse] ratings for {sum(len(v) for v in ratings.values())} team-seasons")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "rating_calibration": {"slope": RATING_SLOPE, "intercept": RATING_INTERCEPT,
                                "note": "points = slope * (home_net_z - away_net_z) + intercept; "
                                        "season-aggregate rating, softer validation than the NFL one — see docstring"},
        "games": games,
        "ratings": ratings,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":"), default=str))
    print(f"\nwrote {OUT} — {OUT.stat().st_size/1024:.0f}KB")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        print(f"NCAA LINES ETL FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
