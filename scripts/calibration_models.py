"""Auditor B: point-in-time probability reconstruction and calibration candidates for the Champion (v1, v2) at realistic prop lines.

Read-only research code. Inputs are the PUBLIC nflverse-derived Champion frame (scripts/trend_research/champion.py, cached parquet) and aggregate line statistics;
no licensed Fantasy Points rows are read or written. Everything here is deterministic.

Layout
  load_frame / eligible_rows   - one row per (player, game) with the Champion's inputs, restricted to prop-like players per market
  Params                       - distribution parameters per row (lam, phi | mu, sig, p0) for the v1 / v2 / naive models
  build_long                   - expand each row to realistic posted lines (a main line near the median plus a ladder of alternates)
  metrics / bootstrap          - Brier, log loss, calibration intercept/slope, ECE, AUC, sharpness with player-clustered bootstrap CIs
  fit_* / apply_*              - Platt, isotonic, base-rate shrink, hierarchical pooling, variance and mean-model fixes
"""
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, gammaln
from scipy.stats import nbinom, norm, poisson

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import champion_policy as cp  # noqa: E402

FP_ROOT = Path(os.environ.get('CAL_FP_ROOT', REPO.parent / 'GOING' / 'FantasyPoints'))
DEV, VAL, HOLD = (2021, 2022, 2023), (2024,), (2025,)
EPS = 1e-6

# Market definitions. `floor` keeps only players a book would plausibly post (v1 mean); `offsets` are ladder steps around the main line.
MARKETS = {
    'receptions': dict(kind='count', positions=('WR', 'TE', 'RB'), floor=1.0, offsets=(-3, -2, -1, 0, 1, 2, 3)),
    'rec_yds': dict(kind='yards', positions=('WR', 'TE', 'RB'), floor=8.0, offsets=(-4, -3, -2, -1, 0, 1, 2, 3, 4)),
    'rush_yds': dict(kind='yards', positions=('RB',), floor=10.0, offsets=(-4, -3, -2, -1, 0, 1, 2, 3, 4)),
    'pass_yds': dict(kind='yards', positions=('QB',), floor=100.0, offsets=(-4, -3, -2, -1, 0, 1, 2, 3, 4), starters=True),
    'pass_tds': dict(kind='count', positions=('QB',), floor=0.3, offsets=(-1, 0, 1), starters=True),
    'rush_tds': dict(kind='count', positions=('RB',), floor=0.10, offsets=(0,)),
    'rec_tds': dict(kind='count', positions=('WR', 'TE', 'RB'), floor=0.10, offsets=(0,)),
    'atd': dict(kind='count', positions=('WR', 'TE', 'RB'), floor=0.20, offsets=(0,)),
}


# ----------------------------------------------------------------------------------------------------------------------------------------------- data
def load_frame(root=None):
    path = Path(root or FP_ROOT) / 'research' / 'cache' / 'champion_2021_2025.parquet'
    frame = pd.read_parquet(path)
    return frame[frame.ready].reset_index(drop=True)


def eligible_rows(frame, market, floor=None):
    spec = MARKETS[market]
    rows = frame[frame.position.isin(spec['positions'])]
    if spec.get('starters'):
        rows = rows[rows.start]
    rows = rows.dropna(subset=['champ_' + market, 'y_' + market])
    if spec['kind'] == 'yards':
        rows = rows[(rows['pw_' + market] > 0) & (rows['pm_' + market] > 0) & rows['ps_' + market].notna()]
    f = spec['floor'] if floor is None else floor
    rows = rows[rows['champ_' + market] >= f]
    return rows.reset_index(drop=True)


def blend(rows, market, c):
    cur, prior, k = rows['cur_' + market].to_numpy(float), rows['prior_' + market].to_numpy(float), rows['k'].to_numpy(float)
    out = (k * cur + c * prior) / (k + c)
    out = np.where(np.isnan(cur), prior, out)
    out = np.where(np.isnan(prior), cur, out)
    return out


def equal_weight_mean(rows, market):
    cur, prior = rows['cur_' + market].to_numpy(float), rows['prior_' + market].to_numpy(float)
    k, n_prior = rows['k'].to_numpy(float), rows['n_prior'].to_numpy(float)
    out = (k * cur + n_prior * prior) / (k + n_prior)
    out = np.where(np.isnan(cur), prior, out)
    return np.where(np.isnan(prior), cur, out)


def policy():
    path = REPO / 'config' / 'champion_policy.json'
    import json
    return json.loads(path.read_text(encoding='utf-8'))


def model_params(rows, market, model, pol=None):
    """Distribution parameters per row. model in {'v1','v2','naive'}. Counts: lam, phi. Yardage: mu, sig, p0. Rows where v2 does not apply fall back to v1."""
    pol = pol or policy()
    spec = MARKETS[market]
    mspec = pol['markets'].get(market)
    positions = rows.position.to_numpy()
    if spec['kind'] == 'count':
        lam = rows['champ_' + market].to_numpy(float)
        if model == 'v2' and mspec:
            applies = np.isin(positions, mspec['positions'])
            lam = np.where(applies, blend(rows, market, mspec['mean']['c']), lam)
        elif model == 'naive':
            lam = equal_weight_mean(rows, market)
        return dict(lam=np.maximum(lam, 1e-9), phi=np.zeros(len(rows)))
    pw, pm, ps = (rows[p + market].to_numpy(float) for p in ('pw_', 'pm_', 'ps_'))
    champ = rows['champ_' + market].to_numpy(float)
    if model == 'naive':
        scale = equal_weight_mean(rows, market) / np.where(champ > 0, champ, np.nan)
        pm, ps = pm * scale, ps * scale
    sigma2 = np.log1p((ps / pm) ** 2)
    mu, sig, p0 = np.log(pm) - sigma2 / 2, np.sqrt(sigma2), 1 - pw
    if model == 'v2' and mspec and mspec.get('shape'):
        shape = mspec['shape']
        mean = blend(rows, market, mspec['mean']['c'])
        n = rows['n'].to_numpy(float)
        cv = np.array([shape['cv'].get(p, np.nan) for p in positions])
        zr = np.array([shape['zero_rate'].get(p, np.nan) for p in positions])
        strength = shape.get('zero_shrink_games', 10)
        q0 = np.clip((n * (1 - pw) + strength * zr) / (n + strength), 0.001, 0.99)
        pos_mean = mean / (1 - q0)
        s2 = np.log1p(cv ** 2)
        ok = np.isfinite(cv) & (mean > 0)
        mu = np.where(ok, np.log(np.where(pos_mean > 0, pos_mean, 1)) - s2 / 2, mu)
        sig = np.where(ok, np.sqrt(s2), sig)
        p0 = np.where(ok, q0, p0)
    elif model == 'v2' and mspec:
        mean = blend(rows, market, mspec['mean']['c'])  # blend mean with the v1 spread (not a production configuration for rush/pass yards; shadow)
        scale = np.where(champ > 0, mean / champ, 1.0)
        mu = mu + np.log(np.where(scale > 0, scale, 1.0))
    return dict(mu=mu, sig=sig, p0=p0)


def p_over(params, line, kind, dist_fix=None):
    """P(stat > line) for half-integer lines using the production conventions (Poisson / NB sf at floor(line); rounded lognormal with zero mass at floor(line)+0.5)."""
    line = np.asarray(line, float)
    if kind == 'count':
        lam, phi = params['lam'], params['phi']
        if dist_fix:
            if 'w' in dist_fix:
                lam = dist_fix['w'] * lam + (1 - dist_fix['w']) * params['pos_lam']
            lam = np.exp(dist_fix.get('a', 0.0) + dist_fix.get('b', 1.0) * np.log(np.maximum(lam, 1e-9)))
            phi = np.full_like(lam, dist_fix.get('phi', 0.0)) + 0 * phi
        out = poisson.sf(np.floor(line), lam)
        pos = phi > 1e-9
        if pos.any():
            n = 1.0 / phi[pos]
            out[pos] = nbinom.sf(np.floor(line[pos]), n, n / (n + lam[pos]))
        return out
    mu, sig, p0 = params['mu'], params['sig'], params['p0']
    if dist_fix:
        mu = dist_fix.get('a', 0.0) + dist_fix.get('b', 1.0) * mu
        sig = sig * math.exp(dist_fix.get('s', 0.0))
        if 'c0' in dist_fix:
            p0 = expit(dist_fix['c0'] + dist_fix.get('c1', 1.0) * np.log(np.clip(p0, 1e-4, 1 - 1e-4) / (1 - np.clip(p0, 1e-4, 1 - 1e-4))))
    x = np.floor(line) + 0.5
    return (1 - p0) * norm.sf((np.log(x) - mu) / np.maximum(sig, 1e-9))


def median_of(params, kind):
    if kind == 'count':
        return poisson.ppf(0.5, params['lam'])
    p0, mu, sig = params['p0'], params['mu'], params['sig']
    q = np.clip((0.5 - p0) / (1 - p0), 1e-6, 1 - 1e-6)
    return np.where(p0 >= 0.5, 0.0, np.exp(mu + sig * norm.ppf(q)))


# ---------------------------------------------------------------------------------------------------------------------------------------- long frame
def build_long(frame, market, floor=None):
    """Rows x realistic lines. The line grid mimics what books post: counts on half-integers with a main line at the median; yardage on a 5-yard grid (x4.5/x9.5, which is
    ~78% of posted yardage lines in data/nfl_betting.json) with a ladder of alternates in steps of ~12% of the median. Lines are fixed from the v2 model's median BEFORE any correction."""
    spec = MARKETS[market]
    rows = eligible_rows(frame, market, floor)
    kind = spec['kind']
    base = model_params(rows, market, 'v2')
    med = median_of(base, kind)
    if kind == 'count':
        m = np.asarray(med, float)
        cand_lo, cand_hi = np.maximum(m - 0.5, 0.5), np.maximum(m + 0.5, 0.5)
        p_lo, p_hi = p_over(base, cand_lo, kind), p_over(base, cand_hi, kind)
        main = np.where(np.abs(p_lo - 0.5) <= np.abs(p_hi - 0.5), cand_lo, cand_hi)
        step = np.ones(len(rows))
    else:
        grid_main = np.maximum(np.round((med + 0.5) / 5.0) * 5.0 - 0.5, 4.5)
        main = grid_main
        step = np.maximum(5.0, 5.0 * np.round(0.12 * np.maximum(med, 1) / 5.0))
    idx, lines, offs = [], [], []
    for off in spec['offsets']:
        line = main + off * step
        ok = line >= (0.5 if kind == 'count' else 4.5)
        idx.append(np.flatnonzero(ok))
        lines.append(line[ok])
        offs.append(np.full(ok.sum(), off))
    idx, lines, offs = np.concatenate(idx), np.concatenate(lines), np.concatenate(offs)
    y_stat = rows['y_' + market].to_numpy(float)[idx]
    long = pd.DataFrame({'row': idx, 'line': lines, 'off': offs, 'is_main': offs == 0, 'y': (y_stat > lines).astype(float), 'stat': y_stat,
                         'season': rows.season.to_numpy()[idx], 'week': rows.week.to_numpy()[idx], 'player_id': rows.player_id.to_numpy()[idx],
                         'position': rows.position.to_numpy()[idx], 'k': rows.k.to_numpy()[idx], 'n': rows.n.to_numpy()[idx],
                         'mean_v1': rows['champ_' + market].to_numpy(float)[idx], 'median': np.asarray(med, float)[idx], 'step': step[idx]})
    return rows, long


def long_probs(rows, long, market, models=('v1', 'v2', 'naive')):
    kind = MARKETS[market]['kind']
    out = {}
    for model in models:
        params = model_params(rows, market, model)
        sub = {k: v[long.row.to_numpy()] for k, v in params.items()}
        out[model] = p_over(sub, long.line.to_numpy(), kind)
    return out


def row_params_long(rows, long, market, model='v2'):
    params = model_params(rows, market, model)
    return {k: v[long.row.to_numpy()] for k, v in params.items()}


# ----------------------------------------------------------------------------------------------------------------------------------------- metrics
def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def fit_logistic(x, y, w=None, ridge=0.0, center=(0.0, 1.0), iters=30, init=None, fit_a=True):
    """Weighted logistic regression y ~ a + b*x by damped Newton; ridge pulls (a, b) toward `center` (pseudo-observations)."""
    w = np.ones_like(x) if w is None else w
    a, b = init if init is not None else (0.0, 1.0)
    for _ in range(iters):
        q = expit(np.clip(a + b * x, -30, 30))
        wt = w * q * (1 - q) + 1e-12
        g = np.array([(w * (y - q)).sum() - ridge * (a - center[0]), (w * (y - q) * x).sum() - ridge * (b - center[1])])
        H = np.array([[wt.sum() + ridge, (wt * x).sum()], [(wt * x).sum(), (wt * x * x).sum() + ridge]]) + 1e-9 * np.eye(2)
        if not fit_a:
            g[0], H[0, :], H[:, 0], H[0, 0] = 0.0, 0.0, 0.0, 1.0
        step = np.clip(np.linalg.solve(H, g), -1.0, 1.0)
        a, b = a + step[0], b + step[1]
        if np.abs(step).max() < 1e-7:
            break
    return float(a), float(b)


class AucHelper:
    """Pre-grouped scores so a weighted AUC costs O(n) per bootstrap draw."""

    def __init__(self, p):
        _, self.grp = np.unique(p, return_inverse=True)
        self.k = int(self.grp.max()) + 1

    def auc(self, y, w):
        pos = np.bincount(self.grp, weights=w * y, minlength=self.k)
        neg = np.bincount(self.grp, weights=w * (1 - y), minlength=self.k)
        below = np.cumsum(neg) - neg
        tp, tn = pos.sum(), neg.sum()
        return float((pos * (below + 0.5 * neg)).sum() / (tp * tn)) if tp > 0 and tn > 0 else float('nan')


def weighted_auc(p, y, w):
    return AucHelper(p).auc(y, w)


def ece10(p, y, w):
    b = np.minimum((p * 10).astype(int), 9)
    tot = w.sum()
    n = np.bincount(b, weights=w, minlength=10)
    sp = np.bincount(b, weights=w * p, minlength=10)
    sy = np.bincount(b, weights=w * y, minlength=10)
    ok = n > 0
    return float((np.abs(sp[ok] - sy[ok])).sum() / tot)


def point_metrics(p, y, w=None, init=None, iters=30, auc=None):
    w = np.ones_like(p) if w is None else w
    p = np.clip(p, EPS, 1 - EPS)
    tot = w.sum()
    x = logit(p)
    a, b = fit_logistic(x, y, w, init=init, iters=iters) if 0 < y.mean() < 1 else (float('nan'), float('nan'))
    return {'n': float(tot), 'brier': float((w * (p - y) ** 2).sum() / tot), 'logloss': float(-(w * (y * np.log(p) + (1 - y) * np.log(1 - p))).sum() / tot),
            'slope': b, 'intercept': a, 'ece': ece10(p, y, w), 'auc': (auc or AucHelper(p)).auc(y, w), 'sharpness': float((w * np.abs(2 * p - 1)).sum() / tot),
            'mean_p': float((w * p).sum() / tot), 'rate': float((w * y).sum() / tot)}


def cluster_index(groups):
    uniq, inv = np.unique(groups, return_inverse=True)
    return inv, len(uniq)


def bootstrap_metrics(p, y, groups, draws=300, seed=20261009, base_p=None):
    """Player-clustered bootstrap CIs for every metric (and, if base_p is given, for the paired Brier/log-loss/ECE differences base - p, positive = p better)."""
    inv, g = cluster_index(groups)
    rng = np.random.default_rng(seed)
    point = point_metrics(p, y)
    keys = ['brier', 'logloss', 'slope', 'intercept', 'ece', 'auc']
    store = {k: [] for k in keys}
    diffs = {k: [] for k in ('brier', 'logloss', 'ece')}
    base_point = point_metrics(base_p, y) if base_p is not None else None
    auc_p = AucHelper(p)
    auc_b = AucHelper(base_p) if base_p is not None else None
    for _ in range(draws):
        w = np.bincount(rng.integers(0, g, g), minlength=g).astype(float)[inv]
        if w.sum() == 0:
            continue
        m = point_metrics(p, y, w, init=(point['intercept'], point['slope']), iters=6, auc=auc_p)
        for k in keys:
            store[k].append(m[k])
        if base_p is not None:
            mb = point_metrics(base_p, y, w, init=(base_point['intercept'], base_point['slope']), iters=2, auc=auc_b)
            for k in diffs:
                diffs[k].append(mb[k] - m[k])
    ci = {k: [float(np.nanquantile(v, 0.025)), float(np.nanquantile(v, 0.975))] for k, v in store.items()}
    out = {'point': point, 'ci95': ci}
    if base_p is not None:
        out['gain_vs_base'] = {k: {'point': float(base_point[k] - point[k]), 'ci95': [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]} for k, v in diffs.items()}
        out['gain_vs_base']['brier_relative'] = float((base_point['brier'] - point['brier']) / base_point['brier'])
    return out


def paired_brier_gain(p_base, p_new, y, groups, draws=1000, seed=7):
    inv, g = cluster_index(groups)
    d = (p_base - y) ** 2 - (p_new - y) ** 2
    sums, counts = np.bincount(inv, weights=d, minlength=g), np.bincount(inv, minlength=g).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, g, size=(draws, g))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    return {'point': float(d.mean()), 'ci95': [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]}


def reliability(p, y, bins=10, w=None):
    w = np.ones_like(p) if w is None else w
    b = np.minimum((p * bins).astype(int), bins - 1)
    rows = []
    for i in range(bins):
        m = b == i
        if m.sum() == 0:
            continue
        rows.append({'bin': f'{i / bins:.1f}-{(i + 1) / bins:.1f}', 'n': int(m.sum()), 'mean_p': float(p[m].mean()), 'rate': float(y[m].mean())})
    return rows


# ------------------------------------------------------------------------------------------------------------------------------------ corrections
def platt_fit(p, y, w=None):
    a, b = fit_logistic(logit(p), y, w)
    return {'method': 'platt', 'a': a, 'b': b}


def platt_apply(p, spec):
    return expit(spec['a'] + spec['b'] * logit(p))


def iso_fit(p, y):
    from sklearn.isotonic import IsotonicRegression
    iso = IsotonicRegression(y_min=0.002, y_max=0.998, out_of_bounds='clip').fit(p, y)
    xs, ys = iso.X_thresholds_, iso.y_thresholds_
    # thin to <=40 knots by quantile for the JSON, keeping the function monotone
    if len(xs) > 40:
        keep = np.unique(np.linspace(0, len(xs) - 1, 40).astype(int))
        xs, ys = xs[keep], ys[keep]
    return {'method': 'isotonic', 'x': [float(v) for v in xs], 'y': [float(v) for v in ys]}


def iso_apply(p, spec):
    return np.interp(p, spec['x'], spec['y'])


def base_rate_table(line, y):
    df = pd.DataFrame({'line': line, 'y': y})
    t = df.groupby('line').y.agg(['mean', 'size'])
    return {float(k): float(v) for k, v in t['mean'].items() if t.loc[k, 'size'] >= 30}, float(df.y.mean())


def base_rate_apply(line, table, overall):
    return np.array([table.get(float(l), overall) for l in line])


def shrink_fit(p, y, base):
    d = p - base
    den = (d * d).sum()
    w = float(np.clip(((y - base) * d).sum() / den, 0, 1)) if den > 0 else 0.0
    return {'method': 'shrink_base', 'w': w}


def shrink_apply(p, base, spec):
    return spec['w'] * p + (1 - spec['w']) * base


def pooled_fit(per_market, kappa):
    """Hierarchical (empirical-Bayes style) logistic recalibration. per_market: {name: (p, y)}. Pooled (a,b) fitted on all markets stacked; each market's (a,b) is the
    penalised fit that pulls toward the pooled value with kappa pseudo-observations."""
    xs = np.concatenate([logit(p) for p, _ in per_market.values()])
    ys = np.concatenate([y for _, y in per_market.values()])
    pooled = fit_logistic(xs, ys)
    out = {}
    for name, (p, y) in per_market.items():
        a, b = fit_logistic(logit(p), y, ridge=kappa, center=pooled)
        out[name] = {'method': 'pooled_platt', 'a': a, 'b': b, 'kappa': kappa, 'pooled': list(pooled)}
    return out


def _nll_lines(theta, kind, params, line, y, mask_names, fixed):
    fix = dict(fixed)
    fix.update(dict(zip(mask_names, theta)))
    p = np.clip(p_over(params, line, kind, dist_fix=fix), EPS, 1 - EPS)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def dist_fit(kind, params, line, y, variant):
    """Fit a distribution fix by minimising line-level log loss on the development rows. variants -> parameter names:
    counts: 'var' (phi), 'mean_var' (a, b, phi); yardage: 'var' (s), 'var_zero' (s, c0), 'mean_var_zero' (a, b, s, c0)."""
    spaces = {('count', 'var'): (['phi'], [0.1]), ('count', 'mean_var'): (['a', 'b', 'phi'], [0.0, 1.0, 0.1]), ('count', 'shrink_var'): (['w', 'a', 'phi'], [0.8, 0.0, 0.1]),
              ('yards', 'var'): (['s'], [0.0]), ('yards', 'var_zero'): (['s', 'c0'], [0.0, 0.0]), ('yards', 'mean_var_zero'): (['a', 'b', 's', 'c0'], [0.0, 1.0, 0.0, 0.0])}
    names, x0 = spaces[(kind, variant)]
    if kind == 'yards':
        fixed = {'a': 0.0, 'b': 1.0, 's': 0.0}
    else:
        fixed = {'a': 0.0, 'b': 1.0, 'phi': 0.0}
    bounds = {'w': (0.0, 1.0), 'phi': (0.0, 2.0), 's': (-0.5, 1.0), 'c0': (-3, 3), 'a': (-8, 8), 'b': (0.3, 1.5)}
    res = minimize(_nll_lines, x0, args=(kind, params, line, y, names, fixed), method='L-BFGS-B', bounds=[bounds[n] for n in names])
    out = dict(fixed)
    out.update(dict(zip(names, [float(v) for v in res.x])))
    if kind == 'count' and 'phi' not in names:
        out['phi'] = 0.0
    out = {k: v for k, v in out.items() if k in names or k in ('a', 'b') or (k == 'c0' and 'c0' in names)}
    if 'w' in names:
        out['pos_lam_note'] = 'lam = w*lam + (1-w)*pos_lam[position]; pos_lam are 2021-2023 position means (see parameters)'
    return {'method': 'dist_' + variant, **out}


def dist_apply(kind, params, line, spec):
    fix = {k: v for k, v in spec.items() if k not in ('method',)}
    if kind == 'count':
        fix.setdefault('a', 0.0)
        fix.setdefault('b', 1.0)
    return p_over(params, line, kind, dist_fix=fix)


# ------------------------------------------------------------------------------------------------------------------- JS-equivalent application
def apply_spec(p_over_value, spec, side='Over', push=0.0):
    """Reference implementation of what the JS function must do (used by tests): calibrate P(over | no push), then rescale by (1 - push); Under is the complement."""
    p = np.asarray(p_over_value, float)
    q = p / np.maximum(1 - push, 1e-12) if np.any(push) else p
    if spec['method'] in ('platt', 'pooled_platt'):
        c = expit(spec['a'] + spec['b'] * logit(q))
    elif spec['method'] == 'isotonic':
        c = np.interp(q, spec['x'], spec['y'])
    else:
        raise ValueError(spec['method'])
    over = c * (1 - push)
    return over if side == 'Over' else (1 - push) - over
