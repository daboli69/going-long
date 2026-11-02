"""V1 calibration and V2 prediction checks from docs/SNAPSIM_PREREG.md. Every 2026 game played, simulated with only earlier weeks."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import snapfit, snapgame, snapsim  # noqa: E402
import hashlib  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1000


def actual(week_max: int):
    p = pd.read_parquet(ROOT / "data/raw/play_by_play_2026.parquet", columns=["week", "season_type", "posteam", "defteam", "play_type", "penalty", "qb_dropback", "sack", "down", "qb_kneel", "qb_spike", "two_point_attempt", "penalty_team", "penalty_yards"])
    p = p[(p["season_type"] == "REG") & (p["week"] <= week_max)]
    sn = p[p["play_type"].isin(["pass", "run"]) & (p["penalty"] != 1) & (p["qb_kneel"] != 1) & (p["qb_spike"] != 1) & (p["two_point_attempt"] != 1)]
    pen = p[(p["penalty"] == 1) & p["play_type"].isin(["pass", "run", "no_play"]) & (p["penalty_yards"].fillna(0) > 0) & p["down"].notna()]
    teams = sn["posteam"].nunique()
    games = len(set(zip(p["week"], p["posteam"]))) / 1.0
    n_tg = sn.groupby(["week", "posteam"]).ngroups
    return {"snaps": len(sn) / n_tg, "dropbacks": sn["qb_dropback"].sum() / n_tg, "sacks": sn["sack"].sum() / n_tg, "penalties": len(pen) / n_tg,
            "fourth_go": ((sn["down"] == 4).sum()) / n_tg}


if __name__ == "__main__":
    g = pd.read_csv(ROOT / "data/raw/games.csv")
    g = g[(g["season"] == 2026) & (g["game_type"] == "REG") & g["result"].notna()].sort_values("week")
    inj_all = pd.read_parquet(ROOT / "data/raw/injuries_2026.parquet")
    rows = []
    cache = {}
    for r in g.itertuples():
        wk = int(r.week)
        if wk not in cache:
            P = snapfit.fit(wk)
            cache[wk] = (P, snapfit.load(wk), inj_all[inj_all["week"] == wk])
        P, p, inj = cache[wk]
        rng = np.random.default_rng(1)
        ven = snapgame.venue_effects(r.home_team, (int(r.away_rest), int(r.home_rest)))
        pools = [snapgame.build_pool(P, p, r.away_team, wk, None, N, rng, inj), snapgame.build_pool(P, p, r.home_team, wk, None, N, rng, inj)]
        crowd = ven["multiplier"] if r.home_team == ven["team"] else 1.0
        sim = snapsim.simulate(P, r.away_team, r.home_team, pools, n=N, seed=int(hashlib.sha256(r.game_id.encode()).hexdigest()[:8], 16), crowd_mult=crowd)
        sc = sim["score"]
        rows.append({"gid": r.game_id, "week": wk, "home_pts_sim": float(sc[:, 1].mean()), "away_pts_sim": float(sc[:, 0].mean()), "p_home_sim": float((sc[:, 1] > sc[:, 0]).mean() + 0.5 * (sc[:, 1] == sc[:, 0]).mean()),
                     "p_cover_sim": float((sc[:, 1] - sc[:, 0] > r.spread_line).mean()), "p_over_sim": float((sc.sum(1) > r.total_line).mean()), "home_pts": float(r.home_score), "away_pts": float(r.away_score),
                     "result": float(r.result), "spread_line": float(r.spread_line), "total": float(r.total), "total_line": float(r.total_line), "home_ml": float(r.home_moneyline), "away_ml": float(r.away_moneyline),
                     **{f"sim_{m}": float(sim["stats"][m].mean()) for m in ("snaps", "dropbacks", "sacks", "penalties", "fourth_go", "punts", "fg_att", "tds", "fgs", "ints")},
                     "sim_pass_yds": float((sim["qb"][0]["yds"].mean() + sim["qb"][1]["yds"].mean()) / 2), "sim_rush_yds": float((sim["acc"][0]["rushyd"].sum(1).mean() + sim["acc"][1]["rushyd"].sum(1).mean()) / 2),
                     "sim_comp": float((sim["qb"][0]["comp"].mean() + sim["qb"][1]["comp"].mean()) / 2), "sim_att": float((sim["qb"][0]["att"].mean() + sim["qb"][1]["att"].mean()) / 2)})
        print(r.game_id, round(rows[-1]["home_pts_sim"], 1), round(rows[-1]["away_pts_sim"], 1), flush=True)
    d = pd.DataFrame(rows)
    act = actual(int(g["week"].max()))
    pts_act = (d["home_pts"].mean() + d["away_pts"].mean()) / 2
    v1 = {"games": int(len(d)), "points_per_team": {"sim": float((d["home_pts_sim"].mean() + d["away_pts_sim"].mean()) / 2), "actual": float(pts_act)}}
    for m in ("snaps", "dropbacks", "sacks", "penalties", "fourth_go"):
        v1[m + "_per_team"] = {"sim": float(d["sim_" + m].mean() / 1.0), "actual": float(act[m])}
    v1["pass_rate"] = {"sim": float(d["sim_dropbacks"].mean() / d["sim_snaps"].mean()), "actual": float(act["dropbacks"] / act["snaps"])}
    for k, vv in v1.items():
        if isinstance(vv, dict) and "sim" in vv:
            vv["ratio"] = vv["sim"] / vv["actual"] if vv["actual"] else None
            vv["within_5pct"] = bool(abs(vv["ratio"] - 1) <= 0.05) if k != "points_per_team" else bool(abs(vv["sim"] - vv["actual"]) <= 1.0)
    v1["calibrated"] = all(vv["within_5pct"] for vv in v1.values() if isinstance(vv, dict) and "within_5pct" in vv)
    w = d[d["week"] >= 4].copy()
    ph = lambda ml: -ml / (100 - ml) if ml < 0 else 100 / (100 + ml)
    pm = w["home_ml"].map(ph) / (w["home_ml"].map(ph) + w["away_ml"].map(ph))
    y = (w["result"] > 0).astype(float)
    ll = lambda p_, y_: float(-(y_ * np.log(np.clip(p_, 0.01, 0.99)) + (1 - y_) * np.log(1 - np.clip(p_, 0.01, 0.99))).mean())
    cov = (w["result"] > w["spread_line"]).astype(float)
    ov = (w["total"] > w["total_line"]).astype(float)
    v2 = {"games": int(len(w)), "win_log_loss_sim": ll(w["p_home_sim"], y), "win_log_loss_market": ll(pm, y), "win_log_loss_coin": ll(np.full(len(w), 0.5), y),
          "cover_brier_sim": float(((w["p_cover_sim"] - cov) ** 2).mean()), "over_brier_sim": float(((w["p_over_sim"] - ov) ** 2).mean()), "brier_coin": 0.25,
          "mean_abs_total_error_sim": float(((w["home_pts_sim"] + w["away_pts_sim"]) - w["total"]).abs().mean()), "mean_abs_total_error_line": float((w["total_line"] - w["total"]).abs().mean()),
          "mean_abs_margin_error_sim": float((((w["home_pts_sim"] - w["away_pts_sim"]) - w["result"]).abs()).mean()), "mean_abs_margin_error_line": float((w["spread_line"] - w["result"]).abs().mean()),
          "sims_per_game": N}
    dg = pd.read_parquet(ROOT / "data/raw/play_by_play_2026.parquet", columns=["week", "season_type", "posteam", "play_type", "penalty", "pass_touchdown", "rush_touchdown", "yards_gained", "complete_pass", "pass_attempt", "sack", "interception", "rush_attempt", "qb_scramble", "field_goal_result", "punt_attempt", "qb_kneel", "qb_spike", "two_point_attempt"])
    dg = dg[(dg["season_type"] == "REG") & (dg["penalty"] != 1) & (dg["qb_kneel"] != 1) & (dg["qb_spike"] != 1) & (dg["two_point_attempt"] != 1)]
    ntg = dg[dg["play_type"].isin(["pass", "run"])].groupby(["week", "posteam"]).ngroups
    att_ = dg[(dg["pass_attempt"] == 1)]
    diag = {"punts": {"sim": float(d["sim_punts"].mean()), "actual": float((dg["punt_attempt"] == 1).sum() / ntg)}, "fg_att": {"sim": float(d["sim_fg_att"].mean()), "actual": float((dg["play_type"] == "field_goal").sum() / ntg)},
            "off_tds": {"sim": float(d["sim_tds"].mean()), "actual": float(((dg["pass_touchdown"] == 1).sum() + (dg["rush_touchdown"] == 1).sum()) / ntg)},
            "pass_yds": {"sim": float(d["sim_pass_yds"].mean()), "actual": float(att_.loc[att_["complete_pass"] == 1, "yards_gained"].sum() / ntg)},
            "rush_yds": {"sim": float(d["sim_rush_yds"].mean()), "actual": float(dg.loc[(dg["rush_attempt"] == 1) & (dg["qb_scramble"] != 1) | (dg["qb_scramble"] == 1), "yards_gained"].sum() / ntg)},
            "completions": {"sim": float(d["sim_comp"].mean()), "actual": float(att_["complete_pass"].sum() / ntg)}, "attempts": {"sim": float(d["sim_att"].mean()), "actual": float(len(att_) / ntg)},
            "ints": {"sim": float(d["sim_ints"].mean()), "actual": float(dg["interception"].sum() / ntg)}}
    out = {"v1": v1, "v2": v2, "diagnostics": diag}
    (ROOT / "docs" / "snapsim_validation.json").write_text(json.dumps(out, indent=1))
    d.to_parquet(ROOT / "data" / "snapsim_validation_games.parquet") if (ROOT / "data").exists() else None
    print(json.dumps(out, indent=1))
