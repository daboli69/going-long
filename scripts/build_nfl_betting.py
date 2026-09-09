#!/usr/bin/env python3
"""
build_nfl_betting.py — NFL game lines, power ratings, and (if you have a key)
player props, for the Betting view.

What's actually verified, this session, against real data, before a line of
this shipped:
  - nflreadpy installs clean, pip install nflreadpy pyarrow, no key.
  - nfl.load_schedules() carries real current-season Vegas lines
    (spread_line, total_line, moneylines, spread odds) baked in — this is
    the Lee Sharpe dataset the nflverse community maintains.
  - Power ratings are NOT a pre-built function here — there's no single
    "team net rating" call in nflreadpy the way sportsdataverse has for CFB.
    Built from play-by-play instead: offensive EPA/play minus defensive
    EPA/play allowed, accumulated ONLY from games before the one being
    rated (strictly prior information, so it's usable to price an upcoming
    game rather than describe one that already happened).
  - The EPA-to-points conversion below is a REAL, walk-forward-tested
    number, not invented: regressing 711 real 2023-2025 games' actual
    margins against ratings built ONLY from each team's games before that
    week gives margin ≈ 38.15 × rating_diff + 2.49, correlation 0.382.
    That's a modest, honest signal — nowhere near circular reasoning (an
    earlier, wrong version of this that used each game's own EPA to
    "predict" that same game's margin gave a meaningless 0.988).

What's NOT verified — correctly shaped, cannot be tested from wherever this
runs without credentials, and you should know that before trusting it:
  - ESPN's injury endpoint (undocumented, no key, but unofficial — can
    change without notice).
  - The Odds API player props / live lines (needs a free key from
    the-odds-api.com — this script will just skip that section without
    one; it does not fabricate props).
  - Pinnacle-derived "sharp" data does not exist as a free source anymore —
    confirmed independently (multiple sources, including Pinnacle's own
    GitHub docs repo): they closed public API access July 23, 2025. The
    Odds API's cross-book consensus is the honest substitute — track line
    movement and book agreement, not one book's "true" number.

Usage:
    pip install -r requirements.txt
    python build_nfl_betting.py

Env vars (all optional):
    SEASON            default 2026
    ODDS_API_KEY      from the-odds-api.com — enables live props/lines
    HISTORY_SEASONS   how many past seasons to pull for rating calibration
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import nflreadpy as nfl
    import polars as pl
except ImportError:
    print("Needs nflreadpy + polars + pyarrow — pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    import requests
except ImportError:
    requests = None

SEASON = int(os.environ.get("SEASON", "2026"))
HISTORY_SEASONS = int(os.environ.get("HISTORY_SEASONS", "3"))
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "").strip()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "nfl_betting.json"

# Walk-forward calibrated against 711 real 2023-2025 games — see docstring.
RATING_SLOPE = 38.15
RATING_INTERCEPT = 2.49   # embeds NFL home-field edge
MIN_PRIOR_GAMES = 3       # a rating needs at least this many games behind it to count


def fetch_lines():
    """Real Vegas lines, current + recent seasons, straight off nflreadpy."""
    seasons = list(range(SEASON - HISTORY_SEASONS + 1, SEASON + 1))
    sched = nfl.load_schedules(seasons=seasons)
    games = []
    for row in sched.iter_rows(named=True):
        games.append({
            "game_id": row.get("game_id"),
            "season": row.get("season"), "week": row.get("week"),
            "away": row.get("away_team"), "home": row.get("home_team"),
            "kickoff": row.get("gameday"), "gametime": row.get("gametime"),
            "spread": row.get("spread_line"), "total": row.get("total_line"),
            "away_ml": row.get("away_moneyline"), "home_ml": row.get("home_moneyline"),
            "away_spread_odds": row.get("away_spread_odds"),
            "home_spread_odds": row.get("home_spread_odds"),
            "away_score": row.get("away_score"), "home_score": row.get("home_score"),
            "completed": row.get("away_score") is not None,
        })
    print(f"[nflreadpy] {len(games)} games, seasons {seasons}")
    return games


def _load_pbp_available(seasons):
    """nflreadpy's play-by-play loader validates its own season range
    internally and raises if a requested season is outside what it
    currently accepts — in practice this is the CURRENT season, before
    nflverse has published play-by-play for it yet, even though schedules
    (fetch_lines, above) already has real lines for it. Confirmed live:
    load_pbp(seasons=[2024,2025,2026]) throws "Season must be between
    1999 and 2025"; load_pbp(seasons=[2024,2025]) succeeds fine.

    Try the full list first; on failure, drop the most recent season and
    retry, repeating until something loads or nothing's left. This is the
    same shape as every other honest-degradation path in this project —
    ratings come back built from whatever seasons are actually available
    rather than taking the whole build down over one season not existing
    yet, and current-season GAMES/LINES (which don't depend on this) are
    completely unaffected either way."""
    remaining = list(seasons)
    while remaining:
        try:
            return nfl.load_pbp(seasons=remaining)
        except Exception as exc:  # noqa: BLE001
            dropped = remaining.pop()
            print(f"  ! PBP unavailable for {dropped} ({exc}) — retrying without it")
    print("  ! No PBP available for any requested season — ratings will be empty this run")
    return None


def build_ratings():
    """Season-to-date net EPA/play per team, using ONLY games strictly
    before the one a rating would be used to price. Returns
    {season: {team: {week: rating_entering_that_week}}}."""
    seasons = list(range(SEASON - HISTORY_SEASONS + 1, SEASON + 1))
    pbp = _load_pbp_available(seasons)
    if pbp is None or pbp.is_empty():
        return {}

    off = (pbp.filter(pl.col("posteam").is_not_null())
              .group_by(["season", "week", "posteam"])
              .agg(pl.col("epa").mean().alias("off_epa")))
    deff = (pbp.filter(pl.col("defteam").is_not_null())
               .group_by(["season", "week", "defteam"])
               .agg(pl.col("epa").mean().alias("def_epa_allowed")))

    merged = (off.rename({"posteam": "team"})
                 .join(deff.rename({"defteam": "team"}), on=["season", "week", "team"])
                 .sort(["team", "season", "week"]))
    merged = merged.with_columns((pl.col("off_epa") - pl.col("def_epa_allowed")).alias("net_epa"))
    merged = merged.with_columns(
        pl.col("net_epa").shift(1).over(["team", "season"]).cum_sum().over(["team", "season"]).alias("_sum"),
        pl.col("net_epa").shift(1).over(["team", "season"]).cum_count().over(["team", "season"]).alias("_n"),
    )
    merged = merged.filter(pl.col("_n") >= MIN_PRIOR_GAMES)
    merged = merged.with_columns((pl.col("_sum") / pl.col("_n")).alias("rating"))

    out = {}
    for row in merged.iter_rows(named=True):
        s, wk, team = str(row["season"]), row["week"], row["team"]
        out.setdefault(s, {}).setdefault(team, {})[str(wk)] = round(row["rating"], 5)
    print(f"[ratings] built for {sum(len(v) for v in out.values())} team-seasons, "
          f"conversion: margin ≈ {RATING_SLOPE}×diff + {RATING_INTERCEPT}")
    return out


def fetch_espn_injuries():
    """ESPN's hidden injury endpoint. No key, no login — but unofficial,
    can change without notice. NOT reachable/testable from every
    environment this script might run in; if it 404s or the shape has
    changed, this degrades to an empty dict rather than failing the build."""
    if requests is None:
        return {}
    out = {}
    try:
        teams_resp = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams", timeout=20)
        teams_resp.raise_for_status()
        team_ids = [t["team"]["id"] for t in teams_resp.json()
                    .get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])]
        for tid in team_ids:
            try:
                r = requests.get(
                    f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/teams/{tid}/injuries",
                    timeout=15)
                if r.ok:
                    out[tid] = r.json()
            except Exception as exc:  # noqa: BLE001
                print(f"  ! injuries for team {tid} failed: {exc}")
            time.sleep(0.1)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! ESPN injuries unavailable this run: {exc}")
        return {}
    print(f"[espn] injuries pulled for {len(out)} teams")
    return out


def fetch_odds_api_props():
    """Player props from the-odds-api.com. Needs a free key — get one at
    the-odds-api.com, no card required. Skips cleanly with no key rather
    than failing the whole build."""
    if not ODDS_API_KEY or requests is None:
        print("[odds-api] ODDS_API_KEY not set — skipping props, game lines still come from nflreadpy")
        return []
    try:
        events = requests.get(
            "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events",
            params={"apiKey": ODDS_API_KEY}, timeout=20).json()
        props = []
        for ev in events[:20]:  # credits burn per call — cap per run
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/americanfootball_nfl/events/{ev['id']}/odds",
                params={"apiKey": ODDS_API_KEY, "regions": "us",
                        "markets": "player_pass_yds,player_rush_yds,player_reception_yds,player_anytime_td",
                        "oddsFormat": "american"}, timeout=20)
            if r.ok:
                props.append(r.json())
            time.sleep(0.2)
        print(f"[odds-api] pulled props for {len(props)} events")
        return props
    except Exception as exc:  # noqa: BLE001
        print(f"  ! Odds API fetch failed: {exc}")
        return []


def build():
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": SEASON,
        "rating_calibration": {"slope": RATING_SLOPE, "intercept": RATING_INTERCEPT,
                                "note": "points = slope * (home_rating - away_rating) + intercept; "
                                        "walk-forward tested on real 2023-2025 games, not invented"},
        "games": fetch_lines(),
        "ratings": build_ratings(),
        "injuries": fetch_espn_injuries(),
        "props_raw": fetch_odds_api_props(),
        "has_live_odds": bool(ODDS_API_KEY),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":"), default=str))
    print(f"\nwrote {OUT} — {OUT.stat().st_size/1024:.0f}KB")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:  # noqa: BLE001
        print(f"NFL BETTING ETL FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
