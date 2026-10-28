"""Probability-quality metrics and temporally aware paired bootstrap (model-side copy)."""
from __future__ import annotations
import numpy as np
import pandas as pd

EPS = 1e-9


def clip(p):
    return np.clip(np.asarray(p, float), EPS, 1 - EPS)


def logloss_vec(y, p):
    p = clip(p)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def logloss(y, p):
    return float(np.mean(logloss_vec(np.asarray(y, float), p)))


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def accuracy(y, p):
    return float(np.mean((np.asarray(p) >= 0.5) == (np.asarray(y) == 1)))


def auc(y, p):
    y = np.asarray(y, float)
    r = pd.Series(np.asarray(p, float)).rank().values
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _logit(p):
    p = clip(p)
    return np.log(p / (1 - p))


def calibration(y, p):
    """Slope (y ~ a + b*logit p, 2-parameter MLE) and intercept with slope fixed at 1 (calibration-in-the-large)."""
    y = np.asarray(y, float)
    z = _logit(p)

    def newton(X, offset):
        beta = np.zeros(X.shape[1])
        for _ in range(50):
            eta = offset + X @ beta
            mu = 1 / (1 + np.exp(-eta))
            g = X.T @ (y - mu)
            H = (X * (mu * (1 - mu))[:, None]).T @ X + 1e-9 * np.eye(X.shape[1])
            step = np.linalg.solve(H, g)
            beta += step
            if np.max(np.abs(step)) < 1e-9:
                break
        return beta, np.linalg.inv(H)

    b2, cov2 = newton(np.column_stack([np.ones_like(z), z]), 0.0)
    b1, cov1 = newton(np.ones((len(z), 1)), z)
    return {'intercept_fixed_slope': float(b1[0]), 'intercept_se': float(np.sqrt(cov1[0, 0])),
            'slope': float(b2[1]), 'slope_se': float(np.sqrt(cov2[1, 1]))}


def summary(y, p) -> dict:
    return {'n': int(len(y)), 'log_loss': logloss(y, p), 'brier': brier(y, p), 'accuracy': accuracy(y, p),
            'auc': auc(y, p), **calibration(y, p)}


def reliability(y, p, edges=(0, .3, .4, .5, .6, .7, .8, 1.0001)) -> pd.DataFrame:
    d = pd.DataFrame({'y': np.asarray(y, float), 'p': np.asarray(p, float)})
    d['bin'] = pd.cut(d.p, edges, right=False)
    r = d.groupby('bin', observed=True).agg(n=('y', 'size'), mean_p=('p', 'mean'), observed=('y', 'mean')).reset_index()
    r['se'] = np.sqrt(r.observed * (1 - r.observed) / r.n)
    return r


def paired_bootstrap(df: pd.DataFrame, diff_col: str, draws=4000, seed=20261028, block=None) -> dict:
    """Mean paired difference with date-clustered bootstrap inside season blocks.

    df needs columns: season, game_date, <diff_col>. block=None resamples whole game dates with replacement;
    block=k resamples circular blocks of k consecutive game dates (robustness to date-to-date dependence).
    """
    rng = np.random.default_rng(seed)
    seasons = []
    for s, g in df.groupby('season'):
        by = g.groupby('game_date')[diff_col].agg(['sum', 'size']).sort_index()
        seasons.append((by['sum'].values, by['size'].values))
    total = sum(x.sum() for x, _ in seasons)
    n = sum(m.sum() for _, m in seasons)
    num = np.zeros(draws)
    den = np.zeros(draws)
    for sums, counts in seasons:
        k = len(sums)
        if block is None:
            idx = rng.integers(0, k, size=(draws, k))
        else:
            nb = int(np.ceil(k / block))
            starts = rng.integers(0, k, size=(draws, nb))
            idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % k).reshape(draws, -1)[:, :k]
        num += sums[idx].sum(1)
        den += counts[idx].sum(1)
    boot = num / den
    lo95, hi95 = np.percentile(boot, [2.5, 97.5])
    lo975, hi975 = np.percentile(boot, [1.25, 98.75])
    return {'mean': float(total / n), 'n': int(n), 'ci95': [float(lo95), float(hi95)], 'ci975': [float(lo975), float(hi975)],
            'prob_negative': float(np.mean(boot < 0))}
