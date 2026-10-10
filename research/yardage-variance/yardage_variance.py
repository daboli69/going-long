"""Yardage variance / mean / tail research (rec_yds, rush_yds, pass_yds). Read-only: uses the licensed Champion cache in memory only, writes aggregates.

Protocol: walk-forward. For test season T in (2023, 2024, 2025) every model is fit ONLY on seasons < T. Variant selection uses 2023+2024; 2025 is confirmation only.
Lines are the cm.build_long ladder (anchored on the deployed v2 median BEFORE any correction). Loss = line-level Brier / log loss, paired against the
current Champion (v2 params, i.e. the production probabilities) with season-week-team cluster bootstrap. Zero parameter vector == Champion.
Usage: python research/yardage-variance/yardage_variance.py [market ...]   (default rec_yds rush_yds pass_yds). No network, no writes except results_<market>.json.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize, nnls
from scipy.special import expit, logit
from scipy.stats import gamma as gamma_dist, norm

warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
import calibration_models as cm  # noqa: E402

EPS = 1e-6
TESTS = (2023, 2024, 2025)
ACT = {'rec_yds': 'y_targets', 'rush_yds': 'y_carries', 'pass_yds': 'y_attempts'}
SHARE = {'rec_yds': 'target_share', 'rush_yds': 'carry_share', 'pass_yds': None}
CENTER = {'rec_yds': np.log(30.0), 'rush_yds': np.log(40.0), 'pass_yds': np.log(235.0)}
POL = cm.policy()
CALPOL = json.loads((HERE.parents[1] / 'config' / 'calibration_policy.json').read_text(encoding='utf-8'))


# ------------------------------------------------------------------------------------------------------------------------------ features
def base_from_v2(rows, market):
    p = cm.model_params(rows, market, 'v2', POL)
    M = (1 - p['p0']) * np.exp(p['mu'] + p['sig'] ** 2 / 2)
    return dict(M=M, sig=p['sig'], p0=np.clip(p['p0'], 1e-4, 0.99))


def feature_blocks(rows, market, base):
    n = len(rows)
    k = rows.k.to_numpy(float)
    lM = np.log(base['M']) - CENTER[market]
    ls0 = np.log(base['sig']) - np.log(0.8)
    k0, klow, inv = (k == 0).astype(float), ((k >= 1) & (k <= 2)).astype(float), 1.0 / (1.0 + k)
    pos = rows.position.to_numpy()
    te, rb = (pos == 'TE').astype(float), (pos == 'RB').astype(float)
    cvs = np.zeros(n)
    sh = SHARE[market]
    if sh:
        cs, ss = rows['champ_' + sh].to_numpy(float), rows['sd_' + sh].to_numpy(float)
        cvs = np.clip(np.where(cs > 0.01, ss / np.maximum(cs, 0.01), 1.0), 0, 3.0) - 0.8
        cvs = np.nan_to_num(cvs)
    l0 = logit(base['p0']) + 1.5
    one = np.ones(n)
    posd = [te, rb] if market == 'rec_yds' else []
    # each block lists (name, column); theta==0 reproduces the base model
    mean = {'a': one, 'b': lM, 'k0': k0, 'klow': klow}
    sigb = {'s0': one, 's_lM': lM, 's_ls0': ls0, 's_k0': k0, 's_klow': klow, 's_inv': inv, 's_cvs': cvs}
    for nm, col in zip(('te', 'rb'), posd):
        mean['m_' + nm] = col
        sigb['s_' + nm] = col
    p0b = {'d0': one, 'd1': l0, 'dk0': k0}
    return dict(mean=mean, sig=sigb, p0=p0b)


class Spec:
    """Which coefficients are free for a variant. names refer to feature_blocks keys; a tail shape may be 'ln', 'gamma' or 'mix'."""

    def __init__(self, mean=(), sig=(), p0=(), shape='ln', ridge=2e-3):
        self.mean, self.sig, self.p0, self.shape, self.ridge = tuple(mean), tuple(sig), tuple(p0), shape, ridge
        self.n_extra = 3 if shape == 'mix' else 0

    def names(self):
        return ['m:' + s for s in self.mean] + ['s:' + s for s in self.sig] + ['p:' + s for s in self.p0] + ['x%d' % i for i in range(self.n_extra)]


def row_params(spec, theta, blocks, base):
    th = dict(zip(spec.names(), theta))
    lm = np.log(base['M']).copy()
    for s in spec.mean:
        lm = lm + th['m:' + s] * blocks['mean'][s]
    ls = np.log(base['sig']).copy()
    for s in spec.sig:
        ls = ls + th['s:' + s] * blocks['sig'][s]
    lp = logit(base['p0']).copy()
    for s in spec.p0:
        lp = lp + th['p:' + s] * blocks['p0'][s]
    p0 = np.clip(expit(lp), 1e-4, 0.99)
    sig = np.exp(ls)
    mc = np.exp(lm) / (1 - p0)
    extra = [th['x%d' % i] for i in range(spec.n_extra)]
    return dict(mc=mc, sig=sig, p0=p0, extra=extra)


def prob_over(shape, rp, idx, line):
    mc, sig, p0 = rp['mc'][idx], rp['sig'][idx], rp['p0'][idx]
    if shape == 'ln':
        sf = norm.sf((np.log(line) - (np.log(mc) - sig ** 2 / 2)) / sig)
    elif shape == 'gamma':
        cv2 = np.expm1(sig ** 2)
        sf = gamma_dist.sf(line, a=1 / cv2, scale=mc * cv2)
    else:  # two-component lognormal mixture, mean preserving: weight w "boom" at r*mean, remainder at r2*mean
        e0, e1, e2 = rp['extra']
        w = float(np.clip(expit(e0), 0.02, 0.5))
        r = 1 + (1 / w - 1) * float(expit(e1)) * 0.98
        r2 = (1 - w * r) / (1 - w)
        si = sig * np.exp(e2)
        sf = w * norm.sf((np.log(line) - (np.log(mc * r) - si ** 2 / 2)) / si) + (1 - w) * norm.sf((np.log(line) - (np.log(mc * r2) - si ** 2 / 2)) / si)
    return (1 - p0) * sf


def ll_loss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def fit_spec(spec, long_tr, blocks_tr, base_tr):
    names = spec.names()
    idx, line, y = long_tr.row.to_numpy(), long_tr.line.to_numpy(), long_tr.y.to_numpy()
    x0 = np.zeros(len(names))
    for i, nm in enumerate(names):
        if nm == 'x0':
            x0[i] = logit(0.15)
        if nm == 'x2':
            x0[i] = -0.3
    if not names:
        return x0
    free_pen = np.array([0.0 if nm in ('s:s0', 'm:a', 'p:d0') or nm.startswith('x') else 1.0 for nm in names])

    def obj(theta):
        rp = row_params(spec, theta, blocks_tr, base_tr)
        p = prob_over(spec.shape, rp, idx, line)
        return float(ll_loss(p, y).mean() + spec.ridge * (free_pen * theta ** 2).sum())

    bnds = [(-3, 3)] * len(names)
    res = minimize(obj, x0, method='L-BFGS-B', bounds=bnds)
    return res.x


# ------------------------------------------------------------------------------------------------------------------------------ conditional-on-playing base
def cond_base(rows_tr, rows, market, base_all=None):
    """Mean fixed on rows with activity>0 (ratio of means by k bucket on pm), zero mass fixed by a logistic on activity==0. Fit on rows_tr only."""
    act = ACT[market]

    def bucket(k):
        k = np.asarray(k)
        return np.where(k == 0, 0, np.where(k <= 2, 1, 2))
    played = rows_tr[act].to_numpy() > 0
    b_tr = base_from_v2(rows_tr, market)
    pmtr = b_tr['M'] / (1 - b_tr['p0'])
    ytr = rows_tr['y_' + market].to_numpy(float)
    btr = bucket(rows_tr.k)
    ratio = np.array([ytr[played & (btr == b)].sum() / max(pmtr[played & (btr == b)].sum(), 1e-9) if (played & (btr == b)).sum() > 20 else 1.0 for b in range(3)])
    zero_tr = (~played).astype(float)
    l_tr = logit(b_tr['p0'])
    k0tr = (rows_tr.k.to_numpy() == 0).astype(float)

    def nll(t):
        p = np.clip(expit(t[0] + t[1] * l_tr + t[2] * k0tr), EPS, 1 - EPS)
        return float(-(zero_tr * np.log(p) + (1 - zero_tr) * np.log(1 - p)).mean())
    t = minimize(nll, [0, 1, 0], method='L-BFGS-B').x
    b_all = base_from_v2(rows, market)
    pm = b_all['M'] / (1 - b_all['p0']) * ratio[bucket(rows.k)]
    l = logit(b_all['p0'])
    p0 = np.clip(expit(t[0] + t[1] * l + t[2] * (rows.k.to_numpy() == 0)), 1e-4, 0.99)
    sig = b_all['sig']
    return dict(M=pm * (1 - p0), sig=sig, p0=p0), dict(ratio_by_k_bucket=ratio.tolist(), p0_logistic=[float(v) for v in t])


# ------------------------------------------------------------------------------------------------------------------------------ evaluation
class Clusters:
    def __init__(self, groups, draws=1000, seed=11):
        self.inv, self.g = np.unique(groups, return_inverse=True)[1], len(np.unique(groups))
        rng = np.random.default_rng(seed)
        self.idx = rng.integers(0, self.g, size=(draws, self.g))

    def gain(self, d, mask):
        s = np.bincount(self.inv, weights=d * mask, minlength=self.g)
        c = np.bincount(self.inv, weights=mask.astype(float), minlength=self.g)
        boot = s[self.idx].sum(1) / np.maximum(c[self.idx].sum(1), 1)
        return float(d[mask].mean()), [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))]


def summarize(base_p, new_p, y, long, cl, mask_season=None):
    out = {}
    ms = np.ones(len(y), bool) if mask_season is None else mask_season
    for lab, m in (('all', ms), ('main', ms & long.is_main.to_numpy()), ('alt', ms & ~long.is_main.to_numpy())):
        for met, fn in (('brier', lambda p: (p - y) ** 2), ('logloss', lambda p: ll_loss(p, y))):
            pt, ci = cl.gain(fn(base_p) - fn(new_p), m)
            out[f'{lab}_{met}_gain'] = dict(point=pt, ci95=ci)
        out[f'{lab}_brier'] = float(((new_p - y) ** 2)[m].mean())
        out[f'{lab}_n'] = int(m.sum())
    return out


def walk_forward(market, variants, extra_models=None):
    frame = cm.load_frame()
    rows, long = cm.build_long(frame, market)
    base = base_from_v2(rows, market)
    blocks = feature_blocks(rows, market, base)
    y = long.y.to_numpy()
    idx, line = long.row.to_numpy(), long.line.to_numpy()
    seasons = long.season.to_numpy()
    team = rows.team.to_numpy()[idx]
    groups = np.array([f'{s}-{w}-{t}' for s, w, t in zip(seasons, long.week.to_numpy(), team)])
    cl = Clusters(groups)
    sub = {k: v[idx] for k, v in cm.model_params(rows, market, 'v2', POL).items()}
    p_champ = cm.p_over(sub, line, 'yards')
    sub_n = {k: v[idx] for k, v in cm.model_params(rows, market, 'naive', POL).items()}
    p_naive = cm.p_over(sub_n, line, 'yards')
    p_dep = p_champ.copy()
    if market in CALPOL['markets'] and CALPOL['markets'][market]['method'] == 'shrink_const':
        sp = CALPOL['markets'][market]['params']
        mean = rows['champ_' + market].to_numpy(float)[idx]
        band = np.abs(line - mean) <= 0.5 * mean
        p_dep = np.where(band, sp['w'] * p_champ + (1 - sp['w']) * sp['target'], p_champ)
    preds = {'champion': p_champ, 'deployed_cal': p_dep, 'naive_trailing': p_naive}
    thetas = {}
    for name, spec_fn in variants.items():
        p_all = np.full(len(y), np.nan)
        thetas[name] = {}
        for T in TESTS:
            tr, te = seasons < T, seasons == T
            rtr = rows.season.to_numpy() < T
            spec = spec_fn['spec']
            b = base
            bl = blocks
            if spec_fn.get('cond'):
                b, info = cond_base(rows[rtr].reset_index(drop=True), rows, market)
                bl = feature_blocks(rows, market, b)
                thetas[name].setdefault('cond_info', {})[T] = info
            if spec_fn.get('mean_fn'):
                b = spec_fn['mean_fn'](rows, T, base)
                bl = feature_blocks(rows, market, b)
            th = fit_spec(spec, long[tr], bl, b)
            rp = row_params(spec, th, bl, b)
            p_all[te] = prob_over(spec.shape, rp, idx[te], line[te])
            thetas[name][T] = dict(zip(spec.names(), [round(float(v), 4) for v in th]))
        preds[name] = p_all
    res = dict(n_rows=len(rows), n_long=len(long), thetas=thetas, results={})
    masks = {str(T): seasons == T for T in TESTS}
    masks['2023-24'] = np.isin(seasons, (2023, 2024))
    masks['2023-25'] = np.isin(seasons, TESTS)
    in_test = masks['2023-25']
    for name, p in preds.items():
        res['results'][name] = {}
        for lab, m in masks.items():
            r_c = summarize(p_champ, np.where(np.isnan(p), p_champ, p), y, long, cl, m)
            r_d = summarize(p_dep, np.where(np.isnan(p), p_dep, p), y, long, cl, m)
            res['results'][name][lab] = dict(vs_champion=r_c, vs_deployed=r_d)
    return res, dict(rows=rows, long=long, base=base, preds=preds, cl=cl, y=y, seasons=seasons)


def diagnostics(market):
    """Descriptive only (all seasons, no fitting): standardized-residual spread, zero-mass calibration, conditional vs unconditional mean ratio, by k bucket."""
    frame = cm.load_frame()
    rows = cm.eligible_rows(frame, market)
    b = base_from_v2(rows, market)
    act, y = rows[ACT[market]].to_numpy(float), rows['y_' + market].to_numpy(float)
    played = act > 0
    mc = b['M'] / (1 - b['p0'])
    mu = np.log(mc) - b['sig'] ** 2 / 2
    pos = played & (y > 0)
    z = np.where(pos, (np.log(np.where(y > 0, y, 1)) - mu) / b['sig'], np.nan)
    kb = pd.cut(rows.k, [-1, 0, 2, 5, 9, 99]).astype(str)
    df = pd.DataFrame(dict(kb=kb, season=rows.season, z=z, played=played, p0=b['p0'], zero=~played, y=y, M=b['M'], mc=mc, sig=b['sig']))
    out = {}
    for lab, g in list(df.groupby('kb')) + [('all', df)]:
        gp = g[g.played]
        out[lab] = dict(n=int(len(g)), z_sd_played_pos=float(np.nanstd(g.z)), z_mean=float(np.nanmean(g.z)), model_sig=float(g.sig.mean()), implied_sig_ratio=float(np.nanstd(g.z)),
                        p0_pred=float(g.p0.mean()), zero_obs=float(g.zero.mean()), ratio_uncond=float(g.y.sum() / g.M.sum()), ratio_cond=float(gp.y.sum() / gp.mc.mul(1).sum()) if len(gp) else None)
    out['_by_season_ratio_uncond'] = {int(s): float(g.y.sum() / g.M.sum()) for s, g in df.groupby('season')}
    return out


# ------------------------------------------------------------------------------------------------------------------------------ pass yards means
def qb_history_features(frame):
    qb = frame[(frame.position == 'QB') & frame.y_pass_yds.notna() & (frame.y_attempts >= 10)].sort_values(['player_id', 'season', 'week']).copy()
    # vectorised per player loop
    pid = qb.player_id.to_numpy()
    yv = qb.y_pass_yds.to_numpy(float)
    for a in (0.15, 0.3, 0.5):
        e = np.full(len(qb), np.nan)
        cur, last = np.nan, None
        for i in range(len(qb)):
            if pid[i] != last:
                cur, last = np.nan, pid[i]
            e[i] = cur
            cur = yv[i] if np.isnan(cur) else a * yv[i] + (1 - a) * cur
        qb['ewma%d' % int(a * 100)] = e
    # opponent pass-defence residual (strictly earlier games; relative to each QB's champion mean), shrunk toward 0 with 4 pseudo-games, reset each season with half carry-over
    qb['res'] = qb.y_pass_yds / qb.champ_pass_yds - 1
    qb = qb.sort_values(['season', 'week'])
    oa = np.zeros(len(qb))
    hist = {}
    carry = {}
    last_season = None
    keys = list(zip(qb.season, qb.week, qb.opponent, qb.res))
    # process week by week so same-week games never leak
    qb = qb.reset_index(drop=True)
    oa = np.zeros(len(qb))
    for (s, w), g in qb.groupby(['season', 'week'], sort=True):
        for i, opp in zip(g.index, g.opponent):
            sums, n = hist.get((s, opp), (0.0, 0))
            c_prev = carry.get(opp, 0.0)
            oa[i] = (sums + 4 * 0.5 * c_prev) / (n + 4)
        for i, opp, r in zip(g.index, g.opponent, g.res):
            sums, n = hist.get((s, opp), (0.0, 0))
            hist[(s, opp)] = (sums + (0 if np.isnan(r) else r), n + (0 if np.isnan(r) else 1))
        # carry-over refreshed at season end handled lazily below
        if w == g.week.max():
            pass
    # season carry (previous season's final shrunk opp residual) added in a second pass
    fin = {}
    for (s, opp), (sm, n) in hist.items():
        fin[(s, opp)] = sm / (n + 4)
    qb['oa_in'] = oa
    qb['oa_prev'] = [fin.get((s - 1, o), 0.0) for s, o in zip(qb.season, qb.opponent)]
    qb['oa'] = qb.oa_in
    return qb[['player_id', 'season', 'week', 'ewma15', 'ewma30', 'ewma50', 'oa', 'oa_prev']]


def pass_mean_study(market='pass_yds'):
    frame = cm.load_frame()
    rows = cm.eligible_rows(frame, market)
    h = qb_history_features(frame)
    rows = rows.merge(h, on=['player_id', 'season', 'week'], how='left')
    rows['prior_f'] = rows.prior_pass_yds
    out = {}
    y = rows.y_pass_yds.to_numpy(float)
    cands = {'champion': rows.champ_pass_yds, 'cur': rows.cur_pass_yds, 'prior': rows.prior_pass_yds, 'naive_equal_w': pd.Series(cm.equal_weight_mean(rows, market)),
             'ewma15': rows.ewma15, 'ewma30': rows.ewma30, 'ewma50': rows.ewma50}
    for c in (1, 2, 4, 8):
        cands[f'blend_c{c}'] = pd.Series(cm.blend(rows, market, c))
    ok = np.ones(len(rows), bool)
    for v in cands.values():
        ok &= ~np.isnan(np.asarray(v, float))
    for T in TESTS:
        te = (rows.season == T).to_numpy() & ok
        out[str(T)] = {nm: dict(rmse=float(np.sqrt(np.mean((np.asarray(v, float)[te] - y[te]) ** 2))), mae=float(np.mean(np.abs(np.asarray(v, float)[te] - y[te]))), bias_ratio=float(y[te].sum() / np.asarray(v, float)[te].sum())) for nm, v in cands.items()}
        out[str(T)]['n'] = int(te.sum())
    # regression weights (NNLS) fit on seasons < T
    feats = ['champ_pass_yds', 'cur_pass_yds', 'prior_pass_yds', 'ewma30']
    X = rows[feats].to_numpy(float)
    wts = {}
    for T in TESTS:
        tr = (rows.season < T).to_numpy() & ok
        w, _ = nnls(X[tr], y[tr])
        te = (rows.season == T).to_numpy() & ok
        pred = X[te] @ w
        wts[str(T)] = dict(weights=dict(zip(feats, [round(float(v), 3) for v in w])), rmse=float(np.sqrt(np.mean((pred - y[te]) ** 2))), mae=float(np.mean(np.abs(pred - y[te]))))
        # opponent adjustment second stage
        base_pred = X[tr] @ w
        A = np.column_stack([base_pred, base_pred * rows.oa.to_numpy(float)[tr]])
        g, _, _, _ = np.linalg.lstsq(A, y[tr], rcond=None)
        pred2 = (X[te] @ w) * (g[0] + g[1] * rows.oa.to_numpy(float)[te])
        wts[str(T)]['opp_stage'] = dict(g=[float(v) for v in g], rmse=float(np.sqrt(np.mean((pred2 - y[te]) ** 2))))
    out['nnls'] = wts
    # champion vs components correlation
    out['corr_champ_vs'] = {c: float(np.corrcoef(rows.champ_pass_yds[ok], rows[c][ok])[0, 1]) for c in ('cur_pass_yds', 'prior_pass_yds', 'ewma30')}
    out['champ_minus_equalw_mean'] = float((rows.champ_pass_yds - pd.Series(cm.equal_weight_mean(rows, market))).mean())
    out['champ_dev_by_k'] = {int(kk): float((g.champ_pass_yds - pd.Series(cm.equal_weight_mean(g, market), index=g.index)).mean()) for kk, g in rows.groupby(np.minimum(rows.k, 8))}
    return out, rows


def make_mean_fn(kind):
    """Return fn(rows, T, base) -> base override whose mean is an alternative QB pass-yards mean (weights fit on seasons < T)."""
    def fn(rows, T, base):
        frame = _FRAME
        h = _HIST
        r = rows[['player_id', 'season', 'week']].merge(h, on=['player_id', 'season', 'week'], how='left')
        y = rows.y_pass_yds.to_numpy(float)
        ew = np.where(np.isnan(r.ewma30.to_numpy(float)), rows.prior_pass_yds.to_numpy(float), r.ewma30.to_numpy(float))
        feats = np.column_stack([rows.champ_pass_yds, rows.cur_pass_yds, rows.prior_pass_yds, ew])
        feats = np.where(np.isnan(feats), rows.champ_pass_yds.to_numpy(float)[:, None], feats)
        tr = rows.season.to_numpy() < T
        if kind == 'equalw':
            mean = cm.equal_weight_mean(rows, 'pass_yds')
        elif kind == 'ewma':
            mean = ew
        elif kind == 'nnls':
            w, _ = nnls(feats[tr], y[tr])
            mean = feats @ w
        elif kind == 'nnls_opp':
            w, _ = nnls(feats[tr], y[tr])
            bp = feats @ w
            oa = np.nan_to_num(r.oa.to_numpy(float))
            A = np.column_stack([bp[tr], bp[tr] * oa[tr]])
            g = np.linalg.lstsq(A, y[tr], rcond=None)[0]
            mean = bp * (g[0] + g[1] * oa)
        mean = np.where(np.isfinite(mean) & (mean > 20), mean, rows.champ_pass_yds.to_numpy(float))
        sig = base['sig']  # lognormal CV kept as the Champion's own (ps/pm), so only the mean moves
        return dict(M=mean, sig=sig, p0=base['p0'])
    return fn


_FRAME = None
_HIST = None


def final_fit(market, V, ctx):
    """Parameters of every variant fit on ALL seasons 2021-2025 (the production candidate) with the 2026 mean_fn weights, plus the centering constants."""
    rows, long, base = ctx['rows'], ctx['long'], ctx['base']
    out = {'center_log_mean': float(CENTER[market]), 'sig_ref': 0.8, 'p0_logit_shift': 1.5}
    for name, v in V.items():
        b, bl = base, feature_blocks(rows, market, base)
        if v.get('cond'):
            continue
        if v.get('mean_fn'):
            b = v['mean_fn'](rows, 2026, base)
            bl = feature_blocks(rows, market, b)
        th = fit_spec(v['spec'], long, bl, b)
        out[name] = dict(zip(v['spec'].names(), [round(float(x), 4) for x in th]))
    return out


def run(market):
    global _FRAME, _HIST
    pos_blocks = ['te', 'rb'] if market == 'rec_yds' else []
    mean_k = ['a', 'b', 'k0', 'klow']
    sig_all = ['s0', 's_lM', 's_ls0', 's_k0', 's_klow', 's_inv', 's_cvs'] + ['s_' + p for p in pos_blocks]
    sig_nocvs = [s for s in sig_all if s != 's_cvs']
    mean_all = mean_k + ['m_' + p for p in pos_blocks]
    p0k = ['d0', 'd1', 'dk0']
    if market == 'pass_yds':
        sig_all = [s for s in sig_all if s != 's_cvs']
        sig_nocvs = sig_all
    V = {
        'sig_const': dict(spec=Spec(sig=['s0'])),
        'sig_s0_ls0': dict(spec=Spec(sig=['s0', 's_ls0'])),
        'mean_only': dict(spec=Spec(mean=mean_all)),
        'mean_plus_sigconst': dict(spec=Spec(mean=mean_all, sig=['s0'])),
        'sig_full': dict(spec=Spec(sig=sig_all)),
        'sig_full_nocvs': dict(spec=Spec(sig=sig_nocvs)),
        'all': dict(spec=Spec(mean=mean_all, sig=sig_all, p0=p0k)),
        'all_nocvs': dict(spec=Spec(mean=mean_all, sig=sig_nocvs, p0=p0k)),
        'all_gamma': dict(spec=Spec(mean=mean_all, sig=sig_all, p0=p0k, shape='gamma')),
        'all_mix': dict(spec=Spec(mean=mean_all, sig=sig_all, p0=p0k, shape='mix')),
        'cond_sigfull': dict(spec=Spec(sig=sig_all), cond=True),
    }
    if market == 'rec_yds':
        V['lite'] = dict(spec=Spec(mean=['a', 'b', 'm_te', 'm_rb'], sig=['s0', 's_lM', 's_cvs', 's_k0', 's_te', 's_rb'], p0=['d0', 'd1']))
    if market == 'rush_yds':
        V['lite'] = dict(spec=Spec(mean=['a', 'b', 'k0', 'klow'], sig=['s0', 's_lM', 's_ls0', 's_cvs', 's_k0'], p0=['d0', 'd1']))
    if market == 'pass_yds':
        V = {k: v for k, v in V.items() if k not in ('cond_sigfull', 'sig_full_nocvs', 'all_nocvs')}
        for k in list(V):
            if V[k]['spec'].p0:
                V[k]['spec'] = Spec(mean=V[k]['spec'].mean, sig=V[k]['spec'].sig, p0=(), shape=V[k]['spec'].shape)
        frame = cm.load_frame()
        _FRAME, _HIST = frame, qb_history_features(frame)
        for nm in ('equalw', 'ewma', 'nnls', 'nnls_opp'):
            V[f'mean_{nm}_rawsig'] = dict(spec=Spec(), mean_fn=make_mean_fn(nm))
            V[f'mean_{nm}_sigfull'] = dict(spec=Spec(sig=sig_all), mean_fn=make_mean_fn(nm))
            V[f'mean_{nm}_sigfull_corr'] = dict(spec=Spec(mean=['a', 'b'], sig=sig_all), mean_fn=make_mean_fn(nm))
            V[f'mean_{nm}_lite'] = dict(spec=Spec(mean=['a', 'b'], sig=['s0', 's_lM', 's_ls0']), mean_fn=make_mean_fn(nm))
        V['lite'] = dict(spec=Spec(mean=['a', 'b'], sig=['s0', 's_lM', 's_ls0']))
    res, ctx = walk_forward(market, V)
    res['final_fit'] = final_fit(market, V, ctx)
    res['diagnostics'] = diagnostics(market)
    if market == 'pass_yds':
        res['pass_mean_study'], _ = pass_mean_study()
    (HERE / f'results_{market}.json').write_text(json.dumps(res, indent=1, default=float), encoding='utf-8')
    return res


def table(res, lab='2023-25', ref='vs_champion'):
    lines = []
    for name, d in res['results'].items():
        r = d[lab][ref]
        f = lambda k: '%+.4f [%+.4f,%+.4f]' % (r[k]['point'], *r[k]['ci95'])
        lines.append(f"{name:28s} all_B {f('all_brier_gain')} | all_LL {f('all_logloss_gain')} | main_B {f('main_brier_gain')} | alt_B {f('alt_brier_gain')}")
    return '\n'.join(lines)


if __name__ == '__main__':
    markets = sys.argv[1:] or ['rec_yds', 'rush_yds', 'pass_yds']
    for m in markets:
        r = run(m)
        print('=====', m, 'rows', r['n_rows'], 'long', r['n_long'])
        for lab in ('2023', '2024', '2025', '2023-24', '2023-25'):
            print('--', lab, 'vs champion (gain>0 = better)')
            print(table(r, lab))
        if m == 'pass_yds':
            print('-- 2025 vs deployed')
            print(table(r, '2025', 'vs_deployed'))
