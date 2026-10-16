"""Normalize the schedule, build canonical games, and aggregate play-by-play
into one row per team per game."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Relocations and alternate abbreviations -> current nflverse abbreviation.
TEAM_ALIASES = {
    "OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WSH": "WAS",
    "JAC": "JAX", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
}
TEAMS = frozenset({
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
    "HOU", "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
})


def normalize_team(code) -> str:
    code = str(code).strip().upper()
    code = TEAM_ALIASES.get(code, code)
    if code not in TEAMS:
        raise ValueError(f"Unknown team abbreviation: {code!r}")
    return code


def canonical_game_id(season: int, week: int, away: str, home: str) -> str:
    """nflverse convention: {season}_{week:02d}_{away}_{home} with normalized teams."""
    return f"{int(season)}_{int(week):02d}_{normalize_team(away)}_{normalize_team(home)}"


def american_to_prob(odds) -> float:
    """Implied probability (with vig) from American odds; NaN when missing."""
    if odds is None or pd.isna(odds) or odds == 0:
        return np.nan
    odds = float(odds)
    return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)


def no_vig_home_prob(home_ml, away_ml) -> float:
    """Proportional (multiplicative) de-vig of a two-way moneyline."""
    ph, pa = american_to_prob(home_ml), american_to_prob(away_ml)
    if np.isnan(ph) or np.isnan(pa) or ph + pa <= 0:
        return np.nan
    return ph / (ph + pa)


def find_duplicates(games: pd.DataFrame) -> pd.DataFrame:
    """Rows sharing a canonical id, or the same teams on the same date."""
    by_id = games[games.duplicated("game_id", keep=False)]
    by_match = games[games.duplicated(["gameday", "home_team", "away_team"], keep=False)]
    return pd.concat([by_id, by_match]).drop_duplicates()


def load_games(path: Path, first_season: int) -> tuple[pd.DataFrame, list[str]]:
    """Read nfldata games.csv into the canonical game table. Returns (games, warnings)."""
    raw = pd.read_csv(path, low_memory=False)
    raw = raw[raw["season"] >= first_season].copy()
    warnings: list[str] = []
    g = pd.DataFrame({
        "season": raw["season"].astype(int),
        "week": raw["week"].astype(int),
        "game_type": raw["game_type"].astype(str),
        "gameday": raw["gameday"].astype(str),
        "gametime": raw["gametime"].fillna("13:00").astype(str),
        "home_team": raw["home_team"].map(normalize_team),
        "away_team": raw["away_team"].map(normalize_team),
        "home_score": pd.to_numeric(raw["home_score"], errors="coerce"),
        "away_score": pd.to_numeric(raw["away_score"], errors="coerce"),
        "neutral_site": (raw["location"].astype(str) == "Neutral").astype(int),
        "div_game": pd.to_numeric(raw["div_game"], errors="coerce").fillna(0).astype(int),
        "roof": raw["roof"].fillna("").astype(str),
        "stadium_id": raw["stadium_id"].fillna("").astype(str),
        "home_qb_id": raw["home_qb_id"], "away_qb_id": raw["away_qb_id"],
        "home_qb_name": raw["home_qb_name"], "away_qb_name": raw["away_qb_name"],
        "spread_line": pd.to_numeric(raw["spread_line"], errors="coerce"),
        "total_line": pd.to_numeric(raw["total_line"], errors="coerce"),
        "home_moneyline": pd.to_numeric(raw["home_moneyline"], errors="coerce"),
        "away_moneyline": pd.to_numeric(raw["away_moneyline"], errors="coerce"),
        "source_game_id": raw["game_id"].astype(str),
    })
    g["game_id"] = [canonical_game_id(*r) for r in g[["season", "week", "away_team", "home_team"]].itertuples(index=False)]
    mismatch = g[g["game_id"] != g["source_game_id"]]
    if len(mismatch):
        warnings.append(f"{len(mismatch)} source game ids differ from canonical ids after team normalization "
                        f"(e.g. {mismatch['source_game_id'].iloc[0]} -> {mismatch['game_id'].iloc[0]}).")
    # Kickoff times in nfldata are US Eastern local clock time.
    local = pd.to_datetime(g["gameday"] + " " + g["gametime"], errors="coerce")
    g["kickoff_utc"] = local.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert("UTC")
    if g["kickoff_utc"].isna().any():
        warnings.append(f"{int(g['kickoff_utc'].isna().sum())} games have unparseable kickoff times.")
    g["completed"] = g["home_score"].notna() & g["away_score"].notna()
    g["margin"] = g["home_score"] - g["away_score"]
    g["home_win"] = np.where(g["completed"], np.where(g["margin"] > 0, 1.0, np.where(g["margin"] < 0, 0.0, np.nan)), np.nan)
    g["tie"] = g["completed"] & (g["margin"] == 0)
    g["market_p_home_novig"] = [no_vig_home_prob(h, a) for h, a in zip(g["home_moneyline"], g["away_moneyline"])]
    g["roof_type"] = stadium_roof_types(g)
    dups = find_duplicates(g)
    if len(dups):
        warnings.append(f"Dropped {len(dups) - dups['game_id'].nunique()} duplicate game rows.")
        g = g.drop_duplicates("game_id", keep="last")
    return g.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True), warnings


# --------------------------------------------------------------------------- play-by-play

PBP_COLUMNS = [
    "game_id", "season", "week", "posteam", "defteam", "play_type", "epa", "success",
    "pass", "rush", "qb_dropback", "sack", "interception", "fumble_lost", "yards_gained",
    "pass_touchdown", "rush_touchdown", "down", "third_down_converted", "third_down_failed",
    "yardline_100", "fixed_drive", "fixed_drive_result", "game_seconds_remaining",
    "score_differential", "qtr", "passer_player_id", "qb_epa", "two_point_attempt", "play_id",
]


def team_game_stats(pbp: pd.DataFrame) -> pd.DataFrame:
    """Aggregate offensive plays into one row per (game_id, team) of offensive stats."""
    p = pbp[[c for c in PBP_COLUMNS if c in pbp.columns]].copy()
    p = p[p["play_type"].isin(["pass", "run"]) & p["epa"].notna() & p["posteam"].notna()
          & (p["two_point_attempt"].fillna(0) == 0)]
    p["posteam"] = p["posteam"].map(normalize_team)
    for c in ("pass", "rush", "qb_dropback", "sack", "interception", "fumble_lost",
              "pass_touchdown", "rush_touchdown", "third_down_converted", "third_down_failed", "success"):
        p[c] = p[c].fillna(0).astype(float)
    p["yards_gained"] = p["yards_gained"].fillna(0)
    p["is_db"] = p["qb_dropback"]
    p["is_ru"] = ((p["rush"] == 1) & (p["qb_dropback"] == 0)).astype(float)
    p["early"] = p["down"].isin([1, 2]).astype(float)
    p["explosive"] = (((p["is_db"] == 1) & (p["yards_gained"] >= 20)) | ((p["is_ru"] == 1) & (p["yards_gained"] >= 10))).astype(float)
    p["turnover"] = p["interception"] + p["fumble_lost"]
    p = p.sort_values(["game_id", "play_id"])
    # seconds from this snap to the next snap of the same drive (clock runs down)
    gap = p.groupby(["game_id", "fixed_drive"])["game_seconds_remaining"].diff(-1)
    neutral = (p["score_differential"].abs() <= 7) & (p["qtr"] <= 3)
    p["neutral_gap"] = gap.where(neutral & gap.between(1, 60))

    def wmean(v, w):
        return (v * w).sum() / w.sum() if w.sum() > 0 else np.nan

    rows = []
    for (gid, team), d in p.groupby(["game_id", "posteam"], sort=False):
        third = d["third_down_converted"].sum() + d["third_down_failed"].sum()
        drives = d.groupby("fixed_drive").agg(minyl=("yardline_100", "min"), res=("fixed_drive_result", "first"))
        rz = drives[drives["minyl"] <= 20]
        rows.append({
            "game_id": gid, "team": team,
            "plays": len(d), "dropbacks": d["is_db"].sum(), "rushes": d["is_ru"].sum(),
            "pass_yds": d.loc[d["is_db"] == 1, "yards_gained"].sum(),
            "rush_yds": d.loc[d["is_ru"] == 1, "yards_gained"].sum(),
            "total_yds": d["yards_gained"].sum(),
            "pass_td": d["pass_touchdown"].sum(), "rush_td": d["rush_touchdown"].sum(),
            "turnovers": d["turnover"].sum(),
            "epa_pp": d["epa"].mean(), "sr": d["success"].mean(),
            "pass_epa": wmean(d["epa"], d["is_db"]), "rush_epa": wmean(d["epa"], d["is_ru"]),
            "pass_sr": wmean(d["success"], d["is_db"]), "rush_sr": wmean(d["success"], d["is_ru"]),
            "early_epa": wmean(d["epa"], d["early"]), "early_sr": wmean(d["success"], d["early"]),
            "third_conv": d["third_down_converted"].sum() / third if third else np.nan,
            "rz_td_rate": (rz["res"] == "Touchdown").mean() if len(rz) else np.nan,
            "explosive_rate": d["explosive"].mean(),
            "sack_rate": d["sack"].sum() / d["is_db"].sum() if d["is_db"].sum() else np.nan,
            "pass_rate": d["is_db"].mean(),
            "sec_per_play": d["neutral_gap"].mean(),
        })
    return pd.DataFrame(rows)


def qb_game_stats(pbp: pd.DataFrame) -> pd.DataFrame:
    """Per passer per game: dropbacks and summed QB EPA (for prior-efficiency features)."""
    p = pbp[(pbp["qb_dropback"] == 1) & pbp["qb_epa"].notna() & pbp["passer_player_id"].notna()
            & (pbp["play_type"].isin(["pass", "run"]))]
    out = (p.groupby(["game_id", "posteam", "passer_player_id"]).agg(qb_dropbacks=("qb_epa", "size"), qb_epa_sum=("qb_epa", "sum"))
           .reset_index().rename(columns={"passer_player_id": "qb_id", "posteam": "team"}))
    out["team"] = out["team"].map(normalize_team)
    return out


def stadium_roof_types(g: pd.DataFrame) -> pd.Series:
    """Static roof type per stadium (dome / retractable / outdoors), from every listed game.
    Game-day 'open'/'closed' values only reveal that a roof is retractable; the game-day
    state itself is not used because it is decided close to kickoff."""
    kinds = g.groupby("stadium_id")["roof"].agg(lambda r: set(r) - {""})
    def kind(stadium, roof):
        seen = kinds.get(stadium, set()) | ({roof} - {""})
        if seen & {"open", "closed"}:
            return "retractable"
        if "dome" in seen:
            return "dome"
        return "outdoors" if seen else "unknown"
    return pd.Series([kind(s, r) for s, r in zip(g["stadium_id"], g["roof"])], index=g.index)
