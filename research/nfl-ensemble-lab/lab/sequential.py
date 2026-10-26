"""Always-valid sequential evidence (Phase 14): a betting e-process for bounded per-game evidence.

H0: E[x] <= 0 for x in [-1, 1]. Wealth E_t = prod(1 + lambda_t x_t) with a predictable bet
lambda_t = clip(m / (v + m^2), 0, 0.5) from games before t (aGRAPA-style). Under H0, E_t is a nonnegative
supermartingale, so P(sup E_t >= 1/alpha) <= alpha (Ville's inequality): checking every week is valid.
"""
from __future__ import annotations

import numpy as np

THRESHOLD = 20.0          # 1 / alpha, alpha = 0.05


def e_process(x) -> dict:
    x = np.clip(np.asarray(x, float), -1.0, 1.0)
    wealth, path = 1.0, []
    s1 = s2 = 0.0
    for i, xi in enumerate(x):
        if i == 0:
            lam = 0.0
        else:
            m = s1 / i
            v = max(s2 / i - m * m, 0.0)
            lam = float(np.clip(m / (v + m * m + 1e-12), 0.0, 0.5))
        wealth *= 1.0 + lam * xi
        path.append(wealth)
        s1 += xi
        s2 += xi * xi
    return {"n": int(len(x)), "mean": float(x.mean()) if len(x) else None, "e_value": float(wealth),
            "max_e": float(max(path)) if path else 1.0, "crossed": bool(path and max(path) >= THRESHOLD), "path": path}


def cs_upper(x, alpha: float = 0.05, rho2: float = 0.079) -> float | None:
    """One-sided Robbins normal-mixture confidence sequence upper bound on the running mean of x in [-1, 1]
    (sub-Gaussian with sigma = 1; rho2 tuned for n near 100). Valid simultaneously at all n (Phase 15 futility bound)."""
    x = np.clip(np.asarray(x, float), -1.0, 1.0)
    t = len(x)
    if t == 0:
        return None
    radius = np.sqrt((t * rho2 + 1) / rho2 * 2 * np.log(np.sqrt(t * rho2 + 1) / alpha))
    return float((x.sum() + radius) / t)


def monitor_summary(x, min_effect: float) -> dict:
    """e-process (evidence for improvement) plus futility (upper confidence bound below the minimum meaningful effect)."""
    e = {k: v for k, v in e_process(x).items() if k != "path"}
    up = cs_upper(x)
    e |= {"cs_upper": up, "min_effect": min_effect, "futile": bool(up is not None and up < min_effect)}
    return e
