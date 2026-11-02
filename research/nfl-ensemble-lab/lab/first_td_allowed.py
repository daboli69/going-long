"""First touchdown each defense gives up, by the scorer's position. Counts, not predictions.

A team's first TD given up is the first touchdown scored against it in a game. The overall option keeps only the game's first touchdown, charged to the
team that gave it up. Touchdowns not scored by an offensive pass or run (returns, defensive and special teams scores) go in Def/ST.
Two-point tries are not touchdowns here. Source: nflverse play-by-play and the nflverse players table (position).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache" / "first_td_allowed"
POSITIONS = ["QB", "RB", "WR", "TE", "Other", "Def/ST"]
POS_MAP = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE"}


def seasons() -> list[int]:
    return sorted(int(p.stem.split("_")[-1]) for p in RAW.glob("play_by_play_*.parquet") if int(p.stem.split("_")[-1]) >= 2015)


def build_season(season: int) -> pd.DataFrame:
    """One row per team per game for the first touchdown that team scored, with who scored and whether it was the game's first."""
    src = RAW / f"play_by_play_{season}.parquet"
    path = CACHE / f"{season}.parquet"
    if path.exists() and path.stat().st_mtime >= src.stat().st_mtime:
        return pd.read_parquet(path)
    cols = ["game_id", "week", "season_type", "home_team", "away_team", "play_id", "qtr", "touchdown", "two_point_attempt", "td_team", "td_player_id", "td_player_name", "posteam", "pass_touchdown", "rush_touchdown"]
    p = pd.read_parquet(src, columns=cols)
    p = p[p["season_type"] == "REG"]
    games = p[["game_id", "week", "home_team", "away_team"]].drop_duplicates("game_id")
    t = p[(p["touchdown"] == 1) & (p["two_point_attempt"].fillna(0) == 0) & p["td_team"].notna()].sort_values(["game_id", "play_id"]).copy()
    pl = pd.read_parquet(RAW / "players.parquet", columns=["gsis_id", "position"]).drop_duplicates("gsis_id").set_index("gsis_id")["position"]
    off = ((t["pass_touchdown"] == 1) | (t["rush_touchdown"] == 1)) & (t["td_team"] == t["posteam"])
    t["pos"] = np.where(off, t["td_player_id"].map(pl).map(POS_MAP).fillna("Other"), "Def/ST")
    t["game_first"] = ~t.duplicated("game_id")
    first = t.drop_duplicates(["game_id", "td_team"]).merge(games, on=["game_id", "week"], suffixes=("", "_g"))
    first["def_team"] = np.where(first["td_team"] == first["home_team"], first["away_team"], first["home_team"])
    out = first[["game_id", "week", "td_team", "def_team", "td_player_name", "pos", "game_first", "qtr"]].rename(columns={"td_team": "scoring_team", "td_player_name": "scorer"})
    out.attrs = {}
    out = out.assign(season=season)
    g = pd.concat([games.assign(team=games["home_team"]), games.assign(team=games["away_team"])])[["game_id", "week", "team"]].assign(season=season)
    CACHE.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path)
    g.to_parquet(CACHE / f"{season}_games.parquet")
    return out


def table(season: int, weeks: list[int] | None, overall: bool) -> dict:
    td = build_season(season)
    g = pd.read_parquet(CACHE / f"{season}_games.parquet")
    avail = sorted(int(w) for w in g["week"].unique())
    ws = [w for w in (weeks or avail) if w in avail]
    td, g = td[td["week"].isin(ws)], g[g["week"].isin(ws)]
    if overall:
        td = td[td["game_first"]]
    rows = []
    for team, gg in g.groupby("team"):
        mine = td[td["def_team"] == team]
        counts = {p: int((mine["pos"] == p).sum()) for p in POSITIONS}
        n = int(len(mine))
        rows.append({"team": team, "games": int(len(gg)), "tds": n, "counts": counts, "pct": {p: (counts[p] / n if n else None) for p in POSITIONS}})
    n_all = int(len(td))
    league = {p: int((td["pos"] == p).sum()) for p in POSITIONS}
    return {"season": season, "weeks": ws, "weeks_available": avail, "overall": overall, "rows": sorted(rows, key=lambda r: r["team"]),
            "league": {"games": int(len(g) // 2), "tds": n_all, "counts": league, "pct": {p: (league[p] / n_all if n_all else None) for p in POSITIONS}}}
