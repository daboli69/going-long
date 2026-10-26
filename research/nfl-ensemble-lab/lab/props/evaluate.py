"""Walk-forward evaluation of the props simulator vs baseline B (docs/PROPS_PREREGISTRATION.md).

  python -m lab.props.evaluate dev            2022 development season (repeatable)
  python -m lab.props.evaluate eval           2023-2025, the single pre-registered look (refuses to overwrite)
  python -m lab.props.evaluate analyze        metrics/tests from saved player-game rows
"""
from __future__ import annotations

import json
import sys
import time
import zlib

import numpy as np
import pandas as pd
from scipy import stats

from ..config import ARTIFACTS_DIR, RAW_DIR
from ..ingest import normalize_team
from . import models as M
from . import players as PL
from . import sim as S

OUT = ARTIFACTS_DIR / "props"
DEV, EVAL = (2022,), (2023, 2024, 2025)
N_SIMS = 10_000
STATS = ("pass_yds", "rush_yds", "rec_yds", "rec")


def crps_samples(x: np.ndarray, y: float) -> float:
    x = np.sort(x)
    n = len(x)
    i = np.arange(1, n + 1)
    return float(np.mean(np.abs(x - y)) - np.sum((2 * i - n - 1) * x) / n ** 2)


def crps_normal(mu, sd, y):
    z = (y - mu) / sd
    return float(sd * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi)))


def _team_ppg(games, season, week, team):
    g = games[(games["home_team"] == team) | (games["away_team"] == team)]
    pts = np.where(g["home_team"] == team, g["home_score"], g["away_score"])
    g = g.assign(pts=pts)
    cur = g[(g["season"] == season) & (g["week"] < week)]["pts"]
    prev = g[g["season"] == season - 1]["pts"]
    pm = prev.mean() if len(prev) else 22.0
    return (len(cur) * (cur.mean() if len(cur) else 0) + PL.K_BLEND * pm) / (len(cur) + PL.K_BLEND)


def _pos_sd(pan, season):
    pv = pan[pan["season"] == season - 1]
    return {"rec_yds": float(pv.loc[pv["targets"] >= 3, "rec_yds"].std()), "rush_yds": float(pv.loc[pv["carries"] >= 8, "rush_yds"].std()),
            "pass_yds": float(pv.loc[pv["dropbacks"] >= 10, "pass_yds"].std())}


def run_season(season: int, n_sims: int = N_SIMS, log=print, limit=None) -> pd.DataFrame:
    T = M.fit(range(2016, season))
    cs, rz = S.calibrate_clock(T)
    log(f"{season}: clock scale {cs:.3f}, red-zone boost {rz:.3f} (targets {T['real_scrimmage_per_team']:.1f} plays, "
        f"{T['real_points_per_team']:.1f} points per team)")
    p = M.load_pbp([season - 1, season])
    pan = PL.panel(p, T)
    games = pd.read_csv(RAW_DIR / "games.csv")
    for c in ("home_team", "away_team"):
        games[c] = games[c].map(normalize_team)
    games = games[(games["game_type"] == "REG")]
    target = games[(games["season"] == season) & games["home_score"].notna()].dropna(subset=["spread_line", "total_line"])
    if limit:
        target = target.head(limit)
    possd = _pos_sd(pan, season)
    ps = p[p["season"] == season]
    first_qb = ps[ps["play_type"] == "pass"].dropna(subset=["passer_player_id"]).groupby(["game_id", "posteam"])["passer_player_id"].first()
    rows, corr_rows, team_rows = [], [], []
    cache_week, a = None, None
    t0 = time.time()
    for gi, g in enumerate(target.sort_values(["week", "game_id"]).itertuples(index=False)):
        if g.week != cache_week:
            a, cache_week = PL.asof(pan, season, g.week), g.week
        sides = [g.home_team, g.away_team]
        ros = pan[(pan["season"] == season) & (pan["week"] == g.week)]
        teams, cols, info = [], {}, []
        for t in sides:
            qb = first_qb.get((g.game_id, t))
            tp = pan[pan["posteam"] == t]
            ti = PL.team_inputs(a, ros[ros["posteam"] == t], t, tp[(tp["season"] == season) & (tp["week"] < g.week)].drop_duplicates("game_id"),
                                tp[tp["season"] == season - 1].drop_duplicates("game_id"), g.week, qb)
            for pid in list(ti["recv"].index) + list(ti["rush"].index) + ([qb] if qb else []):
                cols.setdefault(pid, len(cols))
            info.append((t, qb, ti))
        P = len(cols)
        pl = {"w_recv": np.zeros(P), "dist_recv": np.full((P, 7), 1 / 7), "coff": np.zeros(P), "w_rush": np.zeros(P),
              "dist_rush": np.full((P, 7), 1 / 7)}
        for pid, c in cols.items():
            wr, dr, co, wu, du = PL.efficiency(a, pid)
            pl["w_recv"][c], pl["dist_recv"][c], pl["coff"][c], pl["w_rush"][c], pl["dist_rush"][c] = wr, dr, co, wu, du
        for t, qb, ti in info:
            teams.append({"pass_off": ti["pass_off"], "qb_col": cols.get(qb, 0),
                          "recv_cols": np.array([cols[x] for x in ti["recv"].index]), "recv_cum": np.cumsum(ti["recv"]["share"].to_numpy()),
                          "rush_cols": np.array([cols[x] for x in ti["rush"].index]), "rush_cum": np.cumsum(ti["rush"]["share"].to_numpy())})
        imp = [(g.total_line + g.spread_line) / 2, (g.total_line - g.spread_line) / 2]
        rng = np.random.default_rng(zlib.crc32(g.game_id.encode()))
        e, cal_pts = S.calibrate(T, teams, pl, imp, rng)
        r = S.simulate(T, teams, pl, n_sims, e, rng)
        act = pan[pan["game_id"] == g.game_id].set_index("pid")
        team_rows.append({"game_id": g.game_id, "season": season, "week": g.week, "imp_home": imp[0], "imp_away": imp[1],
                          "sim_home": float(r["points"][:, 0].mean()), "sim_away": float(r["points"][:, 1].mean()),
                          "sim_p_home": float((r["points"][:, 0] > r["points"][:, 1]).mean() + 0.5 * (r["points"][:, 0] == r["points"][:, 1]).mean()),
                          "act_home": g.home_score, "act_away": g.away_score, "e_home": e[0], "e_away": e[1]})
        for si, (t, qb, ti) in enumerate(info):
            ratio = float(np.clip(imp[si] / max(_team_ppg(games, season, g.week, t), 1.0), 0.6, 1.6))
            elig = []
            if qb:
                elig.append((qb, "pass_yds"))
            elig += [(pid, k) for pid in ti["recv"].index[ti["recv"]["share"] >= 0.10] for k in ("rec_yds", "rec")]
            elig += [(pid, "rush_yds") for pid in ti["rush"].index[(ti["rush"]["share"] >= 0.20)]]
            for pid, k in elig:
                if pid not in act.index or pid not in a.index:
                    continue
                y = float(act.loc[pid, k])
                x = r["stats"][k][:, cols[pid]]
                ar = a.loc[pid]
                if k == "pass_yds":
                    mu, sd0, n0 = ar.get("qb_mean"), ar.get("qb_std"), ar.get("qb_size")
                    p85 = ar.get("pass_yds_p85")
                else:
                    mu, sd0, n0 = ar.get(k), ar.get(f"{k}_sd"), ar.get("games_total")
                    p85 = ar.get(f"{k}_p85")
                if mu is None or np.isnan(mu):
                    continue
                mu = float(mu) * ratio
                n0 = float(np.nan_to_num(n0))
                rec = {"game_id": g.game_id, "season": season, "week": g.week, "team": t, "pid": pid, "stat": k, "actual": y,
                       "sim_mean": float(x.mean()), "base_mean": mu, "crps_sim": crps_samples(x, y)}
                if k == "rec":
                    lam = max(mu, 0.05)
                    xb = rng.poisson(lam, n_sims).astype(float)
                    rec["crps_base"] = crps_samples(xb, y)
                    med = stats.poisson.median(lam)
                    b_lo80, b_hi80 = stats.poisson.ppf([0.1, 0.9], lam)
                    b_lo50, b_hi50 = stats.poisson.ppf([0.25, 0.75], lam)
                    b_cdf = lambda v: stats.poisson.cdf(np.floor(v), lam)
                    rec["pit_base"] = float(stats.poisson.cdf(y - 1, lam) + 0.5 * stats.poisson.pmf(y, lam))
                else:
                    sd = (n0 * float(np.nan_to_num(sd0, nan=possd[k])) + PL.K_BLEND * possd[k]) / (n0 + PL.K_BLEND)
                    sd = max(sd, 1.0)
                    rec["crps_base"] = crps_normal(mu, sd, y)
                    med = mu
                    b_lo80, b_hi80 = stats.norm.ppf([0.1, 0.9], mu, sd)
                    b_lo50, b_hi50 = stats.norm.ppf([0.25, 0.75], mu, sd)
                    b_cdf = lambda v, mu=mu, sd=sd: stats.norm.cdf(v, mu, sd)
                    rec["pit_base"] = float(stats.norm.cdf(y, mu, sd))
                line = np.floor(med) + 0.5
                q = np.quantile(x, [0.1, 0.25, 0.75, 0.9])
                rec |= {"line": line, "over": float(y > line), "p_over_sim": float((x > line).mean()), "p_over_base": float(1 - b_cdf(line)),
                        "in80_sim": float(q[0] <= y <= q[3]), "in50_sim": float(q[1] <= y <= q[2]),
                        "in80_base": float(b_lo80 <= y <= b_hi80), "in50_base": float(b_lo50 <= y <= b_hi50),
                        "pit_sim": float((x < y).mean() + 0.5 * (x == y).mean())}
                if p85 is not None and not np.isnan(p85):
                    rec |= {"tail_line": float(p85), "tail": float(y > p85), "p_tail_sim": float((x > p85).mean()),
                            "p_tail_base": float(1 - b_cdf(p85))}
                rows.append(rec)
            # correlation: QB passing yards vs the top-share receiver
            if qb and len(ti["recv"]):
                wr1 = ti["recv"]["share"].idxmax()
                xq, xw = r["stats"]["pass_yds"][:, cols[qb]], r["stats"]["rec_yds"][:, cols[wr1]]
                corr_rows.append({"game_id": g.game_id, "team": t, "sim_corr": float(np.corrcoef(xq, xw)[0, 1]),
                                  "qb_act": float(act.loc[qb, "pass_yds"]) if qb in act.index else np.nan,
                                  "wr_act": float(act.loc[wr1, "rec_yds"]) if wr1 in act.index else np.nan,
                                  "qb_sim": float(xq.mean()), "wr_sim": float(xw.mean())})
        if gi % 20 == 0:
            log(f"{season} game {gi + 1}/{len(target)} {g.game_id} e={np.round(e, 2)} cal={np.round(cal_pts, 1)} imp={np.round(imp, 1)} "
                f"{time.time() - t0:.0f}s")
    return pd.DataFrame(rows), pd.DataFrame(corr_rows), pd.DataFrame(team_rows)


def boot_test(df, n=2000, seed=7):
    """Game-cluster bootstrap of mean(crps_sim - crps_base). One-sided p for H1: mean < 0 (recentred under H0)."""
    d = df.assign(diff=df["crps_sim"] - df["crps_base"]).groupby("game_id")["diff"].agg(["sum", "size"])
    obs = d["sum"].sum() / d["size"].sum()
    idx = np.random.default_rng(seed).integers(0, len(d), (n, len(d)))
    bm = d["sum"].to_numpy()[idx].sum(1) / d["size"].to_numpy()[idx].sum(1)
    p = float((np.sum((bm - obs) <= obs) + 1) / (n + 1))
    return float(obs), p, [float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))]


def analyze(tag: str) -> dict:
    d = OUT / tag
    df = pd.read_parquet(d / "player_games.parquet")
    cr = pd.read_parquet(d / "correlation.parquet")
    tm = pd.read_parquet(d / "team_points.parquet")
    obs, p, ci = boot_test(df)
    res = {"tag": tag, "player_game_stats": int(len(df)), "games": int(df["game_id"].nunique()),
           "primary": {"mean_crps_sim": float(df["crps_sim"].mean()), "mean_crps_base": float(df["crps_base"].mean()),
                       "mean_diff": obs, "diff_ci95": ci, "p_one_sided": p, "passes": bool(obs < 0 and p < 0.05)}}
    by = {}
    for k, s in df.groupby("stat"):
        t = s.dropna(subset=["tail"]) if "tail" in s else s.iloc[:0]
        ll = lambda pr, y: float(-np.mean(y * np.log(np.clip(pr, 1e-4, 1 - 1e-4)) + (1 - y) * np.log(np.clip(1 - pr, 1e-4, 1 - 1e-4))))
        by[k] = {"n": int(len(s)), "crps_sim": float(s["crps_sim"].mean()), "crps_base": float(s["crps_base"].mean()),
                 "cov80_sim": float(s["in80_sim"].mean()), "cov80_base": float(s["in80_base"].mean()),
                 "cov50_sim": float(s["in50_sim"].mean()), "cov50_base": float(s["in50_base"].mean()),
                 "ou_logloss_sim": ll(s["p_over_sim"], s["over"]), "ou_logloss_base": ll(s["p_over_base"], s["over"]),
                 "tail_n": int(len(t)), "tail_rate": float(t["tail"].mean()) if len(t) else None,
                 "tail_brier_sim": float(np.mean((t["p_tail_sim"] - t["tail"]) ** 2)) if len(t) else None,
                 "tail_brier_base": float(np.mean((t["p_tail_base"] - t["tail"]) ** 2)) if len(t) else None,
                 "tail_pred_sim": float(t["p_tail_sim"].mean()) if len(t) else None, "tail_pred_base": float(t["p_tail_base"].mean()) if len(t) else None,
                 "pit_hist_sim": np.histogram(s["pit_sim"], bins=10, range=(0, 1))[0].tolist(),
                 "pit_hist_base": np.histogram(s["pit_base"], bins=10, range=(0, 1))[0].tolist(),
                 "mean_sim": float(s["sim_mean"].mean()), "mean_base": float(s["base_mean"].mean()), "mean_actual": float(s["actual"].mean())}
    res["by_stat"] = by
    c = cr.dropna()
    res["correlation_qb_wr1"] = {"sim_mean_within_game": float(c["sim_corr"].mean()),
                                 "actual_residual_corr": float(np.corrcoef(c["qb_act"] - c["qb_sim"], c["wr_act"] - c["wr_sim"])[0, 1]),
                                 "team_games": int(len(c))}
    res["team_points"] = {"implied_mean": float(tm[["imp_home", "imp_away"]].to_numpy().mean()),
                          "sim_mean": float(tm[["sim_home", "sim_away"]].to_numpy().mean()),
                          "actual_mean": float(tm[["act_home", "act_away"]].to_numpy().mean()),
                          "max_abs_calibration_gap": float(np.max(np.abs(tm[["sim_home", "sim_away"]].to_numpy() - tm[["imp_home", "imp_away"]].to_numpy())))}
    (d / "analysis.json").write_text(json.dumps(res, indent=2, default=str))
    return res


def run(tag: str, seasons, n_sims=N_SIMS, limit=None, log=print):
    d = OUT / tag
    if tag == "eval" and (d / "player_games.parquet").exists():
        raise FileExistsError("The 2023-25 evaluation look has already been taken; it is never re-scored.")
    d.mkdir(parents=True, exist_ok=True)
    parts = [run_season(s, n_sims, log, limit) for s in seasons]
    for i, name in enumerate(("player_games", "correlation", "team_points")):
        pd.concat([x[i] for x in parts]).to_parquet(d / f"{name}.parquet", index=False)
    return analyze(tag)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if cmd == "analyze":
        print(json.dumps(analyze(sys.argv[2] if len(sys.argv) > 2 else "dev"), indent=2))
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        with open(OUT / f"{cmd}_run.log", "a", encoding="utf-8") as fh:
            def log(m):
                fh.write(f"{pd.Timestamp.now(tz='UTC').isoformat()} {m}\n")
                fh.flush()
            res = run(cmd, DEV if cmd == "dev" else EVAL, log=log)
        print(json.dumps(res["primary"], indent=2))
