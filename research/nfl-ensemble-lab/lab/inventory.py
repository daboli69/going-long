"""Phase 7 data inventory: every source the lab downloads, its coverage and freshness, and how it is used.

Roles:
  model      - historically valid pregame feature (as-of reconstructable for 2016+), fed to models
  model*     - model feature whose 2026 coverage is incomplete (see the gap column)
  monitoring - live/current-only information shown on dashboards, never a model input
GOING comparison is a static read-only finding from inspecting the GOING repository (Phase 7).
"""
from __future__ import annotations

import re

import pandas as pd

from .config import RAW_DIR

# (file prefix, label, url, granularity, role, GOING uses it?, notes)
CATALOG = [
    ("play_by_play", "nflverse play-by-play", "github.com/nflverse/nflverse-data/releases/tag/pbp", "play", "model", "yes (nflreadpy)", ""),
    ("participation", "nflverse play participation", "nflverse-data/releases/tag/pbp_participation", "play x player", "model*", "yes (2026 unavailable)",
     "Not published for 2026: the Phase 5 RAPM stops at 2025. Phase 7 snap model is the substitute."),
    ("snap_counts", "PFR snap counts (nflverse)", "nflverse-data/releases/tag/snap_counts", "player-game", "model", "yes", "Basis of the Phase 7 snap model; 2026 available."),
    ("injuries", "Official injury reports (nflverse)", "nflverse-data/releases/tag/injuries", "player-week", "model*", "yes",
     "No verified publication time for 2025 or 2026 weeks 1-5 (lab archive began 2026-10); those games have no verified report."),
    ("depth_charts", "Depth charts (nflverse / ESPN)", "nflverse-data/releases/tag/depth_charts", "player-week", "monitoring", "no", "Static; ignores injuries."),
    ("ngs_", "Next Gen Stats", "nflverse-data/releases/tag/nextgen_stats", "player-week", "model", "yes", ""),
    ("pfradv_", "PFR advanced stats", "nflverse-data/releases/tag/pfr_advstats", "player-game", "model", "no", ""),
    ("ftn", "FTN charting", "nflverse-data/releases/tag/ftn_charting", "play", "model", "yes (scheme tendencies)", "2022+ only."),
    ("players", "nflverse players (ids, positions)", "nflverse-data/releases/tag/players", "player", "model", "yes", ""),
    ("roster_weekly", "nflverse weekly rosters", "nflverse-data/releases/tag/weekly_rosters", "player-week", "monitoring", "yes",
     "Phase 7: ACT/RES/INA status; no as-of timestamps, so monitoring only."),
    ("games.csv", "nfldata schedule, results, lines", "github.com/nflverse/nfldata", "game", "model", "yes", "Closing line is a benchmark, not an input."),
]
LIVE = [
    ("ESPN injuries", "site.api.espn.com/apis/site/v2/sports/football/nfl/injuries", "player", "monitoring", "no"),
    ("ESPN scoreboard", "site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", "game", "monitoring", "yes"),
    ("ESPN transactions", "site.api.espn.com/apis/site/v2/sports/football/nfl/transactions", "transaction", "monitoring", "no"),
    ("NFL.com injury report", "www.nfl.com/injuries/", "player-week", "monitoring (official)", "no",
     "Phase 7: same content as nflverse, archived with retrieval time; 100% gsis match."),
    ("Sleeper players", "api.sleeper.app/v1/players/nfl", "player", "monitoring", "yes (ADP / ids)",
     "Phase 7: QB depth order, injury and practice status; fetched at most daily."),
    ("Open-Meteo forecast", "api.open-meteo.com", "game", "monitoring", "no", "Forecast weather never enters models."),
]
NOT_AVAILABLE = [
    ("nflverse player_stats 2026", "release asset stats_player_week_2026 not published (checked 2026-10-17)"),
    ("nflverse pbp_participation 2026", "not published (also unavailable in GOING)"),
    ("Official game-day inactives", "no free machine-readable source; ESPN 'inactive' statuses and weekly-roster INA are partial"),
    ("Coaching/scheme play-calling data", "no free current source beyond FTN tendencies"),
]


def _seasons(prefix: str) -> list[int]:
    return sorted(int(m.group(1)) for p in RAW_DIR.glob(f"{prefix}*") if (m := re.search(r"(20\d\d)", p.name)))


def _latest_week(prefix: str, season: int):
    for p in RAW_DIR.glob(f"{prefix}*{season}*.parquet"):
        try:
            return int(pd.read_parquet(p, columns=["week"])["week"].max())
        except Exception:
            return None
    return None


def build(season: int | None = None) -> pd.DataFrame:
    from . import sources
    from .data_pipeline import current_season
    season = season or current_season()
    man = sources.load_manifest()
    rows = []
    for prefix, label, url, gran, role, going, note in CATALOG:
        ss = _seasons(prefix)
        stamps = [v.get("downloaded_at") for k, v in man.items() if prefix.rstrip("_.csv") in k and v.get("downloaded_at")]
        rows.append({"source": label, "url": url, "granularity": gran, "role": role,
                     "seasons": f"{min(ss)}-{max(ss)}" if ss else ("schedule" if prefix == "games.csv" else "-"),
                     f"latest {season} week": _latest_week(prefix, season) if season in ss else ("n/a" if ss else None),
                     "last_download": max(stamps) if stamps else None, "in GOING": going, "notes": note})
    for x in LIVE:
        label, url, gran, role, going = x[:5]
        rows.append({"source": label, "url": url, "granularity": gran, "role": role, "seasons": "live", "in GOING": going,
                     "notes": x[5] if len(x) > 5 else ""})
    return pd.DataFrame(rows)


def unavailable() -> pd.DataFrame:
    return pd.DataFrame(NOT_AVAILABLE, columns=["data", "status"])
