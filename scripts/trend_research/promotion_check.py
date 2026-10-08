"""Promotion check for Champion v2: runs the PRODUCTION functions (scripts/champion_policy.py) on every reconstructed row and compares the full probability chain
(mean + distribution) with v1 at realistic prop lines, by segment, on the validation (2024) and holdout (2025) seasons and on settled 2026 tracker predictions.

Run: python scripts/trend_research.py promotion
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import nbinom, norm, poisson

from . import champion
from .experiments2 import champion_rows

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import champion_policy as cp  # noqa: E402

COUNT_LINES = {'receptions': [1.5, 2.5, 3.5, 4.5, 5.5, 6.5], 'rec_tds': [0.5], 'rush_tds': [0.5], 'atd': [0.5], 'pass_tds': [0.5, 1.5, 2.5]}
YARD_FACTORS = (0.8, 1.0, 1.2)
OUT = Path(__file__).resolve().parents[2] / 'research' / 'trend-intelligence' / 'promotion_check_champion_v2.json'
POSITIONS = {'receptions': ('WR', 'TE', 'RB'), 'rec_yds': ('WR', 'TE', 'RB'), 'rec_tds': ('WR', 'TE', 'RB'), 'rush_tds': ('RB',), 'atd': ('WR', 'TE', 'RB'),
             'pass_tds': ('QB',), 'pass_yds': ('QB',)}


def _blend_mean(row, market, c):
    cur, prior, k = row['cur_' + market], row['prior_' + market], row['k']
    if cur != cur:
        return prior
    if prior != prior:
        return cur
    return (k * cur + c * prior) / (k + c)


def _ln_over(line, mu_log, sigma, p0):
    """P(X > line) for a half-integer line with the rounded-lognormal convention used in index.html (F evaluated at floor(line)+0.5)."""
    x = math.floor(line) + 0.5
    if x <= 0:
        return 1 - p0
    if sigma <= 0:
        return (1 - p0) * (1.0 if math.exp(mu_log) > x else 0.0)
    return (1 - p0) * (1 - norm.cdf((math.log(x) - mu_log) / sigma))


def v1_over(market, row, line):
    if market in COUNT_LINES:
        return float(poisson.sf(math.floor(line), max(row['champ_' + market], 1e-9)))
    pw, pm, ps = row['pw_' + market], row['pm_' + market], row['ps_' + market]
    if not (pw > 0 and pm > 0) or ps != ps:
        return None
    sigma2 = math.log1p((ps / pm) ** 2)
    return _ln_over(line, math.log(pm) - sigma2 / 2, math.sqrt(sigma2), 1 - pw)


def v2_over(market, row, line, policy):
    spec = cp.market_policy(policy, market)
    if spec is None:
        return v1_over(market, row, line)
    mean = _blend_mean(row, market, spec['mean']['c'])
    if mean != mean:
        return None
    shape = spec.get('shape')
    if market in COUNT_LINES:
        mean = max(mean, 1e-9)
        if shape and shape.get('family') == 'nbinom':
            phi = shape['phi']
            n = 1.0 / phi
            return float(nbinom.sf(math.floor(line), n, n / (n + mean)))
        return float(poisson.sf(math.floor(line), mean))
    fields = cp.pooled_lognormal(mean, row['n'], 1 - row['pw_' + market], row['position'], shape)
    if fields is None:
        return None
    return _ln_over(line, fields['mu_log'], fields['sigma_log'], fields['zero_mass'])


def _rows_for(frame, market):
    rows = frame[frame.position.isin(POSITIONS[market])]
    if market.startswith('pass_'):
        rows = rows[rows.start]
    return rows.dropna(subset=['champ_' + market, 'y_' + market])


def evaluate(root, policy):
    frame = champion_rows(root)
    out = {'markets': {}, 'policy_version': policy['version']}
    for market in policy['markets']:
        rows = _rows_for(frame, market)
        rows = rows[rows.season >= 2024]
        if market in ('rec_yds', 'pass_yds'):
            rows = rows[(rows['pw_' + market] > 0) & (rows['pm_' + market] > 0) & rows['ps_' + market].notna()]
        records = []
        for row in rows.to_dict('records'):
            lines = COUNT_LINES[market] if market in COUNT_LINES else sorted({math.floor(max(row['champ_' + market] * f, 1.0)) + 0.5 for f in YARD_FACTORS})
            for line in lines:
                a, b = v1_over(market, row, line), v2_over(market, row, line, policy)
                if a is None or b is None:
                    continue
                records.append({'season': row['season'], 'week': row['week'], 'position': row['position'], 'k': row['k'], 'player_id': row['player_id'], 'mean': row['champ_' + market],
                                'y': 1.0 if row['y_' + market] > line else 0.0, 'p1': a, 'p2': b})
        df = pd.DataFrame(records)
        out['markets'][market] = _summarize(df)
    return out


def _brier(df, col):
    return float(((df[col] - df.y) ** 2).mean())


def _logloss(df, col):
    p = df[col].clip(1e-6, 1 - 1e-6)
    return float(-(df.y * np.log(p) + (1 - df.y) * np.log(1 - p)).mean())


def _slope(df, col):
    """Calibration slope of the logit of the probability against outcomes (1 = calibrated, <1 = overconfident)."""
    p = df[col].clip(1e-4, 1 - 1e-4)
    x = np.log(p / (1 - p)).to_numpy()
    y = df.y.to_numpy()
    if y.min() == y.max() or x.std() < 1e-9:
        return {'slope': None, 'intercept': None}
    intercept, beta = 0.0, 1.0
    for _ in range(40):  # damped Newton: a rare-event market must not blow up
        eta = np.clip(intercept + beta * x, -30, 30)
        q = 1 / (1 + np.exp(-eta))
        w = q * (1 - q) + 1e-9
        g = np.array([(y - q).sum(), ((y - q) * x).sum()])
        H = np.array([[w.sum(), (w * x).sum()], [(w * x).sum(), (w * x * x).sum()]]) + 1e-6 * np.eye(2)
        step = np.clip(np.linalg.solve(H, g), -1.0, 1.0)
        intercept, beta = intercept + step[0], beta + step[1]
    return {'slope': float(beta), 'intercept': float(intercept)}


def _cell(df):
    return {'n': int(len(df)), 'brier_v1': _brier(df, 'p1'), 'brier_v2': _brier(df, 'p2'), 'brier_relative_gain': (_brier(df, 'p1') - _brier(df, 'p2')) / _brier(df, 'p1'),
            'logloss_v1': _logloss(df, 'p1'), 'logloss_v2': _logloss(df, 'p2'), 'calibration_v1': _slope(df, 'p1'), 'calibration_v2': _slope(df, 'p2'),
            'mean_p_v1': float(df.p1.mean()), 'mean_p_v2': float(df.p2.mean()), 'observed': float(df.y.mean())}


def _summarize(df):
    res = {'by_season': {str(s): _cell(g) for s, g in df.groupby('season')}, 'segments': {}}
    res['all'] = _cell(df)
    # cluster bootstrap of the Brier difference over players
    d = (df.p1 - df.y) ** 2 - (df.p2 - df.y) ** 2
    groups = df.player_id.to_numpy()
    uniq, inv = np.unique(groups, return_inverse=True)
    sums, counts = np.bincount(inv, weights=d.to_numpy()), np.bincount(inv).astype(float)
    rng = np.random.default_rng(20261008)
    idx = rng.integers(0, len(sums), size=(2000, len(sums)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    res['brier_difference_ci95'] = [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]
    for name, mask in (('weeks 1-6', df.week <= 6), ('weeks 7+', df.week > 6), ('k<=2 current games', df.k <= 2), ('k>=6 current games', df.k >= 6)):
        sub = df[mask]
        if len(sub) >= 300:
            res['segments'][name] = _cell(sub)
    for pos, sub in df.groupby('position'):
        if len(sub) >= 300:
            res['segments'][f'position {pos}'] = _cell(sub)
    q = df['mean'].quantile([1 / 3, 2 / 3]).to_numpy()
    for name, mask in (('low-mean third', df['mean'] <= q[0]), ('middle third', (df['mean'] > q[0]) & (df['mean'] <= q[1])), ('high-mean third', df['mean'] > q[1])):
        sub = df[mask]
        if len(sub) >= 300:
            res['segments'][name] = _cell(sub)
    worst = min((c['brier_relative_gain'] for c in res['segments'].values()), default=0)
    res['worst_segment_relative_gain'] = float(worst)
    return res
