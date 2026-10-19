"""Situational sub-models, fitted walk-forward and compiled to lookup tables for vectorised simulation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder

from ..config import RAW_DIR

AIR_EDGES = [0, 5, 10, 15, 20, 30]          # 7 bins
YAC_EDGES = [1, 3, 6, 10, 20]               # 6 bins
RUSH_EDGES = [0, 2, 4, 7, 11, 20]           # 7 bins
N_STATE = (3, 7, 7, 7, 4)                   # down, to-go, yardline, score diff, time
PBP_COLS = ["game_id", "play_id", "season", "week", "season_type", "posteam", "defteam", "home_team", "away_team", "down", "ydstogo",
            "yardline_100", "score_differential", "qtr", "game_seconds_remaining", "half_seconds_remaining", "play_type", "sack",
            "air_yards", "yards_after_catch", "complete_pass", "interception", "fumble_lost", "rushing_yards", "receiving_yards",
            "passing_yards", "yards_gained", "passer_player_id", "receiver_player_id", "rusher_player_id", "qb_scramble",
            "field_goal_result", "kick_distance", "extra_point_result", "two_point_attempt", "qb_kneel", "qb_spike",
            "penalty", "penalty_team", "penalty_yards", "first_down_penalty"]


def b_down(d):
    return np.clip(np.asarray(d, float), 1, 3).astype(int) - 1


def b_togo(t):
    return np.digitize(t, [2, 3, 5, 8, 11, 16])


def b_yl(y):
    return np.digitize(y, [6, 11, 21, 41, 61, 81])


def b_sd(d):
    return np.digitize(d, [-14, -7, 0, 1, 8, 15])


def b_time(sec):
    sec = np.asarray(sec, float)
    q = np.clip(1 + (3600 - sec) // 900, 1, 4)
    half = np.where(sec > 1800, sec - 1800, sec)
    return np.where(q == 4, np.where(sec <= 300, 3, 2), np.where((q == 2) & (half <= 120), 1, 0)).astype(int)


def state_index(down, togo, yl, sd, sec):
    a, b, c, d, e = b_down(down), b_togo(togo), b_yl(yl), b_sd(sd), b_time(sec)
    return (((a * 7 + b) * 7 + c) * 7 + d) * 4 + e


def _grid():
    g = np.stack(np.meshgrid(*[np.arange(n) for n in N_STATE], indexing="ij"), -1).reshape(-1, 5)
    return g                                     # row order matches state_index


def load_pbp(seasons) -> pd.DataFrame:
    out = []
    for s in seasons:
        f = (RAW_DIR / "history" if s <= 2014 else RAW_DIR) / f"play_by_play_{s}.parquet"
        p = pd.read_parquet(f, columns=PBP_COLS)
        out.append(p[p["season_type"] == "REG"])
    p = pd.concat(out, ignore_index=True).sort_values(["game_id", "play_id"])
    for c in ("qb_kneel", "qb_spike", "sack", "complete_pass", "interception", "fumble_lost", "qb_scramble", "two_point_attempt",
              "penalty", "first_down_penalty"):
        p[c] = p[c].fillna(0)
    return p


def _state_feats(p):
    return np.c_[b_down(p["down"]), b_togo(p["ydstogo"]), b_yl(p["yardline_100"]), b_sd(p["score_differential"]),
                 b_time(p["game_seconds_remaining"])]


def _fit_table(X, y, grid, C=1.0):
    enc = OneHotEncoder(categories=[np.arange(n) for n in grid.max(0) + 1], handle_unknown="ignore")
    m = LogisticRegression(C=C, max_iter=3000)
    m.fit(enc.fit_transform(X), y)
    pr = m.predict_proba(enc.transform(grid))
    out = np.zeros((len(grid), int(np.max(y)) + 1))
    out[:, m.classes_.astype(int)] = pr
    return out


def _empirical_by(keys, values, n_keys):
    return [np.asarray(values[keys == k], float) for k in range(n_keys)]


def recency_resample_games(p, season_weights, seed=20261019):
    """Importance sample WHOLE games, preserving every within-game play/clock pair."""
    games = p[["game_id", "season"]].drop_duplicates("game_id")
    weights = games["season"].map(season_weights).to_numpy(float)
    if not np.isfinite(weights).all() or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError("Invalid structural season weights")
    selection = np.random.default_rng(seed).choice(len(games), len(games), replace=True, p=weights / weights.sum())
    copies = games.iloc[selection][["game_id"]].copy()
    copies["_copy"] = np.arange(len(copies))
    result = p.merge(copies, on="game_id", how="inner")
    result["game_id"] = result["game_id"].astype(str) + "__phase10_" + result["_copy"].astype(str)
    return result.drop(columns="_copy").sort_values(["game_id", "play_id"])


def fit(train_seasons, kick_season=None, cutoff_week=None, season_weights=None) -> dict:
    """All sub-models from REG-season plays of train_seasons (strictly earlier than any evaluated season)."""
    p = load_pbp(train_seasons)
    if cutoff_week is not None:
        p = p[(p["season"] < max(train_seasons)) | (p["week"] <= cutoff_week)]
    if season_weights is not None:
        # Optional shadow-only importance resampling for empirical tables that
        # cannot accept likelihood weights. Default v1 takes neither branch.
        p = recency_resample_games(p, season_weights)
    p = p[(p["qb_kneel"] == 0) & (p["qb_spike"] == 0)]
    scrim = p[p["play_type"].isin(["pass", "run"]) & p["down"].notna() & (p["two_point_attempt"] == 0)]
    G = _grid()
    T = {"grid_size": len(G)}
    # pre-snap / no-play penalties (DraftKings flow: a penalty ends the play, field position moves, replay or first down)
    snaps = p[p["down"].notna() & p["play_type"].isin(["pass", "run", "no_play"]) & (p["two_point_attempt"] == 0)]
    pen = snaps[(snaps["play_type"] == "no_play") & (snaps["penalty"] == 1) & snaps["penalty_yards"].notna()]
    T["pen_rate"] = float(len(pen) / len(snaps))
    T["pen_gain"] = np.where(pen["penalty_team"] == pen["posteam"], -pen["penalty_yards"], pen["penalty_yards"]).astype(float)
    T["pen_fd"] = pen["first_down_penalty"].to_numpy(bool)
    T["p_pass"] = _fit_table(_state_feats(scrim), (scrim["play_type"] == "pass").astype(int).to_numpy(), G)[:, 1]
    dbk = scrim[scrim["play_type"] == "pass"]
    T["p_sack"] = _fit_table(_state_feats(dbk), dbk["sack"].astype(int).to_numpy(), G)[:, 1]
    att = dbk[(dbk["sack"] == 0) & dbk["air_yards"].notna()]
    air_bin = np.digitize(att["air_yards"], AIR_EDGES)
    T["air"] = _fit_table(_state_feats(att), air_bin, G)
    outc = np.where(att["interception"] == 1, 2, np.where(att["complete_pass"] == 1, 0, 1))
    g2 = np.stack(np.meshgrid(np.arange(7), np.arange(7), np.arange(3), indexing="ij"), -1).reshape(-1, 3)
    X2 = np.c_[air_bin, b_yl(att["yardline_100"]), b_down(att["down"])]
    T["outcome"] = _fit_table(X2, outc, g2)                      # index (air*7 + yl)*3 + down
    comp = att[att["complete_pass"] == 1]
    cb = np.digitize(comp["air_yards"], AIR_EDGES)
    yac = comp["yards_after_catch"].fillna(0).clip(lower=0)
    g3 = np.stack(np.meshgrid(np.arange(7), np.arange(7), indexing="ij"), -1).reshape(-1, 2)
    T["yac"] = _fit_table(np.c_[cb, b_yl(comp["yardline_100"])], np.digitize(yac, YAC_EDGES), g3)   # index air*7 + yl
    runs = scrim[scrim["play_type"] == "run"]
    T["rush"] = _fit_table(_state_feats(runs), np.digitize(runs["rushing_yards"].fillna(runs["yards_gained"]), RUSH_EDGES), G)
    T["air_vals"] = _empirical_by(air_bin, att["air_yards"].to_numpy(), 7)
    T["yac_vals"] = _empirical_by(np.digitize(yac, YAC_EDGES), yac.to_numpy(), 6)
    rv = runs["rushing_yards"].fillna(runs["yards_gained"]).to_numpy()
    T["rush_vals"] = _empirical_by(np.digitize(rv, RUSH_EDGES), rv, 7)
    # red zone: exact-yardline empirical gains (goal-line truncation makes coarse bins undercount touchdowns)
    T["rz_rush"] = {y: runs.loc[runs["yardline_100"] == y, "yards_gained"].to_numpy(float) for y in range(1, 21)}
    T["rz_pass"] = {y: comp.loc[comp["yardline_100"] == y, "yards_gained"].to_numpy(float) for y in range(1, 21)}
    T["real_yds_per_comp"] = float(comp["yards_gained"].mean())           # v2 fix 1(a) targets (training seasons only)
    T["real_yds_per_carry"] = float(np.nanmean(rv))
    T["sack_vals"] = dbk.loc[dbk["sack"] == 1, "yards_gained"].fillna(-7).to_numpy(float)
    T["fum_comp"] = float(comp["fumble_lost"].mean())
    T["fum_run"] = float(runs["fumble_lost"].mean())
    T["fum_sack"] = float(dbk.loc[dbk["sack"] == 1, "fumble_lost"].mean())
    T["catch_by_air"] = np.array([((outc == 0) & (air_bin == k)).sum() / max(1, (air_bin == k).sum()) for k in range(7)])
    # 4th down: go / punt / fg
    f4 = p[(p["down"] == 4) & p["play_type"].isin(["pass", "run", "punt", "field_goal"])]
    cls = np.where(f4["play_type"] == "punt", 1, np.where(f4["play_type"] == "field_goal", 2, 0))
    g4 = np.stack(np.meshgrid(np.arange(7), np.arange(7), np.arange(7), np.arange(4), indexing="ij"), -1).reshape(-1, 4)
    T["fourth"] = _fit_table(np.c_[b_togo(f4["ydstogo"]), b_yl(f4["yardline_100"]), b_sd(f4["score_differential"]),
                                   b_time(f4["game_seconds_remaining"])], cls, g4)   # ((togo*7+yl)*7+sd)*4+time
    fg = p[p["play_type"] == "field_goal"].dropna(subset=["kick_distance"])
    mfg = LogisticRegression(max_iter=1000).fit(fg[["kick_distance"]].to_numpy(), (fg["field_goal_result"] == "made").astype(int))
    T["fg_coef"] = (float(mfg.intercept_[0]), float(mfg.coef_[0][0]))
    xp = p[p["extra_point_result"].notna()]
    T["pat"] = float((xp["extra_point_result"] == "good").mean())
    # next-possession starts and clock, from consecutive plays
    q = p[p["play_type"].isin(["pass", "run", "punt", "field_goal", "no_play", "kickoff", "extra_point", "qb_kneel", "qb_spike"])]
    q = q[["game_id", "posteam", "yardline_100", "play_type", "game_seconds_remaining", "qtr", "half_seconds_remaining",
           "complete_pass", "sack", "season"]].copy()          # snaps only: timeout / end-of-quarter rows would shorten clock samples
    q["n_pos"], q["n_yl"] = q.groupby("game_id")["posteam"].shift(-1), q.groupby("game_id")["yardline_100"].shift(-1)
    q["n_sec"], q["n_qtr"] = q.groupby("game_id")["game_seconds_remaining"].shift(-1), q.groupby("game_id")["qtr"].shift(-1)
    ks = kick_season or max(train_seasons)
    ko = q[(q["play_type"] == "kickoff") & (q["season"] == ks)].dropna(subset=["n_yl"])
    T["kick_start"] = ko["n_yl"].clip(1, 99).to_numpy(float)
    pu = q[(q["play_type"] == "punt") & (q["n_pos"] != q["posteam"])].dropna(subset=["n_yl"])
    T["punt_start"] = _empirical_by(b_yl(pu["yardline_100"]), pu["n_yl"].clip(1, 99).to_numpy(), 7)
    same_half = ((q["qtr"] <= 2) == (q["n_qtr"] <= 2)) & q["n_sec"].notna()
    dt = (q["game_seconds_remaining"] - q["n_sec"]).where(same_half).clip(0, 60)
    hurry = q["qtr"].isin([2, 4]) & (q["half_seconds_remaining"] <= 120)
    klass = np.where(q["play_type"] == "pass", np.where((q["complete_pass"] == 1) | (q["sack"] == 1), 1, 0),
                     np.where(q["play_type"] == "run", 1, 2))
    reg = p[p["qtr"] <= 4]
    T["real_scrimmage_per_team"] = float(len(reg[reg["play_type"].isin(["pass", "run"]) & (reg["two_point_attempt"] == 0)]) /
                                         (reg["game_id"].nunique() * 2))
    T["clock_scale"] = 1.0
    T["rz_boost"] = 0.0
    g = pd.read_csv(RAW_DIR / "games.csv")
    g = g[g["season"].isin(list(train_seasons)) & (g["game_type"] == "REG") & g["home_score"].notna()]
    if cutoff_week is not None:
        g = g[(g["season"] < max(train_seasons)) | (g["week"] <= cutoff_week)]
    if season_weights is None:
        T["real_points_per_team"] = float(np.r_[g["home_score"], g["away_score"]].mean())
    else:
        T["real_points_per_team"] = float(np.average((g["home_score"] + g["away_score"]) / 2,
                                                      weights=g["season"].map(season_weights)))
    T["sigma_e"], T["kappa"] = 0.15, 30.0
    T["clock"] = {(k, h): dt[(klass == k) & (hurry == h) & dt.notna()].to_numpy(float) for k in range(3) for h in (False, True)}
    return T
