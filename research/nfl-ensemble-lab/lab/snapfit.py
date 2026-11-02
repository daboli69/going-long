"""Parameters for the snap simulator, fitted from play-by-play (docs/SNAPSIM_PREREG.md). 2025 counts at half weight, 2026 before the game week at full weight."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SEASON = 2026
PRIOR_WEIGHT = 0.5
COLS = ["game_id", "season", "week", "posteam", "defteam", "home_team", "away_team", "play_id", "drive", "qtr", "down", "ydstogo", "yardline_100", "game_seconds_remaining", "half_seconds_remaining",
        "score_differential", "play_type", "pass_attempt", "rush_attempt", "complete_pass", "yards_gained", "sack", "interception", "fumble_lost", "qb_hit", "qb_scramble", "qb_dropback",
        "qb_kneel", "qb_spike", "touchdown", "field_goal_result", "kick_distance", "return_yards", "penalty", "penalty_type", "penalty_team", "penalty_yards", "run_gap", "run_location", "timeout",
        "two_point_attempt", "passer_player_id", "receiver_player_id", "rusher_player_id", "kickoff_attempt", "punt_attempt", "return_touchdown", "drive_start_transition", "air_yards"]
PRE_OFF = {"False Start"}   # only false starts take the crowd multiplier; other own-team penalties fall in the live class
PRE_DEF = {"Defensive Offside", "Neutral Zone Infraction", "Encroachment", "Defensive Delay of Game", "Defensive Too Many Men on Field"}
GAPS = ["left_end", "left_tackle", "left_guard", "middle", "right_guard", "right_tackle", "right_end"]


def shr(total, n, prior, m):
    return (total + m * prior) / (n + m)


def feats(down, ytg, yl, sd, gsr):
    return np.column_stack([down == 2, down == 3, down == 4, np.log(np.clip(ytg, 1, 30)), yl / 100.0, np.clip(sd, -21, 21) / 14.0, gsr / 3600.0, (gsr < 300) & (sd < 0), (gsr < 300) & (sd > 0)]).astype(float)


def feats4(down, ytg, yl, sd, gsr):
    return np.column_stack([feats(down, ytg, yl, sd, gsr), (yl / 100.0) ** 2, yl <= 30, yl <= 45]).astype(float)


def hurry_state(sd, gsr, hsr, qtr):
    late = (gsr <= 300) | ((qtr == 2) & (hsr <= 120))
    return np.where(late & (sd < 0), 1, np.where((gsr <= 300) & (sd > 0), 2, 0))


@dataclass
class Params:
    league: dict = field(default_factory=dict)
    off: dict = field(default_factory=dict)
    deff: dict = field(default_factory=dict)
    pass_coef: tuple = None
    fourth_coef: tuple = None
    fg_coef: tuple = None
    yards: dict = field(default_factory=dict)
    elapsed: dict = field(default_factory=dict)
    ko_start: np.ndarray = None
    players: dict = field(default_factory=dict)


def load(before_week: int, season: int = SEASON) -> pd.DataFrame:
    fr = []
    for s, w in ((season - 1, PRIOR_WEIGHT), (season, 1.0)):
        f = RAW / f"play_by_play_{s}.parquet"
        if not f.exists():
            continue
        p = pd.read_parquet(f, columns=COLS + ["season_type"])
        p = p[p["season_type"] == "REG"]
        if s == season:
            p = p[p["week"] < before_week]
        fr.append(p.assign(w=w, yr=s))
    p = pd.concat(fr, ignore_index=True)
    return p.sort_values(["yr", "game_id", "play_id"]).reset_index(drop=True)


def _newton(y, p, group, m):
    """Per group offset on the logit scale from a league model's probabilities, shrunk toward zero."""
    g = pd.DataFrame({"g": group, "r": y - p, "v": p * (1 - p)}).groupby("g").agg(r=("r", "sum"), v=("v", "sum"))
    return (g["r"] / (g["v"] + m)).to_dict()


def fit(before_week: int, season: int = SEASON) -> Params:
    P = Params()
    p = load(before_week, season)
    p["w"] = p["w"].astype(float)
    snap = p[p["play_type"].isin(["pass", "run", "no_play"]) & p["down"].notna() & (p["qb_kneel"] != 1) & (p["qb_spike"] != 1) & (p["two_point_attempt"] != 1)].copy()
    sc = snap[snap["play_type"].isin(["pass", "run"]) & (snap["penalty"] != 1)].copy()
    sc["db"] = (sc["qb_dropback"] == 1).astype(float)
    L = P.league
    # ---- pass or run
    X = feats(sc["down"].to_numpy(), sc["ydstogo"].to_numpy(), sc["yardline_100"].to_numpy(), sc["score_differential"].fillna(0).to_numpy(), sc["game_seconds_remaining"].to_numpy())
    mp = LogisticRegression(C=10, max_iter=500).fit(X, sc["db"], sample_weight=sc["w"])
    P.pass_coef = (mp.coef_[0], float(mp.intercept_[0]))
    pp = mp.predict_proba(X)[:, 1]
    P.off["pass_delta"] = _newton(sc["db"].to_numpy() * sc["w"].to_numpy(), pp * sc["w"].to_numpy(), sc["posteam"].to_numpy(), 40.0)
    # ---- fourth down: go, field goal, punt
    f4 = p[(p["down"] == 4) & (p["qb_kneel"] != 1) & (p["qb_spike"] != 1) & p["play_type"].isin(["pass", "run", "punt", "field_goal"]) & (p["penalty"] != 1)].copy()
    f4["cls"] = np.where(f4["play_type"].isin(["pass", "run"]), 0, np.where(f4["play_type"] == "field_goal", 1, 2))
    X4 = feats4(f4["down"].to_numpy(), f4["ydstogo"].to_numpy(), f4["yardline_100"].to_numpy(), f4["score_differential"].fillna(0).to_numpy(), f4["game_seconds_remaining"].to_numpy())
    m4 = LogisticRegression(C=10, max_iter=1000).fit(X4, f4["cls"], sample_weight=f4["w"])
    P.fourth_coef = (m4.coef_, m4.intercept_)
    pg = m4.predict_proba(X4)[:, 0]
    P.off["go_delta"] = _newton((f4["cls"] == 0).astype(float).to_numpy() * f4["w"].to_numpy(), pg * f4["w"].to_numpy(), f4["posteam"].to_numpy(), 15.0)
    fg = f4[f4["play_type"] == "field_goal"].dropna(subset=["kick_distance"])
    mf = LogisticRegression(C=10, max_iter=500).fit(fg[["kick_distance"]].to_numpy(), (fg["field_goal_result"] == "made").astype(int), sample_weight=fg["w"])
    P.fg_coef = (float(mf.coef_[0][0]), float(mf.intercept_[0]))
    # ---- dropback outcomes and pressure
    db = sc[sc["db"] == 1].copy()
    db["pr"] = ((db["qb_hit"] == 1) | (db["sack"] == 1)).astype(float)
    db["scr"] = (db["qb_scramble"] == 1).astype(float)
    att = db[(db["sack"] != 1) & (db["scr"] != 1)]
    W = lambda d: d["w"].to_numpy()
    L["pr"] = float(np.average(db["pr"], weights=W(db)))
    L["pr_sack"] = float(np.average(db.loc[db["pr"] == 1, "sack"], weights=W(db[db["pr"] == 1])))
    L["scr"] = float(np.average(db["scr"], weights=W(db)))
    for k, d in (("pr1", att[att["qb_hit"] == 1]), ("pr0", att[att["qb_hit"] != 1])):
        L["comp_" + k] = float(np.average(d["complete_pass"], weights=W(d)))
        L["int_" + k] = float(np.average(d["interception"], weights=W(d)))
    ftn = []
    for s in (season - 1, season):
        f = RAW / f"ftn_{s}.parquet"
        if f.exists():
            ftn.append(pd.read_parquet(f, columns=["nflverse_game_id", "nflverse_play_id", "n_pass_rushers"]))
    if ftn:
        ft = pd.concat(ftn).dropna().rename(columns={"nflverse_game_id": "game_id"})
        ft["nflverse_play_id"] = ft["nflverse_play_id"].astype(float)
        db = db.assign(nflverse_play_id=db["play_id"].astype(float)).merge(ft.drop_duplicates(["game_id", "nflverse_play_id"]), on=["game_id", "nflverse_play_id"], how="left")
        db["blitz"] = (db["n_pass_rushers"] >= 5).astype(float).where(db["n_pass_rushers"].notna())
    else:
        db["blitz"] = np.nan
    bl = db.dropna(subset=["blitz"])
    L["blitz"] = float(np.average(bl["blitz"], weights=W(bl))) if len(bl) else 0.3
    L["pr_b1"] = float(np.average(bl.loc[bl["blitz"] == 1, "pr"], weights=W(bl[bl["blitz"] == 1]))) if len(bl) else L["pr"]
    L["pr_b0"] = float(np.average(bl.loc[bl["blitz"] == 0, "pr"], weights=W(bl[bl["blitz"] == 0]))) if len(bl) else L["pr"]
    # team factors: pressure (allowed by offense, generated by defense), blitz rate, completion, yards, interception
    pr_all = L["pr"]
    for side, key in (("off", "posteam"), ("deff", "defteam")):
        tgt = getattr(P, side)
        g = db.groupby(key).apply(lambda d: pd.Series({"n": d["w"].sum(), "x": (d["pr"] * d["w"]).sum()}), include_groups=False)
        tgt["pr"] = ((g["x"] + 120 * pr_all) / (g["n"] + 120) / pr_all).to_dict()
        gc = att.groupby(key).apply(lambda d: pd.Series({"n": d["w"].sum(), "yds": (d["w"] * d["yards_gained"] * d["complete_pass"]).sum(), "c": (d["w"] * d["complete_pass"]).sum(), "i": (d["w"] * d["interception"]).sum()}), include_groups=False)
        base = np.where(att["qb_hit"] == 1, L["comp_pr1"], L["comp_pr0"])
        tgt["comp"] = _newton(att["complete_pass"].to_numpy() * W(att), base * W(att), att[key].to_numpy(), 40.0)
        comp = att[att["complete_pass"] == 1]
        L["ypc"] = float(np.average(comp["yards_gained"], weights=W(comp)))
        gy = comp.groupby(key).apply(lambda d: pd.Series({"n": d["w"].sum(), "m": np.average(d["yards_gained"], weights=d["w"])}), include_groups=False)
        tgt["ypc"] = {k: float((r.m - L["ypc"]) * r.n / (r.n + 60.0)) for k, r in gy.iterrows()}
        li = (att["interception"] * W(att)).sum() / W(att).sum()
        L["int"] = float(li)
        tgt["int"] = ((gc["i"] + 300 * li) / (gc["n"] + 300) / li).to_dict()
    if len(bl):
        gb = bl.groupby("defteam").apply(lambda d: pd.Series({"n": d["w"].sum(), "x": (d["blitz"] * d["w"]).sum()}), include_groups=False)
        P.deff["blitz"] = ((gb["x"] + 60 * L["blitz"]) / (gb["n"] + 60)).to_dict()
    P.yards["comp"] = comp["yards_gained"].to_numpy(float)
    P.yards["scramble"] = db.loc[db["scr"] == 1, "yards_gained"].to_numpy(float)
    P.yards["sack"] = db.loc[db["sack"] == 1, "yards_gained"].to_numpy(float)
    # ---- runs
    rn = sc[(sc["db"] == 0) & (sc["rush_attempt"] == 1)].copy()
    loc = rn["run_location"].fillna("middle")
    gap = rn["run_gap"].fillna("")
    rn["cat"] = np.where(loc == "middle", "middle", loc + "_" + np.where(gap == "", "guard", gap))
    rn.loc[~rn["cat"].isin(GAPS), "cat"] = "middle"
    L["ypr"] = float(np.average(rn["yards_gained"], weights=W(rn)))
    L["fum_run"] = float(np.average(rn["fumble_lost"].fillna(0), weights=W(rn)))
    L["fum_pass"] = float(np.average(att["fumble_lost"].fillna(0), weights=W(att)))
    L["fum_sack"] = float(np.average(db.loc[db["sack"] == 1, "fumble_lost"].fillna(0), weights=W(db[db["sack"] == 1]))) if (db["sack"] == 1).any() else 0.03
    for k, d in rn.groupby("cat"):
        P.yards["run_" + k] = d["yards_gained"].to_numpy(float)
    P.league["gap_mix"] = (rn.groupby("cat")["w"].sum() / rn["w"].sum()).reindex(GAPS).fillna(0).to_dict()
    for side, key in (("off", "posteam"), ("deff", "defteam")):
        tgt = getattr(P, side)
        gm = rn.groupby([key, "cat"])["w"].sum().unstack(fill_value=0).reindex(columns=GAPS, fill_value=0)
        mix = (gm.add(60 * pd.Series(L["gap_mix"]), axis=1)).div(gm.sum(axis=1) + 60, axis=0)
        tgt["gap_mix"] = {t: mix.loc[t].to_numpy() for t in mix.index}
        gy = rn.groupby(key).apply(lambda d: pd.Series({"n": d["w"].sum(), "m": np.average(d["yards_gained"], weights=d["w"])}), include_groups=False)
        tgt["ypr"] = {k: float((r.m - L["ypr"]) * r.n / (r.n + (60.0 if side == "off" else 100.0))) for k, r in gy.iterrows()}
        gf = rn.groupby(key).apply(lambda d: pd.Series({"n": d["w"].sum(), "x": (d["fumble_lost"].fillna(0) * d["w"]).sum()}), include_groups=False)
        tgt["fum"] = ((gf["x"] + 300 * L["fum_run"]) / (gf["n"] + 300) / max(L["fum_run"], 1e-6)).to_dict()
    # ---- penalties per scrimmage snap
    pen = snap[snap["penalty"] == 1].copy()
    ptype = pen["penalty_type"].fillna("")
    own = pen["penalty_team"] == pen["posteam"]
    pen["cls"] = np.where(own & ptype.isin(PRE_OFF), "pre_off", np.where(~own & ptype.isin(PRE_DEF), "pre_def", np.where(own, "live_off", "live_def")))
    pen = pen[pen["penalty_yards"].fillna(0) > 0]
    n_snap = snap.assign(c=1.0)
    for side, key, classes in (("off", "posteam", ("pre_off", "live_off")), ("deff", "defteam", ("pre_def", "live_def"))):
        tgt = getattr(P, side)
        ns = (n_snap["w"]).groupby(n_snap[key]).sum()
        for c in classes:
            x = (pen.loc[pen["cls"] == c, "w"]).groupby(pen.loc[pen["cls"] == c, key]).sum().reindex(ns.index).fillna(0)
            lg = float(x.sum() / ns.sum())
            L["rate_" + c] = lg
            tgt[c] = ((x + 400 * lg) / (ns + 400)).to_dict()
    for c in ("pre_off", "pre_def", "live_off", "live_def"):
        L["pyds_" + c] = float(pen.loc[pen["cls"] == c, "penalty_yards"].mean()) if (pen["cls"] == c).any() else 5.0
    # ---- clock: seconds to the next snap-type row, by category and state
    allr = p[p["play_type"].isin(["pass", "run", "punt", "field_goal", "kickoff", "no_play", "extra_point"]) & (p["timeout"].fillna(0) != 1)].copy()
    allr["half"] = (allr["qtr"] > 2).astype(int)
    nxt = allr.groupby(["yr", "game_id", "half"])["game_seconds_remaining"].shift(-1)
    allr["el"] = (allr["game_seconds_remaining"] - nxt).clip(0, 60)
    sd = allr["score_differential"].fillna(0).to_numpy()
    allr["hs"] = hurry_state(sd, allr["game_seconds_remaining"].to_numpy(), allr["half_seconds_remaining"].to_numpy(), allr["qtr"].to_numpy())
    cat = np.select([allr["kickoff_attempt"] == 1, allr["punt_attempt"] == 1, allr["play_type"] == "field_goal", allr["play_type"] == "no_play", allr["touchdown"] == 1, allr["sack"] == 1, (allr["play_type"] == "pass") & (allr["complete_pass"] == 1),
                    allr["play_type"] == "pass", allr["play_type"] == "run"], ["ko", "punt", "fg", "pen", "td", "sack", "comp", "inc", "run"], "other")
    allr["cat"] = cat
    ok = allr.dropna(subset=["el"])
    for (c, h), d in ok.groupby(["cat", "hs"]):
        P.elapsed[(c, int(h))] = d["el"].to_numpy(float)
    P.league["el_norm"] = float(ok.loc[(ok["hs"] == 0) & ok["cat"].isin(["run", "comp", "inc"]), "el"].mean())
    nn = ok[(ok["hs"] == 0) & ok["cat"].isin(["run", "comp", "inc"])]
    gp = nn.groupby("posteam").apply(lambda d: pd.Series({"n": d["w"].sum(), "m": np.average(d["el"], weights=d["w"])}), include_groups=False)
    P.off["pace"] = {k: float(shr(r.m * r.n, r.n, P.league["el_norm"], 200.0) / P.league["el_norm"]) for k, r in gp.iterrows()}
    ks = p[(p["drive_start_transition"].isin(["KICKOFF"])) & (p["down"] == 1)].drop_duplicates(["yr", "game_id", "drive"])
    P.ko_start = ks["yardline_100"].dropna().to_numpy(float)
    L["punt_net"] = None
    pn = p[(p["punt_attempt"] == 1) & p["kick_distance"].notna()]
    P.yards["punt"] = (pn["kick_distance"] - pn["return_yards"].fillna(0)).to_numpy(float)
    L["xp"] = 0.95
    rt = p["return_touchdown"].fillna(0)
    L["ret_td_int"] = float(np.average(rt[p["interception"] == 1], weights=p.loc[p["interception"] == 1, "w"]))
    L["ret_td_fum"] = float(np.average(rt[p["fumble_lost"] == 1], weights=p.loc[p["fumble_lost"] == 1, "w"]))
    L["ret_td_punt"] = float(np.average(rt[p["punt_attempt"] == 1], weights=p.loc[p["punt_attempt"] == 1, "w"]))
    L["ret_td_ko"] = float(np.average(rt[p["kickoff_attempt"] == 1], weights=p.loc[p["kickoff_attempt"] == 1, "w"]))
    L["games"] = int(p["game_id"].nunique())
    return P
