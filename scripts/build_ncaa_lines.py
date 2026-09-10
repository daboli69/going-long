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
from build_pipeline import atomic_json

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
    """Select a single preferred bookmaker per game with matched line sides."""
    schedules = {r['game_id']: r for r in schedule_df.iter_rows(named=True)}
    books = {}
    for row in lines_df.iter_rows(named=True):
        gid, book = row['game_id'], row['book']
        if gid not in schedules:
            continue
        r = schedules[gid]
        e = books.setdefault((gid, book), {
            'game_id': gid, 'book': book, 'season': r.get('season'), 'week': r.get('week'),
            'home': r.get('home_team'), 'away': r.get('away_team'), 'kickoff': r.get('start_date'),
            'home_score': r.get('home_points'), 'away_score': r.get('away_points'),
            'completed': bool(r.get('completed'))})
        kind, side, line, odds = row['market_type'], row['abbr'], row['lines'], row['odds']
        if kind == 'spread':
            if side == e['home']:
                e['spread'], e['home_spread_odds'] = line, odds
            elif side == e['away']:
                e['_away_spread'], e['away_spread_odds'] = line, odds
        elif kind == 'total':
            if side == 'over':
                e['total'], e['over_odds'] = line, odds
            elif side == 'under':
                e['_under_total'], e['under_odds'] = line, odds
        elif kind == 'money_line':
            if side == e['home']:
                e['home_ml'] = odds
            elif side == e['away']:
                e['away_ml'] = odds
    selected = {}
    rank = lambda e: PREFERRED_BOOKS.index(e['book']) if e['book'] in PREFERRED_BOOKS else 999
    for e in books.values():
        if e.get('spread') is None or e.pop('_away_spread', None) != -e['spread']:
            e.pop('away_spread_odds', None)
        if e.pop('_under_total', None) != e.get('total'):
            e.pop('under_odds', None)
        if e['game_id'] not in selected or rank(e) < rank(selected[e['game_id']]):
            selected[e['game_id']] = e
    return list(selected.values())


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
    atomic_json(OUT, payload)
    print(f"\nwrote {OUT} — {OUT.stat().st_size/1024:.0f}KB")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        print(f"NCAA LINES ETL FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
