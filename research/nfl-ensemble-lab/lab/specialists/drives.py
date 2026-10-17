"""Phase 8 specialist E data: team-game drive outcomes from play-by-play, windowed strictly pregame."""
from __future__ import annotations

import pandas as pd

from ..config import CACHE_DIR, RAW_DIR

OUT = CACHE_DIR / "phase8_drives.parquet"


def team_game_drives(games: pd.DataFrame, seasons) -> pd.DataFrame:
    from ..advanced import _id_map, _opp_map, _with_defense
    from ..availability import _team
    parts = []
    for s in seasons:
        p = RAW_DIR / f"play_by_play_{s}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p, columns=["game_id", "posteam", "fixed_drive", "fixed_drive_result"]).dropna(subset=["posteam", "fixed_drive"])
        d = d.drop_duplicates(["game_id", "posteam", "fixed_drive"])
        d["td"] = (d["fixed_drive_result"] == "Touchdown").astype(float)
        d["fg"] = (d["fixed_drive_result"] == "Field goal").astype(float)
        g = d.groupby(["game_id", "posteam"]).agg(drives=("fixed_drive", "size"), td=("td", "sum"), fg=("fg", "sum")).reset_index()
        parts.append(g)
    tg = pd.concat(parts, ignore_index=True).rename(columns={"posteam": "team"})
    tg["team"] = tg["team"].map(_team)
    tg["game_id"] = tg["game_id"].map(_id_map(games))
    tg = tg.dropna(subset=["game_id", "team"])
    tg["td_rate"] = tg["td"] / tg["drives"]
    tg["fg_rate"] = tg["fg"] / tg["drives"]
    tg = tg[["game_id", "team", "drives", "td_rate", "fg_rate"]]
    return _with_defense(tg, _opp_map(games), {"drives": "drives", "td_rate": "td_rate", "fg_rate": "fg_rate"})


def build(games: pd.DataFrame, seasons) -> pd.DataFrame:
    """Per (game, team): season-blended and last-5 pregame drive rates (offense and defense allowed)."""
    from ..advanced import window_features
    tg = team_game_drives(games, seasons)
    w = window_features(games, tg, "p8dr_")
    w.to_parquet(OUT, index=False)
    return w
