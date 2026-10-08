"""Vectorised marginals, Gaussian-copula sampling and DraftKings scoring for the DFS research (mirrors the production chain in scripts/champion_policy.py).

A player-game is described by per-component marginals: Poisson counts (receptions, TDs) and lognormal-plus-zero-mass yardage. Dependence is a Gaussian copula: within a player
(receptions / yards / TDs move together) and across players (QB with his pass catchers, opposing offences). Correlations are MEASURED from normal scores of probability-integral
transforms on development seasons, not assumed.
"""
import math

import numpy as np
from scipy.stats import norm, poisson

from . import experiments7 as e7
from .experiments2 import _blend
from .promotion_check import cp

POLICY = None
COMPONENTS = {'QB': ['pass_yds', 'pass_tds', 'rush_yds', 'rush_tds'], 'RB': ['rush_yds', 'rush_tds', 'receptions', 'rec_yds', 'rec_tds'],
              'WR': ['receptions', 'rec_yds', 'rec_tds'], 'TE': ['receptions', 'rec_yds', 'rec_tds']}
COUNT = ('receptions', 'rec_tds', 'rush_tds', 'pass_tds')
COEF = {'pass_yds': 0.04, 'pass_tds': 4.0, 'rush_yds': 0.1, 'rush_tds': 6.0, 'receptions': 1.0, 'rec_yds': 0.1, 'rec_tds': 6.0}
BONUS = {'pass_yds': 300, 'rush_yds': 100, 'rec_yds': 100}


def policy():
    global POLICY
    if POLICY is None:
        import json
        POLICY = {**json.loads(cp.POLICY_PATH.read_text(encoding='utf-8')), 'active': True}
    return POLICY


class Marginal:
    """Marginal distribution of one component for many rows."""

    def __init__(self, market, frame, version):
        self.market = market
        n = len(frame)
        spec = cp.market_policy(policy(), market) if version == 'v2' else None
        if market in COUNT:
            mean = _blend(frame, market, spec['mean']['c']) if spec else frame['champ_' + market].to_numpy(float)
            self.kind = 'count'
            self.lam = np.where(np.isnan(mean), 0.0, np.maximum(mean, 0.0))
            return
        self.kind = 'ln'
        self.mu = np.zeros(n)
        self.sigma = np.zeros(n)
        self.p0 = np.ones(n)
        pw, pm, ps = frame['pw_' + market].to_numpy(float), frame['pm_' + market].to_numpy(float), frame['ps_' + market].to_numpy(float)
        positions = frame.position.to_numpy()
        n_games = frame['n'].to_numpy(float)
        blend = _blend(frame, market, spec['mean']['c']) if spec else None
        for i in range(n):
            done = False
            if spec and spec.get('shape') and not math.isnan(blend[i]) and positions[i] in (spec['shape'].get('cv') or {}):
                f = cp.pooled_lognormal(float(blend[i]), float(n_games[i]), float(1 - (pw[i] if pw[i] == pw[i] else 0.0)), positions[i], spec['shape'])
                if f:
                    self.mu[i], self.sigma[i], self.p0[i] = f['mu_log'], f['sigma_log'], f['nonpositive_weights'][0]
                    done = True
            if not done and pw[i] == pw[i] and pw[i] > 0 and pm[i] == pm[i] and pm[i] > 0:
                s2 = math.log1p((ps[i] / pm[i]) ** 2) if ps[i] == ps[i] else 0.0
                self.mu[i], self.sigma[i], self.p0[i] = math.log(pm[i]) - s2 / 2, math.sqrt(s2), 1 - pw[i]

    def ppf(self, u):
        """Quantile function for probabilities u (rows x draws) or (rows,)."""
        if self.kind == 'count':
            lam = self.lam.reshape(-1, *([1] * (u.ndim - 1)))
            return poisson.ppf(np.clip(u, 1e-12, 1 - 1e-12), np.maximum(lam, 1e-12)) * (lam > 1e-9)
        shape = (-1,) + (1,) * (u.ndim - 1)
        p0, mu, sg = self.p0.reshape(shape), self.mu.reshape(shape), self.sigma.reshape(shape)
        inner = np.clip((u - p0) / np.maximum(1 - p0, 1e-12), 1e-12, 1 - 1e-12)
        value = np.exp(mu + sg * norm.ppf(inner))
        return np.where(u <= p0, 0.0, np.rint(value))

    def pit(self, y, rng):
        """Randomised probability integral transform of the realised values y (rows,)."""
        if self.kind == 'count':
            lam = np.maximum(self.lam, 1e-12)
            lo, hi = poisson.cdf(y - 1, lam), poisson.cdf(y, lam)
            return lo + rng.random(len(y)) * (hi - lo)
        cdf_hi = np.where(y <= 0, self.p0, self.p0 + (1 - self.p0) * norm.cdf((np.log(np.maximum(y + 0.5, 1e-9)) - self.mu) / np.maximum(self.sigma, 1e-9)))
        cdf_lo = np.where(y <= 0, 0.0, np.where(y - 0.5 <= 0, self.p0, self.p0 + (1 - self.p0) * norm.cdf((np.log(np.maximum(y - 0.5, 1e-9)) - self.mu) / np.maximum(self.sigma, 1e-9))))
        return cdf_lo + rng.random(len(y)) * (cdf_hi - cdf_lo)


def dk_core(components):
    """Core DraftKings points from sampled/realised component arrays (dict market -> array). Bonuses included; interceptions, fumbles and conversions are not modelled."""
    total = 0
    for market, coef in COEF.items():
        if market in components:
            total = total + coef * components[market]
    for market, threshold in BONUS.items():
        if market in components:
            total = total + 3.0 * (components[market] >= threshold)
    return total


def nearest_correlation(matrix, floor=1e-6):
    """Project a symmetric matrix onto the nearest valid correlation matrix by eigenvalue clipping."""
    w, v = np.linalg.eigh((matrix + matrix.T) / 2)
    w = np.maximum(w, floor)
    out = v @ np.diag(w) @ v.T
    d = np.sqrt(np.diag(out))
    out = out / np.outer(d, d)
    np.fill_diagonal(out, 1.0)
    return out
