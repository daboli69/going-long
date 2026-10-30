"""Market-anchored props analysis, one look (docs/PROPS_MARKET_ANCHORED_PREREGISTRATION.md, commit 4909f1ba).

Walk-forward per-stat correction p = sigmoid(logit m + b (logit q - logit m)), b in [0,1], vs market, simulator and the
existing stack; placebo; coherence; cost. Writes reports/props_market/results.json. History is reused (descriptive).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab import homewin_eval as ev  # noqa: E402
from lab.config import CACHE_DIR, LAB_ROOT  # noqa: E402

CACHE = CACHE_DIR / "props_kalshi"
OUT = LAB_ROOT / "reports" / "props_market"
MIN_TRAIN, LAMBDA, ALPHA3, PERMS, SEED = 500, 10.0, 0.05 / 3, 200, 0
FEE_RATE = 0.07


def lg(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sig(x):
    return 1 / (1 + np.exp(-x))


def fit_b(m, q, y) -> float:
    a, d = lg(m), lg(q) - lg(m)

    def loss(b):
        p = np.clip(sig(a + b * d), 1e-9, 1 - 1e-9)
        return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).sum() + LAMBDA * b * b)
    return float(minimize_scalar(loss, bounds=(0.0, 1.0), method="bounded").x)


def walk_forward(T: pd.DataFrame, qcol: str = "p_K") -> pd.DataFrame:
    """Rows scored only where their stat has >= MIN_TRAIN earlier thresholds. Returns T with fitted-model columns."""
    T = T.sort_values(["season", "week"]).reset_index(drop=True)
    wk = list(T[["season", "week"]].drop_duplicates().itertuples(index=False, name=None))
    p_corr, p_stack, b_used, ok = (np.full(len(T), np.nan) for _ in range(4))
    for s, w in wk:
        now = (T["season"] == s) & (T["week"] == w)
        before = (T["season"] < s) | ((T["season"] == s) & (T["week"] < w))
        for stat in T["stat"].unique():
            cur = now & (T["stat"] == stat)
            tr = before & (T["stat"] == stat)
            if not cur.any() or tr.sum() < MIN_TRAIN:
                continue
            b = fit_b(T.loc[tr, "p_market90"], T.loc[tr, qcol], T.loc[tr, "y_home_win"].to_numpy(float))
            m, q = T.loc[cur, "p_market90"].to_numpy(), T.loc[cur, qcol].to_numpy()
            p_corr[cur.to_numpy()] = sig(lg(m) + b * (lg(q) - lg(m)))
            b_used[cur.to_numpy()] = b
            ok[cur.to_numpy()] = 1
        trall = before & (T["stat"].notna())
        if trall.sum() >= MIN_TRAIN:
            lr = LogisticRegression(C=1e6, max_iter=1000).fit(
                np.column_stack([lg(T.loc[trall, "p_market90"]), lg(T.loc[trall, qcol])]), T.loc[trall, "y_home_win"].astype(int))
            cur = now.to_numpy()
            p_stack[cur] = lr.predict_proba(np.column_stack([lg(T.loc[cur, "p_market90"]), lg(T.loc[cur, qcol])]))[:, 1]
    T = T.assign(p_corr=p_corr, p_stack=p_stack, b=b_used)
    return T[ok == 1].copy()


def ladders(S: pd.DataFrame, cols: dict) -> pd.DataFrame:
    y = S["y_home_win"].to_numpy(float)
    g = S.assign(**{f"c_{k}": (S[v].to_numpy() - y) ** 2 for k, v in cols.items()})
    agg = {"season": ("season", "first"), "week": ("week", "first")} | {f"c_{k}": (f"c_{k}", "sum") for k in cols}
    return g.groupby(["gid", "pid", "stat"]).agg(**agg).reset_index()


def paired(df: pd.DataFrame, a: str, b: str, alpha: float, cluster: str = "week") -> dict:
    d = (df[a] - df[b]).to_numpy(float)
    cl = (df["season"].astype(str) + "_" + df["week"].astype(str)).to_numpy() if cluster == "week" else df["gid"].to_numpy()
    return {"n": int(len(d)), "mean_a": float(df[a].mean()), "mean_b": float(df[b].mean()), "delta": float(d.mean()),
            "ci": ev.cluster_boot(d, cl, alpha), "ci_level": 1 - alpha}


def main():
    T0 = pd.read_parquet(CACHE / "scored_thresholds.parquet")
    S = walk_forward(T0)
    y = S["y_home_win"].to_numpy(float)
    S = S.assign(**{f"ll_{k}": -(y * np.log(np.clip(S[v], 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - S[v], 1e-6, 1)))
                    for k, v in {"mkt": "p_market90", "sim": "p_K", "stack": "p_stack", "corr": "p_corr"}.items()})
    L = ladders(S, {"mkt": "p_market90", "sim": "p_K", "stack": "p_stack", "corr": "p_corr"})
    res = {"prereg": "4909f1ba", "label": "reused history, descriptive; only prospective freezes can pass; nothing promoted",
           "scored": {"ladders": int(len(L)), "thresholds": int(len(S)), "weeks": int(L[["season", "week"]].drop_duplicates().shape[0]),
                      "by_stat": L["stat"].value_counts().to_dict(),
                      "b_by_stat_last_week": S.sort_values(["season", "week"]).groupby("stat")["b"].last().round(3).to_dict(),
                      "b_range": [float(S["b"].min()), float(S["b"].max())]},
           "mean_ladder_crps": {k: float(L[f"c_{k}"].mean()) for k in ("mkt", "sim", "stack", "corr")},
           "mean_logscore": {k: float(S[f"ll_{k}"].mean()) for k in ("mkt", "sim", "stack", "corr")}}
    sesoi = 0.01 * float(L["c_mkt"].mean())
    res["sesoi_crps"] = sesoi
    M = {"M1_corr_vs_market": paired(L, "c_corr", "c_mkt", ALPHA3), "M2_corr_vs_simulator": paired(L, "c_corr", "c_sim", ALPHA3),
         "M3_corr_vs_stack": paired(L, "c_corr", "c_stack", ALPHA3)}
    for k, v in M.items():
        v["improves"] = bool(v["ci"][1] < 0)
        v["material"] = bool(v["improves"] and v["delta"] <= -sesoi)
    M["M1_corr_vs_market"]["game_cluster_ci_sensitivity"] = paired(L.assign(season=L["season"]), "c_corr", "c_mkt", ALPHA3, "game")["ci"]
    res["M"] = M
    Lg = {"L1_corr_vs_market": paired(S, "ll_corr", "ll_mkt", ALPHA3), "L2_corr_vs_simulator": paired(S, "ll_corr", "ll_sim", ALPHA3),
          "L3_corr_vs_stack": paired(S, "ll_corr", "ll_stack", ALPHA3)}
    for v in Lg.values():
        v["improves"] = bool(v["ci"][1] < 0)
    res["L"] = Lg
    by = {}
    for stat, g in L.groupby("stat"):
        by[stat] = {"ladders": int(len(g)), "mkt": float(g["c_mkt"].mean()), "corr": float(g["c_corr"].mean()), "sim": float(g["c_sim"].mean())}
    res["by_stat"] = by

    # placebo: shuffle simulator probabilities across players within (game, stat, threshold) groups
    rng = np.random.default_rng(SEED)
    key = T0.groupby(["gid", "stat", "k"]).ngroup().to_numpy()
    shufflable = (T0.groupby(["gid", "stat", "k"])["p_K"].transform("size") >= 2).to_numpy()
    n = len(T0)
    pk = T0["p_K"].to_numpy()
    by_pos = np.lexsort((np.arange(n), key))                      # rows sorted by group, original order inside
    deltas = []
    for i in range(PERMS):
        by_rand = np.lexsort((rng.random(n), key))                # same groups, random order inside
        newp = np.empty(n)
        newp[by_pos] = pk[by_rand]                                # position-wise swap stays inside each group
        P = T0.assign(p_K=newp)
        Sp = walk_forward(P)
        Lp = ladders(Sp, {"mkt": "p_market90", "corr": "p_corr"})
        deltas.append(float(Lp["c_corr"].mean() - Lp["c_mkt"].mean()))
    real = M["M1_corr_vs_market"]["delta"]
    d = np.array(deltas)
    res["placebo"] = {"permutations": PERMS, "shufflable_thresholds_share": float(shufflable.mean()), "real_delta": real,
                      "placebo_delta_mean": float(d.mean()), "placebo_delta_p05": float(np.quantile(d, 0.05)),
                      "permutation_p": float((1 + (d <= real).sum()) / (1 + PERMS)),
                      "credible": bool(real < np.quantile(d, 0.05))}

    # coherence (descriptive)
    ex = T0.groupby(["gid", "pid", "stat"]).agg(season=("season", "first"), week=("week", "first"),
                                                 s_sim=("p_K", "sum"), s_mkt=("p_market90", "sum")).reset_index()
    ex["d"] = ex["s_sim"] - ex["s_mkt"]
    res["coherence"] = {"exceedance_sum_simulator_minus_market": {
        st: {"ladders": int(len(g)), "mean": float(g["d"].mean()),
             "ci95": ev.cluster_boot(g["d"].to_numpy(), (g["season"].astype(str) + "_" + g["week"].astype(str)).to_numpy(), 0.05)}
        for st, g in ex.groupby("stat")}}
    rep = pd.concat([pd.read_parquet(p) for p in sorted((CACHE / "replay").glob("*.parquet"))], ignore_index=True)
    k2 = rep[(rep["arm"] == "K") & (rep["version"] == "v2")]
    ry = k2[k2["stat"] == "rec_yds"].groupby(["gid", "team"])["mean"].sum()
    py = k2[k2["stat"] == "pass_yds"].groupby(["gid", "team"])["mean"].sum()
    ratio = (ry / py).dropna()
    res["coherence"]["pass_yard_identity"] = {
        "team_games": int(len(ratio)), "ratio_receiving_sum_over_passing_mean_quartiles": [float(x) for x in ratio.quantile([.25, .5, .75])],
        "note": "eligible receivers are a subset of all targets, so the identity bounds the ratio at or below 1"}
    res["coherence"]["not_testable"] = ["market-implied same-game correlations (no joint markets)", "team-total ladder agreement (needs ~3,000 more candle pulls)"]

    # cost (descriptive, marked at posted T-90 quote; not a return)
    q = pd.read_parquet(CACHE / "quotes.parquet")[["gid", "pid", "stat", "threshold", "bid90", "ask90"]].rename(columns={"threshold": "k"})
    C = S.merge(q, on=["gid", "pid", "stat", "k"], how="left").dropna(subset=["bid90", "ask90"])
    delta = C["p_corr"].to_numpy() - C["p_market90"].to_numpy()
    ask, bid, m = C["ask90"].to_numpy(), C["bid90"].to_numpy(), C["p_market90"].to_numpy()
    cost_yes = (ask - m) + FEE_RATE * ask * (1 - ask)
    cost_no = (m - bid) + FEE_RATE * (1 - bid) * bid
    buy_yes, buy_no = (delta > cost_yes), (-delta > cost_no)
    pnl = np.where(buy_yes, C["y_home_win"] - ask - FEE_RATE * ask * (1 - ask), np.where(buy_no, bid - C["y_home_win"] - FEE_RATE * (1 - bid) * bid, np.nan))
    flag = buy_yes | buy_no
    cl = (C["season"].astype(str) + "_" + C["week"].astype(str)).to_numpy()
    res["cost"] = {"thresholds": int(len(C)), "median_spread": float(np.median(ask - bid)), "median_abs_edge": float(np.median(np.abs(delta))),
                   "median_cost_to_cross_one_side": float(np.median(np.where(delta > 0, cost_yes, cost_no))),
                   "share_edge_exceeds_cost": float(flag.mean()), "flagged": int(flag.sum()),
                   "mean_marked_pnl_per_contract_after_fee": float(np.nanmean(pnl)) if flag.any() else None,
                   "marked_pnl_ci95": ev.cluster_boot(pnl[flag], cl[flag], 0.05) if flag.sum() > 30 else None,
                   "note": "marked at the posted T-90 quote; fills, depth, size and slippage not modeled; not a return"}
    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(res, indent=1, default=str)
    (OUT / "results.json").write_bytes(body.encode("utf-8"))
    print("Wrote reports/props_market/results.json sha256", hashlib.sha256(body.encode()).hexdigest())
    print("scored", res["scored"]["ladders"], "ladders", res["scored"]["weeks"], "weeks | mean CRPS", {k: round(v, 4) for k, v in res["mean_ladder_crps"].items()})
    for k, v in M.items():
        print(f"{k}: {v['mean_a']:.4f} vs {v['mean_b']:.4f} delta {v['delta']:+.4f} [{v['ci'][0]:+.4f},{v['ci'][1]:+.4f}] improves={v['improves']} material={v['material']}")
    for k, v in Lg.items():
        print(f"{k}: delta {v['delta']:+.5f} [{v['ci'][0]:+.5f},{v['ci'][1]:+.5f}] improves={v['improves']}")
    print("placebo", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["placebo"].items()})
    print("cost", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["cost"].items() if k != "note"})
    print("pass-yard identity", res["coherence"]["pass_yard_identity"]["ratio_receiving_sum_over_passing_mean_quartiles"])
    print("exceedance", {s: round(v["mean"], 3) for s, v in res["coherence"]["exceedance_sum_simulator_minus_market"].items()})


if __name__ == "__main__":
    main()
