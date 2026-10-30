"""Step 0 of docs/PROPS_MARKET_ANCHORED_PREREGISTRATION.md: power by week-resampling simulation.

Semi-parametric: observed per-ladder / per-threshold paired differences from the 20 scored weeks keep their real
within-game and within-week structure. Whole weeks are resampled, a known improvement delta is injected, and the same
week-cluster bootstrap test is run. MDE(W) = smallest delta with power >= 0.80. Writes reports/props_market/power.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lab.config import CACHE_DIR, LAB_ROOT  # noqa: E402

CACHE = CACHE_DIR / "props_kalshi"
OUT = LAB_ROOT / "reports" / "props_market"
R, B, SEED = 300, 500, 0
WGRID = [20, 40, 60, 90, 150, 250, 400]
B_PROXY = 0.2
EVENT_RATES = [0.03, 0.05, 0.10, 0.20]
SESOI_LL, SESOI_CLV = 0.005, 0.005


def lg(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sig(x):
    return 1 / (1 + np.exp(-x))


def week_arrays(df: pd.DataFrame, d: np.ndarray):
    key = (df["season"].astype(str) + "_" + df["week"].astype(str)).to_numpy()
    codes, inv = np.unique(key, return_inverse=True)
    return np.bincount(inv, weights=d, minlength=len(codes)), np.bincount(inv, minlength=len(codes)).astype(float)


def power(sums, counts, delta, W, alpha, sign, rng, reps=R):
    """Share of week-resamples whose bootstrap CI excludes 0 after injecting `delta` (sign=-1: lower is better)."""
    nW = len(sums)
    hit = 0
    for _ in range(reps):
        w = rng.integers(0, nW, W)
        s, c = sums[w] + sign * delta * counts[w], counts[w]
        ix = rng.integers(0, W, (B, W))
        m = s[ix].sum(1) / np.maximum(c[ix].sum(1), 1)
        lo, hi = np.quantile(m, alpha / 2), np.quantile(m, 1 - alpha / 2)
        hit += (hi < 0) if sign < 0 else (lo > 0)
    return hit / reps


def mde(sums, counts, W, alpha, sign, rng, hi=0.5):
    lo = 0.0
    for _ in range(11):
        mid = (lo + hi) / 2
        if power(sums, counts, mid, W, alpha, sign, rng) >= 0.8:
            hi = mid
        else:
            lo = mid
    return float(hi)


def event_power(games, delta, W, rate, rng, reps=200):
    """games: per-game sums/counts with week ids; events chosen at random; test mean CLV difference > 0 on event games."""
    weeks = np.unique(games["wk"])
    by = {w: g for w, g in games.groupby("wk")}
    hit = 0
    for _ in range(reps):
        pick = rng.choice(weeks, W)
        s, c = np.zeros(W), np.zeros(W)
        for i, w in enumerate(pick):
            g = by[w]
            ev = rng.random(len(g)) < rate
            s[i] = (g["s"].to_numpy()[ev] + delta * g["n"].to_numpy()[ev]).sum()
            c[i] = g["n"].to_numpy()[ev].sum()
        if c.sum() == 0:
            continue
        ix = rng.integers(0, W, (B, W))
        m = s[ix].sum(1) / np.maximum(c[ix].sum(1), 1)
        hit += np.quantile(m, 0.025) > 0
    return hit / reps


def event_mde(games, W, rate, rng):
    lo, hi = 0.0, 0.2
    for _ in range(9):
        mid = (lo + hi) / 2
        if event_power(games, mid, W, rate, rng) >= 0.8:
            hi = mid
        else:
            lo = mid
    return float(hi)


def main():
    rng = np.random.default_rng(SEED)
    T = pd.read_parquet(CACHE / "scored_thresholds.parquet")
    res_prev = json.loads((LAB_ROOT / "reports" / "props_kalshi" / "results.json").read_text(encoding="utf-8"))
    icpt = res_prev["S"]["intercept"]
    w_m, w_s = res_prev["S"]["weights"]["p_mkt"]["w"], res_prev["S"]["weights"]["p_sim"]["w"]
    m, q, y = T["p_market90"].to_numpy(), T["p_K"].to_numpy(), T["y_home_win"].to_numpy(float)
    corr = sig(lg(m) + B_PROXY * (lg(q) - lg(m)))
    stack = sig(icpt + w_m * lg(m) + w_s * lg(q))
    T = T.assign(c_m=(m - y) ** 2, c_q=(q - y) ** 2, c_c=(corr - y) ** 2, c_s=(stack - y) ** 2,
                 l_m=-(y * np.log(np.clip(m, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - m, 1e-6, 1))),
                 l_q=-(y * np.log(np.clip(q, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - q, 1e-6, 1))),
                 l_c=-(y * np.log(np.clip(corr, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - corr, 1e-6, 1))),
                 l_s=-(y * np.log(np.clip(stack, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - stack, 1e-6, 1))))
    L = T.groupby(["gid", "pid", "stat"]).agg(season=("season", "first"), week=("week", "first"), c_m=("c_m", "sum"), c_q=("c_q", "sum"),
                                              c_c=("c_c", "sum"), c_s=("c_s", "sum")).reset_index()
    sesoi_crps = 0.01 * float(L["c_m"].mean())
    alpha = 0.05 / 3
    z = norm.ppf(1 - alpha / 2) + norm.ppf(0.8)
    out = {"design": {"weeks_observed": int(L[["season", "week"]].drop_duplicates().shape[0]), "ladders": int(len(L)), "thresholds": int(len(T)),
                      "resamples": R, "bootstrap_draws": B, "proxy_blend_b": B_PROXY, "sesoi_crps": sesoi_crps, "sesoi_logscore": SESOI_LL,
                      "mean_ladder_crps_market": float(L["c_m"].mean())}, "comparisons": {}}
    cases = {"M1_corrected_vs_market": (L, (L["c_c"] - L["c_m"]).to_numpy(), sesoi_crps),
             "M2_corrected_vs_simulator": (L, (L["c_c"] - L["c_q"]).to_numpy(), sesoi_crps),
             "M3_corrected_vs_existing_stack": (L, (L["c_c"] - L["c_s"]).to_numpy(), sesoi_crps),
             "L1_logscore_corrected_vs_market": (T, (T["l_c"] - T["l_m"]).to_numpy(), SESOI_LL),
             "L2_logscore_corrected_vs_simulator": (T, (T["l_c"] - T["l_q"]).to_numpy(), SESOI_LL),
             "L3_logscore_corrected_vs_existing_stack": (T, (T["l_c"] - T["l_s"]).to_numpy(), SESOI_LL)}
    for name, (df, d, sesoi) in cases.items():
        d0 = d - d.mean()  # null: no difference; variance and correlation structure kept
        s, c = week_arrays(df, d0)
        row = {"sd_pooled_difference": float(d.std()), "observed_mean_difference_proxy": float(d.mean()), "sesoi": float(sesoi), "mde_by_weeks": {}}
        for W in WGRID:
            row["mde_by_weeks"][W] = mde(s, c, W, alpha, -1, rng)
        m20 = row["mde_by_weeks"][20]
        row["N_weeks"] = int(np.ceil(20 * (m20 / sesoi) ** 2)) if m20 > sesoi else 20
        row["decidable_now"] = bool(m20 <= sesoi)
        row["prospective_only"] = bool((not row["decidable_now"]) and row["N_weeks"] <= 150)
        out["comparisons"][name] = row
        print(f"{name:<42} MDE(20)={m20:.4f} SESOI={sesoi:.4f} N={row['N_weeks']:>5} decidable_now={row['decidable_now']}", flush=True)

    # E: CLV difference (corrected proxy = K minus naive base) on event games only
    C = T.dropna(subset=["raw90", "rawC"]).copy()
    mv = (C["rawC"] - C["raw90"]).to_numpy()
    clv_k = mv * np.sign(C["p_K"].to_numpy() - C["raw90"].to_numpy())
    clv_b = mv * np.sign(C["p_base"].to_numpy() - C["raw90"].to_numpy())
    C["d"] = (clv_k - clv_b)
    C["d"] = C["d"] - C["d"].mean()
    G = C.groupby(["gid"]).agg(wk=("week", lambda s: 0), season=("season", "first"), week=("week", "first"), s=("d", "sum"), n=("d", "size")).reset_index()
    G["wk"] = G["season"].astype(str) + "_" + G["week"].astype(str)
    out["events"] = {"sesoi_clv": SESOI_CLV, "games": int(len(G)), "sd_pooled_difference": float(C["d"].std()), "mde_by_rate_and_weeks": {}}
    for rate in EVENT_RATES:
        row = {}
        for W in (20, 40, 90, 150, 250):
            row[W] = event_mde(G, W, rate, rng)
        m20 = row[20]
        out["events"]["mde_by_rate_and_weeks"][str(rate)] = {
            "mde": row, "N_weeks": int(np.ceil(20 * (m20 / SESOI_CLV) ** 2)) if m20 > SESOI_CLV else 20,
            "decidable_now": bool(m20 <= SESOI_CLV)}
        print(f"E rate {rate:.0%}: MDE(20)={m20:.4f} N={out['events']['mde_by_rate_and_weeks'][str(rate)]['N_weeks']}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    body = json.dumps(out, indent=1)
    (OUT / "power.json").write_bytes(body.encode("utf-8"))
    print("Wrote reports/props_market/power.json sha256", hashlib.sha256(body.encode()).hexdigest())


if __name__ == "__main__":
    main()
