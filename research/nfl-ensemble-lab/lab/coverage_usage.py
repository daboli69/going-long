"""Defensive coverage (man, zone and the named shells) as inputs to the simulated game. Local files only.

Two FantasyPoints tables feed it: the coverage matrix (one row per defense per week: how often it played man, Cover 3, and so on) and receiving
separation by coverage (one row per receiver per week: routes and yards per route against man and against zone). Only weeks before the game's
week are used (a week's own numbers include its outcome). Nothing here reaches the simulation until `scripts/coverage_check.py` shows, on games
the fit never saw, that it beats the nflverse-only prediction in both 2025 and 2026.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import fpds_usage as X
from . import gamecenter_data as D
from . import usage as U
from .config import CACHE_DIR
from .ingest import normalize_team

WINDOW = 6
SHRINK_ROUTES = 30.0           # routes a receiver needs against one coverage before his split counts as much as his overall number
DEF_COLS = {"man": "man_zone__man_pct", "c1": "coverages__cover_1_pct", "c2": "coverages__cover_2_pct", "c3": "coverages__cover_3_pct",
            "c4": "coverages__cover_4_pct", "c6": "coverages__cover_6_pct", "blitz": "blitz__blitz_pct"}
GROUPS = ("WR", "TE", "RB")


def _a6():
    return X._a6_dir()


def defense_weekly() -> pd.DataFrame:
    """One row per defense per week: share of snaps (0 to 1) in each coverage. Rows with no snaps are dropped."""
    t = pd.read_parquet(_a6() / "coverage_matrix__working_usable.parquet")
    out = t[["season", "week", "team"]].copy()
    for k, c in DEF_COLS.items():
        out[k] = pd.to_numeric(t[c], errors="coerce") / 100.0
    out["team"] = out["team"].map(lambda s: normalize_team(s) if isinstance(s, str) else s)
    out = out.dropna(subset=["season", "week", "team"]).drop_duplicates(["season", "week", "team"], keep="last")
    out["season"], out["week"] = out["season"].astype(int), out["week"].astype(int)
    return out


def receiver_weekly() -> pd.DataFrame:
    """One row per receiver per week: routes and yards per route overall, against man and against zone."""
    t = pd.read_parquet(_a6() / "receiving_separation_by_coverage__working_usable.parquet")
    out = t[["season", "week", "pid"]].copy()
    for k, c in {"rte": "overall__rte", "yprr": "overall__yprr", "m_rte": "man__rte", "m_yprr": "man__yprr", "z_rte": "zone__rte", "z_yprr": "zone__yprr"}.items():
        out[k] = pd.to_numeric(t[c], errors="coerce")
    out["pid"] = out["pid"].astype(str)
    out = out.dropna(subset=["season", "week", "pid"]).drop_duplicates(["season", "week", "pid"], keep="last")
    out["season"], out["week"] = out["season"].astype(int), out["week"].astype(int)
    return out


class Lagged:
    """Rolling features as of a week: defenses' coverage mix and receivers' split yards per route, using only earlier weeks of that season."""

    def __init__(self):
        self.d = defense_weekly()
        self.r = receiver_weekly()
        self._dcache, self._rcache = {}, {}

    def defense(self, season: int, week: int) -> pd.DataFrame:
        """Per-team mean over the last WINDOW weeks before `week` (at least 2), minus the league mean that week."""
        key = (season, week)
        if key not in self._dcache:
            s = self.d[(self.d["season"] == season) & (self.d["week"] < week)]
            weeks = sorted(s["week"].unique())[-WINDOW:]
            s = s[s["week"].isin(weeks)]
            m = s.groupby("team")[list(DEF_COLS)].mean()
            m = m[s.groupby("team")["week"].nunique() >= 2]
            self._dcache[key] = m - m.mean() if len(m) else m
        return self._dcache[key]

    def receivers(self, season: int, week: int) -> pd.DataFrame:
        """Per receiver: routes-weighted yards per route overall, against man and against zone, shrunk toward his overall number."""
        key = (season, week)
        if key not in self._rcache:
            s = self.r[(self.r["season"] == season) & (self.r["week"] < week)]
            weeks = sorted(s["week"].unique())[-WINDOW:]
            s = s[s["week"].isin(weeks)].copy()
            for p in ("", "m_", "z_"):
                s[p + "yds"] = s[p + "rte"].fillna(0) * s[p + "yprr"].fillna(0)
            g = s.groupby("pid")[["rte", "yds", "m_rte", "m_yds", "z_rte", "z_yds"]].sum()
            g = g[g["rte"] >= 20]
            overall = g["yds"] / g["rte"]
            man = (g["m_yds"] + SHRINK_ROUTES * overall) / (g["m_rte"] + SHRINK_ROUTES)
            zone = (g["z_yds"] + SHRINK_ROUTES * overall) / (g["z_rte"] + SHRINK_ROUTES)
            self._rcache[key] = pd.DataFrame({"overall": overall, "man": man, "zone": zone})
        return self._rcache[key]


def opponents() -> dict:
    """(season, week, team) -> opposing team, from the schedule."""
    G = D.games_table()
    out = {}
    for g in G.itertuples():
        out[(int(g.season), int(g.week), g.home_team)] = g.away_team
        out[(int(g.season), int(g.week), g.away_team)] = g.home_team
    return out


def feature_names() -> list[str]:
    names = ["matched"]
    names += [f"man_{p}" for p in GROUPS]
    names += [f"{k}_{p}" for k in ("c1", "c2", "c3", "c4", "c6", "blitz") for p in GROUPS]
    return names


def team_game_features(lag: Lagged, opp: dict, season: int, week: int, team: str, pids, pos) -> np.ndarray:
    """Feature matrix (players x feature_names) for one team-game. A player with no history, or a game against a defense with
    fewer than two weeks on record, gets zeros, which leaves the nflverse prediction as it was."""
    names = feature_names()
    F = np.zeros((len(pids), len(names)))
    o = opp.get((season, week, team))
    dm = lag.defense(season, week)
    if o is None or o not in dm.index:
        return F
    d = dm.loc[o]
    rc = lag.receivers(season, week).reindex(pids)
    for i, (pid, ps) in enumerate(zip(pids, pos)):
        if ps not in GROUPS:
            continue
        r = rc.iloc[i]
        if not np.isnan(r["overall"]) and r["overall"] > 0.2:
            F[i, 0] = d["man"] * (r["man"] - r["zone"]) / r["overall"]
        F[i, 1 + GROUPS.index(ps)] = d["man"]
        for j, k in enumerate(("c1", "c2", "c3", "c4", "c6", "blitz")):
            F[i, 4 + 3 * j + GROUPS.index(ps)] = d[k]
    return F


FAMILIES = {
    "A. This receiver against this defense (his man-minus-zone yards per route x the defense's man rate)": ["matched"],
    "B. Man rate by position (does more man shift yards between wide receivers, tight ends and backs)": ["man_WR", "man_TE", "man_RB"],
    "C. Every coverage shell by position (Cover 1, 2, 3, 4, 6 and blitz)": [n for n in feature_names() if n != "matched" and not n.startswith("man_")],
}


# --------------------------------------------------------------------------- what the simulation reads

APPLIED_PATH = CACHE_DIR / "coverage_applied.json"
MULT_CLIP = (0.9, 1.1)
_LAG: dict = {}


def load_applied(path=APPLIED_PATH) -> dict:
    """{"rec_yds": {"matched": weight}} written by scripts/coverage_check.py for the stats whose typical miss fell in both 2025 and 2026 (owner rule, 2026-11-07)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def receiving_factors(season: int, week: int, versus: str, rule: dict | None = None) -> dict:
    """pid -> factor for receiving yards against `versus`: 1 + weight x (the defense's man rate above the league x the receiver's man-minus-zone yards per route, over his overall).
    Empty when there is no rule or the defense has fewer than two weeks on record."""
    rule = load_applied() if rule is None else rule
    w = (rule.get("rec_yds") or {}).get("matched")
    if w is None:
        return {}
    if "lag" not in _LAG:
        _LAG["lag"] = Lagged()
    lag = _LAG["lag"]
    dm = lag.defense(season, week)
    if versus not in dm.index:
        return {}
    man = float(dm.loc[versus, "man"])
    rc = lag.receivers(season, week)
    m = rc[rc["overall"] > 0.2]
    matched = man * (m["man"] - m["zone"]) / m["overall"]
    return {str(pid): float(np.clip(1.0 + w * v, *MULT_CLIP)) for pid, v in matched.items()}
