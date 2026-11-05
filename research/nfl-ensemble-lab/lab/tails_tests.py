"""Tails test stage: tail-rate tests, forecast accuracy, range models, favorite-longshot table. Run only after docs/TAILS_PREREG.md is committed."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .tails import build, expected_tail, freeze_rule_hash, inventory, power, reconcile, rule


def holm(p: dict) -> dict:
    items = sorted(p.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, v) in enumerate(items):
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return out


def tail_tests(g: pd.DataFrame, sigma: float, R: dict, rng) -> dict:
    out = {}
    for stage in ("discovery", "confirmation"):
        a, b = R[stage]
        d = g[g["season"].between(a, b) & g["result"].notna()]
        rows, pv = {}, {}
        for f in R["flags"]:
            for T in R["tail_thresholds"]:
                hit = (d.loc[d[f], "e"].abs() >= T).to_numpy().astype(float)
                p0 = expected_tail(sigma, T)
                boot = rng.choice(hit, (R["bootstrap_draws"], len(hit))).mean(1) - p0
                key = f"{f}_{T}"
                pv[key] = float((boot <= 0).mean())
                rows[key] = {"flagged_games": int(len(hit)), "observed_rate": float(hit.mean()), "priced_rate": p0, "ratio": float(hit.mean() / p0), "diff": float(hit.mean() - p0), "p_one_sided": pv[key]}
        adj = holm(pv)
        for k in rows:
            rows[k]["p_holm"] = adj[k]
        out[stage] = rows
    out["passed"] = [k for k in out["discovery"] if all(out[s][k]["p_holm"] < R["alpha"] and out[s][k]["ratio"] >= R["min_ratio"] for s in ("discovery", "confirmation"))]
    return out


def brier_compare(g: pd.DataFrame, R: dict, rng) -> dict:
    disc = g["season"].between(*R["discovery"]) & g["result"].notna()
    conf = g[g["season"].between(*R["confirmation"]) & g["result"].notna()]
    y = np.where(conf["result"] > 0, 1.0, np.where(conf["result"] == 0, 0.5, 0.0))
    P = {}
    for name, col in (("closing_line", "spread_line"), ("elo", "elo"), ("elo_qb", "elo_qb")):
        sd = float((g.loc[disc, "result"] - g.loc[disc, col]).std())
        P[name] = {"sigma": sd, "p": stats.norm.cdf(conf[col].to_numpy() / sd)}
    b = {k: (v["p"] - y) ** 2 for k, v in P.items()}
    out = {"games": int(len(conf)), "brier": {k: float(v.mean()) for k, v in b.items()}, "sigma": {k: v["sigma"] for k, v in P.items()}, "paired": {}}
    for a, c in (("elo_qb", "elo"), ("elo", "closing_line"), ("elo_qb", "closing_line")):
        d = b[a] - b[c]
        boot = rng.choice(d, (2000, len(d))).mean(1)
        out["paired"][f"{a}_minus_{c}"] = {"mean": float(d.mean()), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
    return out


def range_models(g: pd.DataFrame, R: dict, rng) -> dict:
    from sklearn.linear_model import QuantileRegressor
    disc = g[g["season"].between(*R["discovery"]) & g["result"].notna()]
    conf = g[g["season"].between(*R["confirmation"]) & g["result"].notna()]
    X = lambda d: np.column_stack([d["u_qb"].astype(float), d["gap"]])
    pin = lambda q, e, qq: np.maximum(q * (e - qq), (q - 1) * (e - qq))
    tm, tc, lo_hi, out = np.zeros(len(conf)), np.zeros(len(conf)), [], {}
    ec = conf["e"].to_numpy()
    for q in (0.05, 0.95):
        fit = QuantileRegressor(quantile=q, alpha=0.0, solver="highs").fit(X(disc), disc["e"].to_numpy())
        qm = fit.predict(X(conf))
        tm += pin(q, ec, qm)
        tc += pin(q, ec, np.full(len(conf), float(disc["e"].quantile(q))))
        lo_hi.append(qm)
        out[f"q{int(q * 100)}_coef_const_qbflag_gap"] = [float(fit.intercept_)] + [float(v) for v in fit.coef_]
    d = tm - tc
    boot = rng.choice(d, (2000, len(d))).mean(1)
    out["pinball_model_minus_constant"] = {"mean": float(d.mean()), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}
    inside = (ec >= lo_hi[0]) & (ec <= lo_hi[1])
    out["coverage_90_model"] = float(inside.mean())
    for f in ("u_qb", "u_gap", "u_any"):
        m = conf[f].to_numpy()
        n, x = int(m.sum()), int((~inside[m]).sum())
        r = min(max(x / n, 1e-9), 1 - 1e-9)
        lr = 2 * (x * np.log(r / 0.10) + (n - x) * np.log((1 - r) / 0.90))
        out[f"coverage_90_model_{f}"] = {"games": n, "outside_rate": x / n, "kupiec_p": float(1 - stats.chi2.cdf(lr, 1))}
    dn, cn = disc[disc["u_any"]]["e"].to_numpy(), conf[conf["u_any"]]["e"].to_numpy()
    df, loc, sc = stats.t.fit(dn)
    out["t_fit_flagged"] = {"df": float(df), "scale": float(sc), "loglik_per_game_t_minus_normal_confirmation": float((stats.t.logpdf(cn, df, loc, sc) - stats.norm.logpdf(cn, dn.mean(), dn.std())).mean())}
    sigma = float(disc.loc[~disc["u_any"], "e"].std())
    out["pit_deciles_flagged_confirmation"] = [int(v) for v in np.histogram(stats.norm.cdf(cn / sigma), bins=10, range=(0, 1))[0]]
    return out


def longshot(g: pd.DataFrame, R: dict) -> dict:
    d = g[g["home_moneyline"].notna() & g["away_moneyline"].notna() & g["result"].notna()].copy()
    ip = lambda ml: np.where(ml < 0, -ml / (100 - ml), 100 / (100 + ml))
    ph, pa = ip(d["home_moneyline"].to_numpy()), ip(d["away_moneyline"].to_numpy())
    d["p_home"] = ph / (ph + pa)
    hd = d["p_home"] < 0.5
    d["p_dog"] = np.where(hd, d["p_home"], 1 - d["p_home"])
    tie = 0.5 * (d["result"] == 0)
    d["dog_win"] = np.where(hd, (d["result"] > 0) + tie, (d["result"] < 0) + tie)
    out = {}
    for stage in ("discovery", "confirmation"):
        s = d[d["season"].between(*R[stage])]
        rows = []
        for lo, hi in ((0, .15), (.15, .25), (.25, .35), (.35, .5)):
            m = s[(s["p_dog"] >= lo) & (s["p_dog"] < hi)]
            if len(m):
                k, n, z = float(m["dog_win"].sum()), len(m), 1.96
                c = (k / n + z * z / (2 * n)) / (1 + z * z / n)
                h = z * np.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
                rows.append({"implied_bin": [lo, hi], "games": n, "implied": float(m["p_dog"].mean()), "realized": k / n, "wilson95": [float(c - h), float(c + h)]})
        out[stage] = rows
    return out


def run_all() -> dict:
    R = rule()
    g, fitted = build()
    rng = np.random.default_rng(R["seed"])
    disc = g["season"].between(*R["discovery"]) & g["result"].notna()
    sigma = float(g.loc[disc & ~g["u_any"], "e"].std())
    return {"rule_sha256": freeze_rule_hash(), "inventory": inventory(), "reconcile": reconcile(), "fitted": fitted, "power": power(g, fitted),
            "tail_tests": tail_tests(g, sigma, R, rng), "forecast_accuracy": brier_compare(g, R, rng), "range_models": range_models(g, R, rng), "favorite_longshot": longshot(g, R)}
