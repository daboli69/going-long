"""As-of (pregame-knowable) player inputs: usage shares, efficiency offsets, baseline B parameters.
Availability = that week's nflverse roster status ACT (game-day inactives are announced 90 min before kickoff)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import RAW_DIR
from .models import AIR_EDGES, RUSH_EDGES

K_BLEND = 4
TGT_PRIOR = {"WR": 0.04, "TE": 0.03, "RB": 0.02, "FB": 0.005}
CAR_PRIOR = {"RB": 0.08, "FB": 0.01, "QB": 0.05, "WR": 0.005}
TGT_GROUP = {"WR": "WR", "TE": "TE", "RB": "RB", "FB": "RB"}
CAR_GROUP = {"RB": "RB", "FB": "RB", "QB": "QB", "WR": "WR", "TE": "WR"}


def panel(p: pd.DataFrame, T: dict) -> pd.DataFrame:
    """One row per (season, week, team, player ACT on the roster) with that game's usage and stats (regulation only)."""
    from .models import state_index
    s = p[(p["qtr"] <= 4) & p["play_type"].isin(["pass", "run"]) & (p["two_point_attempt"] == 0) &
          (p["qb_kneel"] == 0) & (p["qb_spike"] == 0)].copy()
    tg = s[(s["play_type"] == "pass") & (s["sack"] == 0) & s["receiver_player_id"].notna()].copy()
    tg["ab"] = np.digitize(tg["air_yards"].fillna(0), AIR_EDGES)
    tg["resid"] = tg["complete_pass"] - T["catch_by_air"][tg["ab"]]
    rec = tg.groupby(["game_id", "posteam", "receiver_player_id"]).agg(
        targets=("play_id", "size"), rec=("complete_pass", "sum"), rec_yds=("receiving_yards", "sum"), resid=("resid", "sum"))
    for k in range(7):
        rec[f"ab{k}"] = tg.assign(x=tg["ab"] == k).groupby(["game_id", "posteam", "receiver_player_id"])["x"].sum()
    rec = rec.reset_index().rename(columns={"receiver_player_id": "pid"})
    ru = s[(s["play_type"] == "run") & s["rusher_player_id"].notna()].copy()
    ru["rb"] = np.digitize(ru["rushing_yards"].fillna(0), RUSH_EDGES)
    rus = ru.groupby(["game_id", "posteam", "rusher_player_id"]).agg(carries=("play_id", "size"), rush_yds=("rushing_yards", "sum"))
    for k in range(7):
        rus[f"rb{k}"] = ru.assign(x=ru["rb"] == k).groupby(["game_id", "posteam", "rusher_player_id"])["x"].sum()
    rus = rus.reset_index().rename(columns={"rusher_player_id": "pid"})
    db = s[s["play_type"] == "pass"].groupby(["game_id", "posteam", "passer_player_id"]).agg(
        dropbacks=("play_id", "size"), pass_yds=("passing_yards", "sum")).reset_index().rename(columns={"passer_player_id": "pid"})
    pg = rec.merge(rus, on=["game_id", "posteam", "pid"], how="outer").merge(db, on=["game_id", "posteam", "pid"], how="outer").fillna(0)
    team = s.groupby(["game_id", "posteam"]).agg(
        team_targets=("receiver_player_id", lambda x: x.notna().sum()), team_carries=("rusher_player_id", lambda x: x.notna().sum()))
    neu = s[s["down"].between(1, 3) & (s["score_differential"].abs() <= 10) & (s["game_seconds_remaining"] > 300)]
    pp = T["p_pass"][state_index(neu["down"], neu["ydstogo"], neu["yardline_100"], neu["score_differential"], neu["game_seconds_remaining"])]
    team["proe_sum"] = (neu["play_type"].eq("pass").astype(float) - pp).groupby([neu["game_id"], neu["posteam"]]).sum()
    team["neutral"] = neu.groupby(["game_id", "posteam"]).size()
    team = team.fillna(0).reset_index()
    gw = p.drop_duplicates("game_id")[["game_id", "season", "week"]]
    team = team.merge(gw, on="game_id")
    seasons = sorted(p["season"].unique())
    ros = pd.concat([pd.read_parquet(RAW_DIR / f"roster_weekly_{y}.parquet", columns=["season", "week", "team", "gsis_id", "status", "position"])
                     for y in seasons if (RAW_DIR / f"roster_weekly_{y}.parquet").exists()])
    ros = ros[ros["status"] == "ACT"].rename(columns={"gsis_id": "pid", "team": "posteam"})
    from ..ingest import normalize_team
    ros["posteam"] = ros["posteam"].map(normalize_team)
    team["posteam"] = team["posteam"].map(normalize_team)
    pg["posteam"] = pg["posteam"].map(normalize_team)
    out = ros.merge(team, on=["season", "week", "posteam"], how="inner").merge(pg, on=["game_id", "posteam", "pid"], how="left")
    num = [c for c in pg.columns if c not in ("game_id", "posteam", "pid")]
    out[num] = out[num].fillna(0)
    out["tshare"] = np.where(out["team_targets"] > 0, out["targets"] / out["team_targets"], 0)
    out["cshare"] = np.where(out["team_carries"] > 0, out["carries"] / out["team_carries"], 0)
    return out.drop_duplicates(["game_id", "pid"])


def _blend(cur_mean, n_cur, prev_mean):
    prev = np.where(np.isnan(prev_mean), cur_mean, prev_mean)
    out = (n_cur * np.nan_to_num(cur_mean) + K_BLEND * prev) / (n_cur + K_BLEND)
    return np.where(np.isnan(out), np.nan, out)


def asof(pan: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """Per-player as-of aggregates from season-1 (all) and season (weeks < week)."""
    cur = pan[(pan["season"] == season) & (pan["week"] < week)]
    prev = pan[pan["season"] == season - 1]
    agg = {"tshare": "mean", "cshare": "mean", "rec_yds": "mean", "rec": "mean", "rush_yds": "mean", "game_id": "size"}
    c = cur.groupby("pid").agg(agg).rename(columns={"game_id": "n"})
    pv = prev.groupby("pid").agg(agg).rename(columns={"game_id": "n"})
    a = c.join(pv, how="outer", lsuffix="_c", rsuffix="_p")
    a["n_c"] = a["n_c"].fillna(0)
    for k in ("tshare", "cshare", "rec_yds", "rec", "rush_yds"):
        a[k] = _blend(a[f"{k}_c"].to_numpy(), a["n_c"].to_numpy(), a[f"{k}_p"].to_numpy())
    both = pd.concat([cur, prev])
    sums = both.groupby("pid")[["targets", "resid", "carries"] + [f"ab{k}" for k in range(7)] + [f"rb{k}" for k in range(7)]].sum()
    a = a.join(sums)
    sd = both.groupby("pid")[["rec_yds", "rec", "rush_yds"]].std().add_suffix("_sd")
    a = a.join(sd)
    a["games_total"] = both.groupby("pid").size()
    qb = both[both["dropbacks"] >= 10].groupby("pid")["pass_yds"].agg(["mean", "std", "size"]).add_prefix("qb_")
    a = a.join(qb)
    for k, col in (("rec_yds", "rec_yds"), ("rec", "rec"), ("rush_yds", "rush_yds")):
        a[f"{k}_p85"] = both.groupby("pid")[col].quantile(0.85).where(a["games_total"] >= 6)
    a["pass_yds_p85"] = both[both["dropbacks"] >= 10].groupby("pid")["pass_yds"].quantile(0.85).where(a["qb_size"] >= 6)
    last_team = both.sort_values(["season", "week"]).groupby("pid")["posteam"].last()
    a["last_team"] = last_team
    a["position"] = both.sort_values(["season", "week"]).groupby("pid")["position"].last()
    a["cur_team"] = cur.sort_values("week").groupby("pid")["posteam"].last()
    return a


def team_inputs(a: pd.DataFrame, avail: pd.DataFrame, team: str, team_panel_cur: pd.DataFrame, team_panel_prev: pd.DataFrame,
                week: int, qb_pid: str):
    """Shares with within-position-group redistribution of missing regulars, efficiency offsets, PROE offset."""
    av = avail[["pid", "position"]].drop_duplicates("pid").set_index("pid")
    if qb_pid and qb_pid not in av.index:
        av.loc[qb_pid] = "QB"
    regulars = a[(a["cur_team"] == team) if week > 1 else (a["last_team"] == team)]
    res = {}
    for kind, prior, group, col in (("recv", TGT_PRIOR, TGT_GROUP, "tshare"), ("rush", CAR_PRIOR, CAR_GROUP, "cshare")):
        pos = av["position"].where(av["position"].isin(prior.keys()))
        cand = av[pos.notna()].copy()
        if kind == "rush" and qb_pid:
            cand = cand[(cand["position"] != "QB") | (cand.index == qb_pid)]
        cand["share"] = a[col].reindex(cand.index)
        cand["share"] = cand["share"].fillna(cand["position"].map(prior)).clip(lower=0)
        cand["grp"] = cand["position"].map(group)
        miss = regulars[~regulars.index.isin(cand.index)]
        for pid_, r in miss.iterrows():
            g = group.get(r["position"])
            if g is None:
                continue
            m = cand["grp"] == g
            if m.any() and cand.loc[m, "share"].sum() > 0 and not np.isnan(r[col]):
                cand.loc[m, "share"] += r[col] * cand.loc[m, "share"] / cand.loc[m, "share"].sum()
        cand = cand[cand["share"] > 0]
        cand["share"] /= cand["share"].sum()
        res[kind] = cand
    def proe(tp):
        return (tp["proe_sum"].sum() / tp["neutral"].sum()) if len(tp) and tp["neutral"].sum() > 0 else 0.0
    g = len(team_panel_cur)
    pr = (g * proe(team_panel_cur) + K_BLEND * proe(team_panel_prev)) / (g + K_BLEND)
    res["pass_off"] = float(np.clip(pr / 0.2475, -1, 1))
    return res


def efficiency(a: pd.DataFrame, pid: str):
    """Mixture weights/distributions and catch offset for a player (0 when no history)."""
    if pid not in a.index:
        return 0.0, np.full(7, 1 / 7), 0.0, 0.0, np.full(7, 1 / 7)
    r = a.loc[pid]
    nt = float(np.nan_to_num(r.get("targets", 0)))
    ab = np.array([np.nan_to_num(r.get(f"ab{k}", 0)) for k in range(7)], float)
    wr = min(0.7, nt / (nt + 20)) if nt > 0 else 0.0
    dr = ab / ab.sum() if ab.sum() > 0 else np.full(7, 1 / 7)
    coff = float(np.clip((np.nan_to_num(r.get("resid", 0)) / nt if nt else 0) * nt / (nt + 30) / (0.65 * 0.35), -0.8, 0.8))
    nc = float(np.nan_to_num(r.get("carries", 0)))
    rbv = np.array([np.nan_to_num(r.get(f"rb{k}", 0)) for k in range(7)], float)
    wu = min(0.6, nc / (nc + 40)) if nc > 0 else 0.0
    du = rbv / rbv.sum() if rbv.sum() > 0 else np.full(7, 1 / 7)
    return wr, dr, coff, wu, du
