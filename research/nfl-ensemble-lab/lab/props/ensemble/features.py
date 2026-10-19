"""Auditable player-game aggregates and strictly earlier-week rolling features.

Only the explicit ALLOWED_SEASONS may be read. 2023–25 player data is excluded
even when present beside these files. Contemporary weather/routes are excluded.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ...config import RAW_DIR
from ...ingest import normalize_team

ALLOWED_SEASONS = tuple(range(2015, 2023)) + (2026,)
PBP_COLS = ["game_id", "play_id", "season", "week", "season_type", "posteam", "defteam", "qtr", "play_type",
            "two_point_attempt", "qb_kneel", "qb_spike", "sack", "complete_pass", "passer_player_id",
            "receiver_player_id", "rusher_player_id", "passing_yards", "receiving_yards", "rushing_yards",
            "air_yards", "yards_after_catch", "yardline_100", "pass_touchdown", "rush_touchdown", "yards_gained"]
RAW_STATS = ["targets", "carries", "dropbacks", "pass_yds", "pass_tds", "rec", "rec_yds", "rush_yds", "off_td",
             "air_yards", "yac", "deep_targets", "explosives", "rz_targets", "gl_targets", "rz_carries", "gl_carries",
             "outside_rz_td", "long_td", "target_share", "carry_share", "air_share", "rz_target_share", "gl_target_share",
             "rz_carry_share", "gl_carry_share", "team_pass_td_share", "snap_share"]
FEATURES = ["hist_" + c for c in RAW_STATS] + ["hist_games", "adot", "yac_rate", "deep_target_rate",
            "outside_rz_td_rate", "explosive_rate", "long_td_rate", "is_qb", "is_rb", "is_wr", "is_te",
            "home", "rest", "dome", "ind_team_margin", "ind_total", "qb_quality", "qb_out", "backup_qb",
            "opp_position_yards", "opp_position_td", "opp_adjustment"]


def load_plays(seasons, prospective_week=None):
    seasons = tuple(int(s) for s in seasons)
    if any(s not in ALLOWED_SEASONS for s in seasons):
        raise ValueError("2023–25 player outcomes are forbidden for Phase 10")
    parts = []
    for season in seasons:
        p = pd.read_parquet(RAW_DIR / f"play_by_play_{season}.parquet", columns=PBP_COLS)
        if season == 2026:
            if prospective_week is None:
                raise ValueError("A prospective week cutoff is required")
            p = p[p["week"] < prospective_week]
        parts.append(p)
    return pd.concat(parts, ignore_index=True)


def aggregate(plays, rosters):
    """Postgame observations, used only after shifting to earlier weeks."""
    p = plays[(plays["season_type"] == "REG") & (plays["qtr"] <= 4) & plays["play_type"].isin(["pass", "run"])
              & (plays["two_point_attempt"].fillna(0) == 0) & (plays["qb_kneel"].fillna(0) == 0)
              & (plays["qb_spike"].fillna(0) == 0)].copy()
    p["posteam"] = p["posteam"].map(normalize_team)
    keys = ["game_id", "posteam", "pid"]
    chunks = []
    for kind, id_col in (("rec", "receiver_player_id"), ("rush", "rusher_player_id"), ("pass", "passer_player_id")):
        mask = p["play_type"].eq("run" if kind == "rush" else "pass") & p[id_col].notna()
        if kind == "rec":
            mask &= p["sack"].fillna(0).eq(0)
        s = p[mask].rename(columns={id_col: "pid"}).copy()
        rz, gl = s["yardline_100"].le(20), s["yardline_100"].le(5)
        if kind == "rec":
            s = s.assign(targets=1, rec=s["complete_pass"].fillna(0), rec_yds=s["receiving_yards"].fillna(0),
                         yac=s["yards_after_catch"].fillna(0), deep_targets=s["air_yards"].ge(20).astype(int),
                         explosives=s["receiving_yards"].ge(20).astype(int), rz_targets=rz.astype(int), gl_targets=gl.astype(int),
                         off_td=s["pass_touchdown"].fillna(0), outside_rz_td=(~rz & s["pass_touchdown"].eq(1)).astype(int),
                         long_td=(s["receiving_yards"].ge(40) & s["pass_touchdown"].eq(1)).astype(int))
            cols = ["targets", "rec", "rec_yds", "air_yards", "yac", "deep_targets", "explosives", "rz_targets", "gl_targets",
                    "off_td", "outside_rz_td", "long_td"]
        elif kind == "rush":
            s = s.assign(carries=1, rush_yds=s["rushing_yards"].fillna(0), explosives=s["rushing_yards"].ge(20).astype(int),
                         rz_carries=rz.astype(int), gl_carries=gl.astype(int), off_td=s["rush_touchdown"].fillna(0),
                         outside_rz_td=(~rz & s["rush_touchdown"].eq(1)).astype(int),
                         long_td=(s["rushing_yards"].ge(40) & s["rush_touchdown"].eq(1)).astype(int))
            cols = ["carries", "rush_yds", "explosives", "rz_carries", "gl_carries", "off_td", "outside_rz_td", "long_td"]
        else:
            s = s.assign(dropbacks=1, pass_yds=s["passing_yards"].fillna(0), pass_tds=s["pass_touchdown"].fillna(0))
            cols = ["dropbacks", "pass_yds", "pass_tds"]
        chunks.append(s.groupby(keys)[cols].sum())
    observed = pd.concat(chunks).groupby(level=keys).sum().reset_index()
    teams = p.groupby(["game_id", "posteam"]).agg(season=("season", "first"), week=("week", "first"),
                opponent=("defteam", "first"), team_pass_td=("pass_touchdown", "sum"), team_rush_td=("rush_touchdown", "sum"))
    # Roster status labels completed-game eligibility only. Never target-week starter/role features.
    roster = rosters[rosters["status"] == "ACT"].rename(columns={"team": "posteam", "gsis_id": "pid"}).copy()
    roster["posteam"] = roster["posteam"].map(normalize_team)
    out = roster.merge(teams.reset_index(), on=["season", "week", "posteam"], how="inner").merge(observed, on=keys, how="left")
    for c in set(RAW_STATS) - {"snap_share"}:
        if c not in out:
            out[c] = 0.0
    numeric = [c for c in RAW_STATS if c in out]
    out[numeric] = out[numeric].fillna(0)
    for value, share in (("targets", "target_share"), ("carries", "carry_share"), ("air_yards", "air_share"),
                         ("rz_targets", "rz_target_share"), ("gl_targets", "gl_target_share"),
                         ("rz_carries", "rz_carry_share"), ("gl_carries", "gl_carry_share")):
        den = out.groupby(["game_id", "posteam"])[value].transform("sum")
        out[share] = out[value] / den.where(den != 0)
        out[share] = out[share].fillna(0)
    den = out["team_pass_td"] + out["team_rush_td"]
    out["team_pass_td_share"] = (out["team_pass_td"] / den.where(den > 0)).fillna(0.5)
    out["snap_share"] = np.nan
    out["anytime_td"] = out["off_td"].ge(1).astype(int)
    return out.drop_duplicates(["game_id", "pid"]).sort_values(["season", "week", "game_id", "pid"])


def earlier_features(history, candidates):
    """Compute one decision week at a time, excluding ALL target-week observations.

    Last eight eligible historical player-games; no future-season player outcomes.
    Candidate identities/positions may be supplied only from a pregame snapshot or
    strictly earlier roster. Absent players keep missing history (explicit exclusion).
    """
    output = []
    for (season, week), target in candidates.groupby(["season", "week"], sort=True):
        h = history[(history["season"] < season) | ((history["season"] == season) & (history["week"] < week))]
        h = h.sort_values(["season", "week", "game_id"]).groupby("pid").tail(8)
        means = h.groupby("pid")[RAW_STATS].mean().add_prefix("hist_")
        means["hist_games"] = h.groupby("pid").size()
        means["history_last_week"] = h.groupby("pid")["week"].last()
        means["history_last_season"] = h.groupby("pid")["season"].last()
        target = target.merge(means, left_on="pid", right_index=True, how="left")
        # Opponent-v-position observations: prior games only, adjusted by the
        # prior league position mean. No current-game targets/outcomes enter.
        hp = h.assign(yards=h["rec_yds"] + h["rush_yds"] + h["pass_yds"])
        defpos = hp.groupby(["game_id", "opponent", "position"])[["yards", "off_td"]].sum().reset_index()
        defense = defpos.groupby(["opponent", "position"])[["yards", "off_td"]].mean()
        league = defpos.groupby("position")["yards"].mean()
        target = target.merge(defense.rename(columns={"yards": "opp_position_yards", "off_td": "opp_position_td"}),
                              left_on=["opponent", "position"], right_index=True, how="left")
        target["opp_adjustment"] = target["opp_position_yards"] / target["position"].map(league).replace(0, np.nan)
        output.append(target)
    out = pd.concat(output, ignore_index=True)
    for col, numerator, denominator in (("adot", "air_yards", "targets"), ("yac_rate", "yac", "rec"),
            ("deep_target_rate", "deep_targets", "targets"), ("outside_rz_td_rate", "outside_rz_td", None),
            ("explosive_rate", "explosives", None), ("long_td_rate", "long_td", None)):
        den = out["hist_" + denominator] if denominator else out["hist_targets"] + out["hist_carries"]
        out[col] = out["hist_" + numerator] / den.where(den > 0)
    for pos in ("QB", "RB", "WR", "TE"):
        out["is_" + pos.lower()] = out["position"].eq(pos).astype(int)
    for col in FEATURES:
        if col not in out:
            out[col] = np.nan
    return out


def eligible(frame, stat):
    """v1 share thresholds on prior usage; QB is projected from earlier dropbacks."""
    if stat in ("pass_yds", "pass_tds"):
        mask = frame["position"].eq("QB") & frame["projected_qb"].eq(frame["pid"])
    elif stat in ("rec", "rec_yds"):
        mask = frame["hist_target_share"].ge(.10)
    elif stat == "rush_yds":
        mask = frame["hist_carry_share"].ge(.20)
    else:
        mask = frame["hist_target_share"].ge(.10) | frame["hist_carry_share"].ge(.20)
    return mask & frame["hist_games"].notna()
