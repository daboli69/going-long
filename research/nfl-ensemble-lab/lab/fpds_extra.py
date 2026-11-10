"""Every numeric player column in the imported FantasyPoints tables as an as-of feature: the player's mean over his previous six weekly rows of the season.

Used by scripts/fpds_column_screen.py to test columns the projection does not read yet, and by the projection for the columns that passed.
Only rows before the game's week are used.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import fpds_usage as X

SKIP_TABLES = ("fantasy_points_allowed", "coverage_matrix", "team_defense", "team_offense", "pace", "playcaller", "coach_records", "lineup_combos", "injury_reports")
META = re.compile(r"^(_|source_|pid$|entity|game_id_asof|opponent_asof|player_id$|team_details__|splits__|season$|week$|team$)")
WINDOW = 6


def _tables():
    base = X._a6_dir()
    for f in sorted(base.glob("*__working_usable.parquet")):
        name = f.name.replace("__working_usable.parquet", "")
        if not name.startswith(SKIP_TABLES):
            yield name, f


def history(tables: list[str] | None = None) -> pd.DataFrame:
    """One row per (season, week, pid): the mean of each column over the player's previous six rows that season (index excludes the row's own week)."""
    parts = []
    for name, f in _tables():
        if tables is not None and name not in tables:
            continue
        t = pd.read_parquet(f)
        if not {"season", "week", "pid"} <= set(t.columns):
            continue
        t = t.dropna(subset=["season", "week", "pid"]).copy()
        t["season"], t["week"], t["pid"] = t["season"].astype(int), t["week"].astype(int), t["pid"].astype(str)
        cols = [c for c in t.columns if "__" in c and not META.match(c)]
        num = t[cols].apply(pd.to_numeric, errors="coerce")
        num = num.loc[:, num.notna().mean() > 0.2]
        num.columns = [f"{name}:{c}" for c in num.columns]
        num = num.loc[:, ~num.columns.duplicated()]
        d = pd.concat([t[["season", "week", "pid"]], num], axis=1).drop_duplicates(["season", "week", "pid"], keep="last").sort_values(["pid", "season", "week"])
        g = d.groupby(["pid", "season"])
        # previous six rows, not including this week: shift then roll
        roll = g[list(num.columns)].transform(lambda s: s.shift(1).rolling(WINDOW, min_periods=1).mean())
        parts.append(pd.concat([d[["season", "week", "pid"]], roll], axis=1).set_index(["season", "week", "pid"]))
    out = pd.concat(parts, axis=1)
    return out.loc[:, ~out.columns.duplicated()]
