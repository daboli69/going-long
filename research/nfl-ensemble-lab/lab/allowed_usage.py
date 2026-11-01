"""What each defense gives up to each position, from FantasyPoints' fantasy-points-allowed tables, converted to actual stats.

Each table has one row per defense per week: the catches, yards, touchdowns, carries and fantasy points that defense allowed to a position
(quarterbacks, running backs, tight ends, wide receivers). The stats are used, not only the fantasy-point total: a defense that gives up
yards through the air but not on the ground shows that in the stats and is blurred in a single score. Only weeks before the game's week
feed a prediction. Nothing here reaches the simulation until `scripts/allowed_check.py` shows a gain on games the fit never saw.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import fpds_usage as X
from .ingest import normalize_team

WINDOW = 6
K_SHRINK = 4.0   # games of league-average play a defense is assumed to have before its own record counts for more
FILES = {"QB": "qb__working_usable", "RB": "rb__15f126a75b45__usable", "TE": "te__c0cc892bbcc3__usable", "WR": "wr__cb5b53e74409__usable"}
# stat the simulation predicts -> position -> column of the allowed table
STAT_COLS = {
    "rec_yds": {"WR": "receiving__yds", "TE": "receiving__yds", "RB": "receiving__yds"},
    "rec": {"WR": "receiving__rec", "TE": "receiving__rec", "RB": "receiving__rec"},
    "rush_yds": {"RB": "rushing__yds", "QB": "rushing__yds"},
}
FP_COL = "fp__fp"


def allowed_weekly() -> pd.DataFrame:
    """One row per defense, week and position, with every stat that defense allowed to that position."""
    base = X._a6_dir()
    keep = sorted({c for cols in STAT_COLS.values() for c in cols.values()} | {FP_COL})
    frames = []
    for pos, f in FILES.items():
        t = pd.read_parquet(base / f"fantasy_points_allowed_{f}.parquet")
        out = t[["season", "week", "team"]].copy()
        for c in keep:
            out[c] = pd.to_numeric(t[c], errors="coerce") if c in t.columns else np.nan
        out["pos"] = pos
        frames.append(out)
    a = pd.concat(frames, ignore_index=True)
    a["team"] = a["team"].map(lambda s: normalize_team(s) if isinstance(s, str) else s)
    a = a.dropna(subset=["season", "week", "team"]).drop_duplicates(["season", "week", "team", "pos"], keep="last")
    a["season"], a["week"] = a["season"].astype(int), a["week"].astype(int)
    return a


class Allowed:
    """Each defense's recent record against a position, as a shrunk relative gap to the league: 0.10 means 10% more than league average."""

    def __init__(self, table: pd.DataFrame | None = None):
        self.t = allowed_weekly() if table is None else table
        self._cache: dict = {}

    def gaps(self, season: int, week: int) -> pd.DataFrame:
        """Index (team, pos); one column per allowed stat. Defenses with fewer than two earlier weeks are left out."""
        key = (season, week)
        if key not in self._cache:
            s = self.t[(self.t["season"] == season) & (self.t["week"] < week)]
            weeks = sorted(s["week"].unique())[-WINDOW:]
            s = s[s["week"].isin(weeks)]
            cols = [c for c in s.columns if c not in ("season", "week", "team", "pos")]
            g = s.groupby(["team", "pos"])[cols].mean()
            n = s.groupby(["team", "pos"])["week"].nunique()
            league = g.groupby(level="pos").transform("mean")
            rel = (g / league.replace(0, np.nan) - 1.0).fillna(0.0)
            rel = rel.mul(n / (n + K_SHRINK), axis=0)
            self._cache[key] = rel[n >= 2]
        return self._cache[key]


def gap(allowed: Allowed, opp: dict, season: int, week: int, team: str, pos: str, col: str) -> float:
    """The opposing defense's relative gap to the league for one stat against one position (0 when unknown)."""
    o = opp.get((season, week, team))
    g = allowed.gaps(season, week)
    if o is None or (o, pos) not in g.index or col not in g.columns:
        return 0.0
    return float(g.loc[(o, pos), col])
