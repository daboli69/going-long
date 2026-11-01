"""Margin-aware Elo, rebuilt from data/raw/games.csv for the luck-adjusted strength test (docs/LUCK_ADJUSTED_PREREGISTRATION.md).

Written from the standard formula, independently of lab/homewin_v2.py, so a match with the lab's saved Elo forecasts means two implementations agree.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from .ingest import normalize_team

ROOT = Path(__file__).resolve().parents[1]
GAMES = Path(os.environ.get("LUCK_DATA", ROOT / "data")) / "raw" / "games.csv"


def load_games(regular_only: bool = True, since: int = 1999, neutral_rule: str = "stadium_id", until: int = 9999) -> pd.DataFrame:
    """One row per game in kickoff order: ids, teams (current codes), scores (NaN until played), neutral flag, closing lines."""
    g = pd.read_csv(GAMES)
    g = g[(g["season"] >= since) & (g["season"] <= until)]
    if regular_only:
        g = g[g["game_type"] == "REG"]
    g = g.copy()
    g["home"] = g["home_team"].map(normalize_team)
    g["away"] = g["away_team"].map(normalize_team)
    # neutral_rule "stadium_id": the schedule says Neutral, or the game is not at the home team's usual stadium that season, judged by stadium id
    # (a renamed stadium keeps its id). "lab" judges by stadium name, as the lab's saved Elo does, to reproduce it exactly.
    col = "stadium_id" if neutral_rule == "stadium_id" else "stadium"
    usual = g.groupby(["season", "home"])[col].transform(lambda x: x.mode().iat[0])
    g["neutral"] = g["location"].eq("Neutral") | (g[col] != usual)
    g["kickoff"] = pd.to_datetime(g["gameday"] + " " + g["gametime"].fillna("13:00"))
    g["played"] = g["home_score"].notna() & g["away_score"].notna()
    return g.sort_values(["kickoff", "game_id"]).reset_index(drop=True)


def elo_history(games: pd.DataFrame, k: float = 20.0, hfa: float = 55.0, revert: float = 1.0 / 3.0, start: float = 1500.0,
                mov: bool = True) -> pd.DataFrame:
    """Pre-game Elo of both teams and the home win probability, for every game, using only earlier games.

    Standard formula: expected = 1 / (1 + 10^(-gap / 400)), gap = home rating + home field - away rating (no home field at a neutral site);
    update = K x multiplier x (result - expected), multiplier = ln(|margin| + 1) x 2.2 / (0.001 x winner's gap + 2.2) when `mov`, else 1;
    every rating moves a share `revert` of the way back to `start` when a new season begins."""
    ratings: dict = {}
    season = None
    rows = []
    for g in games.itertuples(index=False):
        if g.season != season:
            ratings = {t: start + (1 - revert) * (r - start) for t, r in ratings.items()}
            season = g.season
        hh, aa = ratings.get(g.home, start), ratings.get(g.away, start)
        gap = hh + (0.0 if g.neutral else hfa) - aa
        exp = 1.0 / (1.0 + 10 ** (-gap / 400.0))
        rows.append((g.game_id, hh, aa, gap, exp))
        if not g.played:
            continue
        margin = g.home_score - g.away_score
        act = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
        mult = 1.0 if (margin == 0 or not mov) else np.log(abs(margin) + 1.0) * 2.2 / ((gap if margin > 0 else -gap) * 0.001 + 2.2)
        d = k * mult * (act - exp)
        ratings[g.home], ratings[g.away] = hh + d, aa - d
    return pd.DataFrame(rows, columns=["game_id", "home_elo", "away_elo", "gap", "p_home"])
