"""Power calculation for the luck-adjusted team strength test (docs/LUCK_ADJUSTED_PREREGISTRATION.md). Run BEFORE any new model is fitted.

Reads only data/cache/homewin_deep/forecast_wf.parquet, the saved walk-forward forecasts of the CURRENT score model and its Elo control
(2012 week 1 to 2026 week 8). It never builds or looks at the new model. It measures how noisy a paired comparison of two team-strength
models is on this history, then converts that into the smallest improvement the history can detect with 80% power.

    .venv\\Scripts\\python.exe scripts\\luck_prereg_power.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261101
DRAWS = 4000
PROSPECTIVE_GAMES = {"weeks 9 to 18 of 2026 (about 10 weeks)": 10 * 15}   # 2026 weeks 9 to 18, roughly 15 games a week after byes


def crps_normal(y, mu, sd):
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def logloss(p, win):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(win * np.log(p) + (1 - win) * np.log(1 - p))


def week_cluster_se(d: np.ndarray, groups: np.ndarray) -> float:
    """Standard error of the mean paired difference when games in one week share noise: resample whole weeks."""
    rng = np.random.default_rng(SEED)
    keys, inv = np.unique(groups, return_inverse=True)
    s, c = np.bincount(inv, weights=d), np.bincount(inv)
    idx = rng.integers(0, len(keys), (DRAWS, len(keys)))
    return float((s[idx].sum(1) / c[idx].sum(1)).std())


def main():
    w = pd.read_parquet(ROOT / "data" / "cache" / "homewin_deep" / "forecast_wf.parquet")
    w = w[w["played"] & ~w["tie"].astype(bool)].copy()
    wk = (w["season"].astype(str) + "-" + w["week"].astype(str)).to_numpy()
    y, mu, sd = w["y_m"].to_numpy(float), w["mu_m"].to_numpy(float), w["sd_m"].to_numpy(float)
    # Elo control as a normal forecast: its residual spread over the whole history (the control the earlier protocol used)
    elo_sd = float(np.std(y - w["elo_mu"].to_numpy(float)))
    c_model = crps_normal(y, mu, sd)
    c_elo = crps_normal(y, w["elo_mu"].to_numpy(float), elo_sd)
    d_margin = c_model - c_elo
    win = (y > 0).astype(float)
    d_ll = logloss(w["p_win"].to_numpy(float), win) - logloss(w["p_elo"].to_numpy(float), win)
    out = {"games": int(len(w)), "weeks": int(len(np.unique(wk))), "seasons": [int(w["season"].min()), int(w["season"].max())],
           "elo_residual_sd": elo_sd, "seed": SEED, "draws": DRAWS, "z_alpha_two_sided_05": 1.96, "z_power_80": 0.8416}
    for name, d in (("margin_crps_model_minus_elo", d_margin), ("winner_logloss_model_minus_elo", d_ll)):
        se_naive = float(d.std(ddof=1) / np.sqrt(len(d)))
        se_week = week_cluster_se(d, wk)
        mde = (1.96 + 0.8416) * se_week
        out[name] = {"mean": float(d.mean()), "sd_per_game": float(d.std(ddof=1)), "se_game_independent": se_naive, "se_week_clustered": se_week,
                     "min_detectable_improvement_80pct_power": mde,
                     "scaled_to_prospective": {k: float(mde * np.sqrt(len(d) / n)) for k, n in PROSPECTIVE_GAMES.items()}}
    # context for the size of the numbers
    out["context"] = {"margin_crps_current_model": float(c_model.mean()), "margin_crps_elo": float(c_elo.mean()),
                      "winner_logloss_current_model": float(logloss(w["p_win"].to_numpy(float), win).mean()),
                      "winner_logloss_elo": float(logloss(w["p_elo"].to_numpy(float), win).mean())}
    (ROOT / "docs" / "luck_prereg_power.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
