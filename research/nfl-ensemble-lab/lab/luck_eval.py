"""Scoring and statistics for the luck-adjusted strength test (docs/LUCK_ADJUSTED_PREREGISTRATION.md, Amendment 1)."""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

SEED = 20261101
DRAWS = 4000
Z80 = 1.2815515655446004


def crps(y, mu, sd):
    z = (np.asarray(y, float) - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def logloss(p, win):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(win * np.log(p) + (1 - win) * np.log(1 - p))


def brier(p, win):
    return (p - win) ** 2


def week_bootstrap(d: np.ndarray, weeks: np.ndarray, draws: int = DRAWS, seed: int = SEED) -> dict:
    """Mean paired difference with a 95% interval from resampling whole weeks."""
    keys, inv = np.unique(weeks, return_inverse=True)
    s, c = np.bincount(inv, weights=d), np.bincount(inv)
    idx = np.random.default_rng(seed).integers(0, len(keys), (draws, len(keys)))
    m = s[idx].sum(1) / c[idx].sum(1)
    return {"mean": float(d.mean()), "lo": float(np.percentile(m, 2.5)), "hi": float(np.percentile(m, 97.5)), "weeks": int(len(keys)), "games": int(len(d))}


def diebold_mariano(d: np.ndarray, weeks: np.ndarray, lag: int = 4) -> dict:
    """Weekly mean loss differences, Newey-West variance with `lag` weeks, two-sided normal p-value. Negative mean = first model better."""
    keys, inv = np.unique(weeks, return_inverse=True)
    wk = np.bincount(inv, weights=d) / np.bincount(inv)
    T = len(wk)
    e = wk - wk.mean()
    var = float((e * e).sum() / T)
    for L in range(1, lag + 1):
        var += 2 * (1 - L / (lag + 1)) * float((e[L:] * e[:-L]).sum() / T)
    se = np.sqrt(max(var, 1e-18) / T)
    stat = float(wk.mean() / se)
    return {"stat": stat, "p": float(2 * (1 - norm.cdf(abs(stat)))), "weeks": T}


def holm(pvals: dict) -> dict:
    order = sorted(pvals, key=pvals.get)
    out, running = {}, 0.0
    for i, k in enumerate(order):
        running = max(running, min(1.0, (len(order) - i) * pvals[k]))
        out[k] = running
    return out


def season_wins(loss_new: np.ndarray, loss_ref: np.ndarray, seasons: np.ndarray) -> dict:
    ss = np.unique(seasons)
    better = {int(s): bool(loss_new[seasons == s].mean() < loss_ref[seasons == s].mean()) for s in ss}
    return {"better_in": int(sum(better.values())), "of": int(len(ss)), "by_season": better}


def placebo(mu, sd, y, ref_loss, weeks, seasons, shuffles: int = 200, seed: int = SEED) -> dict:
    """Shuffle the new model's (mean, spread) pairs across games within each week; the mean CRPS difference against the reference must not be a gain."""
    rng = np.random.default_rng(seed)
    keys, inv = np.unique(weeks, return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(len(keys))]
    diffs = []
    for _ in range(shuffles):
        perm = np.arange(len(y))
        for g in groups:
            perm[g] = rng.permutation(g)
        diffs.append(float((crps(y, mu[perm], sd[perm]) - ref_loss).mean()))
    d = np.array(diffs)
    return {"mean_diff": float(d.mean()), "lo": float(np.percentile(d, 2.5)), "hi": float(np.percentile(d, 97.5)), "shuffles": shuffles}


def coverage80(y, mu, sd) -> float:
    return float((np.abs(np.asarray(y) - mu) <= Z80 * sd).mean())


def pit_hist(y, mu, sd, bins: int = 10) -> list[int]:
    return np.histogram(norm.cdf((np.asarray(y) - mu) / sd), bins=bins, range=(0, 1))[0].tolist()


def brier_decomposition(p, win, bins: int = 10) -> dict:
    """Brier = reliability - resolution + uncertainty, with equal-width probability bins."""
    p, win = np.asarray(p), np.asarray(win)
    b = np.minimum((p * bins).astype(int), bins - 1)
    base = win.mean()
    rel = res = 0.0
    for i in range(bins):
        m = b == i
        if m.any():
            f, o, n = p[m].mean(), win[m].mean(), m.sum()
            rel += n * (f - o) ** 2
            res += n * (o - base) ** 2
    n = len(p)
    return {"brier": float(brier(p, win).mean()), "reliability": float(rel / n), "resolution": float(res / n), "uncertainty": float(base * (1 - base))}


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def best_blend_weight(p_line, p_new, win, grid=np.arange(-0.5, 1.5001, 0.05)) -> float:
    """w maximizing the log-likelihood of sigmoid(logit p_line + w x (logit p_new - logit p_line))."""
    base, diff = logit(p_line), logit(p_new) - logit(p_line)
    best, bw = -np.inf, 0.0
    for w in grid:
        pb = 1 / (1 + np.exp(-(base + w * diff)))
        ll = -logloss(pb, win).mean()
        if ll > best:
            best, bw = ll, float(w)
    return bw
