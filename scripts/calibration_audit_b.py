"""Auditor B: calibration audit of the Champion (v1/v2) at realistic lines, with chronologically honest correction tests.

Stages (run in this order; the 2025 holdout is not loaded until `final`, which reads the frozen selection written by `select`):
  python scripts/calibration_audit_b.py diag     # baseline metrics + root-cause diagnostics on 2021-2024 only
  python scripts/calibration_audit_b.py select   # fit corrections on 2021-23, tune/select on 2024 only -> research/calibration/B/selection_2024.json
  python scripts/calibration_audit_b.py final    # score the frozen selection ONCE on 2025, refit on 2021-24 for deployment -> config/calibration_candidates.json

Read-only with respect to the product: it writes only under research/calibration/B and config/calibration_candidates.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_models as cm  # noqa: E402

OUT = cm.REPO / 'research' / 'calibration' / 'B'
CANDIDATES = cm.REPO / 'config' / 'calibration_candidates.json'
VERSION = 'cal-b-2026.10.09-v1'
DRAWS = 300
SIMPLICITY = ['raw', 'platt', 'shrink_const', 'shrink_base', 'pooled_platt', 'isotonic', 'dist_var', 'dist_var_zero', 'dist_mean_var', 'dist_shrink_var', 'dist_mean_var_zero']


def jdump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o)), encoding='utf-8')


# ------------------------------------------------------------------------------------------------------------------------------------------ context
def prepare(max_season):
    frame = cm.load_frame()
    frame = frame[frame.season <= max_season]
    ctx = {}
    for m in cm.MARKETS:
        rows, long = cm.build_long(frame, m)
        probs = cm.long_probs(rows, long, m)
        long = long.assign(p_v1=probs['v1'], p_v2=probs['v2'], p_naive=probs['naive'])
        params = cm.row_params_long(rows, long, m, 'v2')
        pos_mean = rows[rows.season.isin(cm.DEV)].groupby('position')['y_' + m].mean().to_dict()
        if cm.MARKETS[m]['kind'] == 'count':
            params['pos_lam'] = long.position.map(pos_mean).to_numpy(float)
        ctx[m] = dict(rows=rows, long=long, params=params, kind=cm.MARKETS[m]['kind'], pos_mean=pos_mean)
    return ctx


def split_mask(long, seasons):
    return long.season.isin(seasons).to_numpy()


def cell(p, y, groups, base_p=None, draws=DRAWS):
    return cm.bootstrap_metrics(p, y, groups, draws=draws, base_p=base_p)


def favored_side(p, y):
    """Per favored-side buckets (the side a bettor would take: the more likely one)."""
    fav_over = p >= 0.5
    pf = np.where(fav_over, p, 1 - p)
    yf = np.where(fav_over, y, 1 - y)
    out = []
    for side, mask in (('Over', fav_over), ('Under', ~fav_over)):
        for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)):
            sel = mask & (pf >= lo) & (pf < hi)
            if sel.sum() >= 20:
                out.append({'side': side, 'bucket': f'{lo:.1f}-{min(hi, 1):.1f}', 'n': int(sel.sum()), 'mean_p': float(pf[sel].mean()), 'win_rate': float(yf[sel].mean()),
                            'brier': float(((pf[sel] - yf[sel]) ** 2).mean())})
    return out


# --------------------------------------------------------------------------------------------------------------------------------------- diagnostics
def mean_of(params, kind):
    if kind == 'count':
        return params['lam']
    return (1 - params['p0']) * np.exp(params['mu'] + params['sig'] ** 2 / 2)


def group_bias(df, by, edges=None):
    d = df.copy()
    if edges is not None:
        d['g'] = pd.cut(d[by], edges, include_lowest=True).astype(str)
    else:
        d['g'] = d[by].astype(str)
    res = []
    for g, s in d.groupby('g'):
        if len(s) >= 150:
            res.append({'group': g, 'n': int(len(s)), 'mean_pred': float(s.pred.mean()), 'mean_obs': float(s.obs.mean()), 'bias_pct': float(100 * (s.pred.mean() - s.obs.mean()) / max(s.obs.mean(), 1e-9))})
    return res


def row_diagnostics(c, market, seasons):
    kind = c['kind']
    rows = c['rows']
    sel = rows.season.isin(seasons).to_numpy()
    r = rows[sel].reset_index(drop=True)
    params = cm.model_params(r, market, 'v2')
    v1 = cm.model_params(r, market, 'v1')
    pred = mean_of(params, kind)
    obs = r['y_' + market].to_numpy(float)
    df = pd.DataFrame({'pred': pred, 'obs': obs, 'pred_v1': mean_of(v1, kind), 'position': r.position, 'k': r.k, 'n': r.n, 'season': r.season, 'week': r.week,
                       'tshare': r.trend_target_share, 'cshare': r.trend_carry_share})
    diag = {'n_rows': int(len(r)), 'mean_pred_v2': float(pred.mean()), 'mean_pred_v1': float(df.pred_v1.mean()), 'mean_obs': float(obs.mean()),
            'bias_pct_v2': float(100 * (pred.mean() - obs.mean()) / obs.mean()), 'bias_pct_v1': float(100 * (df.pred_v1.mean() - obs.mean()) / obs.mean())}
    diag['bias_by_position'] = group_bias(df, 'position')
    diag['bias_by_k_current_games'] = group_bias(df, 'k', [-1, 0, 2, 5, 8, 12])
    diag['bias_by_season'] = group_bias(df, 'season')
    diag['bias_by_week'] = group_bias(df, 'week', [0, 3, 6, 10, 14, 18])
    q = np.unique(np.quantile(df.pred, [0, .25, .5, .75, 1]))
    diag['bias_by_predicted_level'] = group_bias(df, 'pred', q)
    if market in ('receptions', 'rec_yds', 'rec_tds', 'atd'):
        diag['bias_by_target_share_trend'] = group_bias(df.dropna(subset=['tshare']), 'tshare', [-1, -0.04, -0.01, 0.01, 0.04, 1])
    if market in ('rush_yds', 'rush_tds'):
        diag['bias_by_carry_share_trend'] = group_bias(df.dropna(subset=['cshare']), 'cshare', [-1, -0.08, -0.02, 0.02, 0.08, 1])
    # distribution shape
    if kind == 'count':
        lam = params['lam']
        d = pd.DataFrame({'lam': lam, 'y': obs})
        d['b'] = pd.qcut(d.lam, 4, duplicates='drop').astype(str)
        shape = []
        for b, s in d.groupby('b'):
            resid2 = ((s.y - s.lam) ** 2).mean()
            shape.append({'lam_bucket': b, 'n': int(len(s)), 'mean_lam': float(s.lam.mean()), 'obs_mean': float(s.y.mean()), 'obs_var_about_pred': float(resid2), 'poisson_var': float(s.lam.mean()),
                          'var_ratio': float(resid2 / s.lam.mean()), 'phi_hat': float((((s.y - s.lam) ** 2 - s.lam).mean()) / (s.lam ** 2).mean())})
        diag['dispersion'] = shape
        from scipy.stats import poisson
        diag['p_zero'] = {'predicted': float(poisson.pmf(0, lam).mean()), 'observed': float((obs == 0).mean())}
        diag['tails'] = {f'P(y >= {t} x ceil(mean))': {'pred': float(poisson.sf(np.ceil(lam * t) - 1, lam).mean()), 'obs': float((obs >= np.ceil(lam * t)).mean())} for t in (1.5, 2.0, 3.0)
                         if t * lam.mean() >= 1}
    else:
        mu, sig, p0 = params['mu'], params['sig'], params['p0']
        pos = obs >= 1
        z = (np.log(np.maximum(obs, 1)) - mu) / sig
        diag['lognormal'] = {'pred_sigma_mean': float(sig.mean()), 'obs_sd_z_on_positive': float(z[pos].std()), 'obs_mean_z_on_positive': float(z[pos].mean()),
                             'implied_sigma_multiplier': float(z[pos].std()), 'pred_zero_mass': float(p0.mean()), 'obs_nonpositive': float((~pos).mean())}
        by_pos = []
        for p_, s in pd.DataFrame({'pos': r.position, 'z': z, 'ok': pos, 'p0': p0, 'sig': sig}).groupby('pos'):
            by_pos.append({'position': p_, 'n': int(len(s)), 'pred_zero': float(s.p0.mean()), 'obs_zero': float((~s.ok).mean()), 'pred_sigma': float(s.sig.mean()),
                           'obs_sd_z': float(s.z[s.ok].std()), 'mean_z': float(s.z[s.ok].mean())})
        diag['lognormal_by_position'] = by_pos
        from scipy.stats import norm
        tails = {}
        for t in (1.5, 2.0, 3.0):
            xline = np.floor(t * mean_of(params, kind)) + 0.5
            pr = (1 - p0) * norm.sf((np.log(xline) - mu) / sig)
            tails[f'P(y > {t} x mean)'] = {'pred': float(pr.mean()), 'obs': float((obs > xline).mean())}
        diag['tails'] = tails
    return diag


def line_selection(c, seasons):
    long = c['long'][split_mask(c['long'], seasons)]
    out = {}
    p = long.p_v2.to_numpy()
    y = long.y.to_numpy()
    pf = np.where(p >= 0.5, p, 1 - p)
    yf = np.where(p >= 0.5, y, 1 - y)
    side = np.where(p >= 0.5, 'Over', 'Under')
    absoff = np.abs(long.off.to_numpy())
    out['share_of_all_predictions_with_pfav_gt_0.85'] = float((pf > 0.85).mean())
    out['share_of_main_line_predictions_with_pfav_gt_0.85'] = float((pf[long.is_main.to_numpy()] > 0.85).mean())
    hi = pf > 0.85
    out['n_gt_0.85'] = int(hi.sum())
    if hi.sum():
        out['gt_0.85_win_rate'] = float(yf[hi].mean())
        out['gt_0.85_mean_p'] = float(pf[hi].mean())
        out['gt_0.85_share_main_line'] = float(long.is_main.to_numpy()[hi].mean())
        out['gt_0.85_share_by_side'] = {s: float((side[hi] == s).mean()) for s in ('Over', 'Under')}
        out['gt_0.85_share_by_abs_offset'] = {str(o): float((absoff[hi] == o).mean()) for o in sorted(set(absoff[hi]))}
        by = []
        for s in ('Over', 'Under'):
            for lo_, hi_ in ((0, 0), (1, 1), (2, 2), (3, 9)):
                m = hi & (side == s) & (absoff >= lo_) & (absoff <= hi_)
                if m.sum() >= 15:
                    by.append({'side': s, 'abs_offset': f'{lo_}' if lo_ == hi_ else f'{lo_}+', 'n': int(m.sum()), 'mean_p': float(pf[m].mean()), 'win_rate': float(yf[m].mean())})
        out['gt_0.85_by_side_and_offset'] = by
        line = long.line.to_numpy()
        out['gt_0.85_median_line'] = float(np.median(line[hi]))
        out['gt_0.85_share_line_le_1.5_or_4.5'] = float((line[hi] <= (1.5 if c['kind'] == 'count' else 4.5)).mean())
    out['calibration_main_line_only'] = cm.point_metrics(p[long.is_main.to_numpy()], y[long.is_main.to_numpy()])
    if (~long.is_main.to_numpy()).sum() > 50:
        out['calibration_ladder_only'] = cm.point_metrics(p[~long.is_main.to_numpy()], y[~long.is_main.to_numpy()])
    by_off = []
    for o in sorted(long.off.unique()):
        m = long.off.to_numpy() == o
        if m.sum() >= 200:
            mm = cm.point_metrics(p[m], y[m])
            by_off.append({'offset': int(o), 'n': int(m.sum()), 'mean_p_over': mm['mean_p'], 'rate_over': mm['rate'], 'slope': mm['slope'], 'brier': mm['brier']})
    out['by_ladder_offset'] = by_off
    return out


def disagreement_test(c, seasons):
    """Proxy for 'the pick is where the model disagrees with the market': market := naive trailing-mean model. Select rows by signed disagreement and compare outcomes."""
    long = c['long'][split_mask(c['long'], seasons)]
    p, q, y = long.p_v2.to_numpy(), long.p_naive.to_numpy(), long.y.to_numpy()
    d = p - q
    res = {}
    for name, m in (('model > naive by >=0.10 (over)', d >= 0.10), ('model < naive by >=0.10 (under)', d <= -0.10), ('abs gap >= 0.05', np.abs(d) >= 0.05)):
        if m.sum() >= 50:
            res[name] = {'n': int(m.sum()), 'mean_p_model': float(p[m].mean()), 'mean_p_naive': float(q[m].mean()), 'over_rate': float(y[m].mean())}
    x = np.column_stack([cm.logit(p), cm.logit(q)])
    # logistic with both logits: how much weight the data puts on the model vs the naive trailing mean
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(C=1e6, max_iter=500).fit(x, y)
    res['logit(y) ~ a + b_model*logit(p_v2) + b_naive*logit(p_naive)'] = {'a': float(lr.intercept_[0]), 'b_model': float(lr.coef_[0][0]), 'b_naive': float(lr.coef_[0][1])}
    return res


def baseline_cells(c, market, base_table, overall, seasons, draws=DRAWS):
    long = c['long']
    m = split_mask(long, seasons)
    l = long[m]
    y, g = l.y.to_numpy(), l.player_id.to_numpy()
    base = cm.base_rate_apply(l.line.to_numpy(), base_table, overall)
    out = {}
    pv2 = l.p_v2.to_numpy()
    for subset, mask in (('all_lines', np.ones(len(l), bool)), ('main_line', l.is_main.to_numpy())):
        s = {}
        s['v2'] = cell(pv2[mask], y[mask], g[mask], base_p=None, draws=draws)
        for name, p in (('v1', l.p_v1.to_numpy()), ('naive_trailing_mean', l.p_naive.to_numpy()), ('base_rate_by_line', base)):
            s[name] = {'point': cm.point_metrics(p[mask], y[mask]), 'v2_gain_over_this': {'brier': cm.paired_brier_gain(p[mask], pv2[mask], y[mask], g[mask])}}
        s['reliability_over_p_v2'] = cm.reliability(pv2[mask], y[mask])
        s['favored_side_buckets_v2'] = favored_side(pv2[mask], y[mask])
        s['skill_vs_base_rate_brier'] = float(1 - s['v2']['point']['brier'] / s['base_rate_by_line']['point']['brier'])
        out[subset] = s
    return out


def stage_diag():
    ctx = prepare(2024)
    res = {'commit': 'see git', 'seasons_used': '2021-2024 (2025 holdout not loaded)', 'markets': {}}
    for market, c in ctx.items():
        dev = split_mask(c['long'], cm.DEV)
        table, overall = cm.base_rate_table(c['long'].line.to_numpy()[dev], c['long'].y.to_numpy()[dev])
        res['markets'][market] = {
            'rows_dev': int(c['rows'].season.isin(cm.DEV).sum()), 'rows_val': int(c['rows'].season.isin(cm.VAL).sum()),
            'line_counts_val': {'long_rows': int(split_mask(c['long'], cm.VAL).sum())},
            'dev_2021_23': baseline_cells(c, market, table, overall, cm.DEV, draws=150),
            'val_2024': baseline_cells(c, market, table, overall, cm.VAL),
            'diagnostics_2021_24': row_diagnostics(c, market, cm.DEV + cm.VAL),
            'line_selection_2021_24': line_selection(c, cm.DEV + cm.VAL),
            'disagreement_vs_naive_2021_24': disagreement_test(c, cm.DEV + cm.VAL)}
        print('diag', market, flush=True)
    res['sensitivity_to_eligibility_floor_val_2024'] = sensitivity()
    res['live_tracker_high_confidence'] = live_tracker_summary()
    jdump(OUT / 'baseline_diagnostics.json', res)
    jdump(OUT / 'line_grid.json', line_grid())


def sensitivity():
    frame = cm.load_frame()
    frame = frame[frame.season <= 2024]
    out = {}
    for market, spec in cm.MARKETS.items():
        out[market] = {}
        for label, floor in (('no_floor', 0.0), ('default', None), ('2x_floor', spec['floor'] * 2)):
            rows, long = cm.build_long(frame, market, floor)
            probs = cm.long_probs(rows, long, market, models=('v2',))
            val = (long.season == 2024).to_numpy()
            if val.sum() < 200:
                continue
            m = cm.point_metrics(probs['v2'][val], long.y.to_numpy()[val])
            out[market][label] = {'n_rows_val': int((rows.season == 2024).sum()), 'brier': m['brier'], 'slope': m['slope'], 'intercept': m['intercept'], 'ece': m['ece'], 'mean_p': m['mean_p'], 'rate': m['rate']}
    return out


def line_grid():
    d = json.loads((cm.REPO / 'data' / 'nfl_betting.json').read_text(encoding='utf-8'))
    out = {}
    for market in ('receptions', 'rec_yds', 'rush_yds', 'pass_yds', 'pass_tds', 'rush_tds', 'atd'):
        lines = np.array([r['line'] for r in d['props'] if r['market'] == market and r.get('line') is not None], float)
        if not len(lines):
            continue
        vals, cnt = np.unique(lines, return_counts=True)
        out[market] = {'quotes': int(len(lines)), 'min': float(lines.min()), 'median': float(np.median(lines)), 'max': float(lines.max()),
                       'share_ending_4.5_mod5': float(np.mean(np.isclose(lines % 5, 4.5))), 'top_lines': {str(v): int(c) for v, c in sorted(zip(vals, cnt), key=lambda t: -t[1])[:8]}}
    return out


def live_tracker_summary():
    """Aggregate view of settled live predictions (no personal data): where the >0.85 probabilities come from. The tracker file is in the repo."""
    d = json.loads((cm.REPO / 'data' / 'signal_tracker.json').read_text(encoding='utf-8'))
    rows = []
    for r in d['records']:
        f = r.get('features') or {}
        o = (r.get('outcome') or {}).get('values') or {}
        if 'probability' not in f or o.get('status') not in ('win', 'loss') or f.get('projection_mean') is None or 'line' not in f:
            continue
        rows.append({'fam': r['signal_family'], 'market': f['market'], 'side': f['side'], 'line': f['line'], 'mean': f['projection_mean'], 'sd': f.get('projection_sd'), 'p': f['probability'],
                     'y': 1 if o['status'] == 'win' else 0, 'pid': (r.get('entity') or {}).get('id')})
    df = pd.DataFrame(rows)
    df = df[df.market.isin(['player_receptions', 'player_receiving_yards', 'player_rushing_yards', 'player_passing_yards', 'player_passing_tds'])]
    df['ratio'] = df.line / df['mean'].clip(lower=0.25)
    out = {'n_settled_player_props': int(len(df))}
    for name, s in (('all', df), ('p>0.85', df[df.p > 0.85]), ('p<=0.85', df[df.p <= 0.85])):
        out[name] = {'n': int(len(s)), 'mean_p': float(s.p.mean()), 'win_rate': float(s.y.mean()), 'median_line_over_mean': float(s.ratio.median()),
                     'share_line_over_mean_outside_0.6_1.5': float(((s.ratio < 0.6) | (s.ratio > 1.5)).mean()), 'share_line_le_4.5': float((s.line <= 4.5).mean()),
                     'share_under': float((s.side == 'Under').mean()), 'unique_players': int(s.pid.nunique())}
    hi = df[df.p > 0.85]
    out['p>0.85_by_market'] = {k: {'n': int(len(s)), 'win_rate': float(s.y.mean()), 'mean_p': float(s.p.mean())} for k, s in hi.groupby('market')}
    return out


# --------------------------------------------------------------------------------------------------------------------------------------- correction
def fit_all(ctx, fit_seasons):
    """Fit every correction on `fit_seasons` rows. Returns {market: {method: spec}} plus pooled specs for given kappas."""
    specs, pooled_inputs = {}, {}
    for market, c in ctx.items():
        long = c['long']
        m = split_mask(long, fit_seasons)
        l = long[m]
        p, y = l.p_v2.to_numpy(), l.y.to_numpy()
        s = {'raw': {'method': 'raw'}}
        s['platt'] = cm.platt_fit(p, y)
        s['isotonic'] = cm.iso_fit(p, y)
        table, overall = cm.base_rate_table(l.line.to_numpy(), y)
        base = cm.base_rate_apply(l.line.to_numpy(), table, overall)
        s['shrink_base'] = {**cm.shrink_fit(p, y, base), 'table': {str(k): v for k, v in table.items()}, 'overall': overall}
        const = np.full_like(p, overall)
        s['shrink_const'] = {**cm.shrink_fit(p, y, const), 'method': 'shrink_const', 'overall': overall}
        params = {k: v[m] for k, v in c['params'].items()}
        variants = ['var', 'mean_var', 'shrink_var'] if c['kind'] == 'count' else ['var', 'var_zero', 'mean_var_zero']
        for v in variants:
            if c['kind'] == 'count' and market in ('rush_tds', 'rec_tds', 'atd') and v == 'mean_var':
                pass
            s['dist_' + v] = cm.dist_fit(c['kind'], params, l.line.to_numpy(), y, v)
        specs[market] = s
        pooled_inputs[market] = (p, y)
    return specs, pooled_inputs


def apply_method(c, market, spec, mask):
    long = c['long']
    l = long[mask]
    p = l.p_v2.to_numpy()
    meth = spec['method']
    if meth == 'raw':
        return p
    if meth in ('platt', 'pooled_platt'):
        return cm.platt_apply(p, spec)
    if meth == 'isotonic':
        return cm.iso_apply(p, spec)
    if meth == 'shrink_const':
        return cm.shrink_apply(p, spec['overall'], spec)
    if meth == 'shrink_base':
        table = {float(k): v for k, v in spec['table'].items()}
        base = cm.base_rate_apply(l.line.to_numpy(), table, spec['overall'])
        return cm.shrink_apply(p, base, spec)
    if meth.startswith('dist_'):
        params = {k: v[mask] for k, v in c['params'].items()}
        return cm.dist_apply(c['kind'], params, l.line.to_numpy(), spec)
    raise ValueError(meth)


def stage_select():
    ctx = prepare(2024)
    specs, pooled_inputs = fit_all(ctx, cm.DEV)
    # hierarchical pooling: tune kappa on 2024 total log loss
    kappas = [0, 30, 100, 300, 1000, 3000, 10000, 30000]
    best_kappa, best_ll = None, None
    tune = {}
    for kappa in kappas:
        pm = cm.pooled_fit(pooled_inputs, kappa)
        tot = 0.0
        for market, c in ctx.items():
            mv = split_mask(c['long'], cm.VAL)
            p = apply_method(c, market, pm[market], mv)
            y = c['long'].y.to_numpy()[mv]
            tot += cm.point_metrics(p, y)['logloss'] * mv.sum()
        tot /= sum(split_mask(c['long'], cm.VAL).sum() for c in ctx.values())
        tune[kappa] = tot
        if best_ll is None or tot < best_ll:
            best_ll, best_kappa = tot, kappa
    pooled = cm.pooled_fit(pooled_inputs, best_kappa)
    for market in ctx:
        specs[market]['pooled_platt'] = pooled[market]
    result = {'fit_window': '2021-2023', 'tuned_on': '2024', 'pooled_kappa_tuning_logloss': tune, 'pooled_kappa': best_kappa, 'markets': {}}
    for market, c in ctx.items():
        long = c['long']
        mv = split_mask(long, cm.VAL)
        l = long[mv]
        y, g = l.y.to_numpy(), l.player_id.to_numpy()
        raw = l.p_v2.to_numpy()
        rows = {}
        for name, spec in specs[market].items():
            p = apply_method(c, market, spec, mv)
            cc = cm.bootstrap_metrics(p, y, g, draws=DRAWS, base_p=None if name == 'raw' else raw)
            main = l.is_main.to_numpy()
            rows[name] = {'val_2024_all_lines': cc, 'val_2024_main_line': cm.point_metrics(p[main], y[main]), 'spec': spec if name != 'shrink_base' else {**spec, 'table': '...'}}
            if name != 'raw':
                rows[name]['paired_brier_gain'] = cm.paired_brier_gain(raw, p, y, g)
        # choose: lowest 2024 log loss, then simplest within 0.0003 of it; separately for deployable probability maps and distribution fixes
        def choose(names):
            lls = {n: rows[n]['val_2024_all_lines']['point']['logloss'] for n in names}
            best = min(lls.values())
            for n in sorted(names, key=SIMPLICITY.index):
                if lls[n] <= best + 3e-4:
                    return n
        prob_names = [n for n in rows if n in ('raw', 'platt', 'isotonic', 'shrink_const', 'pooled_platt')]  # shrink_base (line-position prior) is a benchmark only: it is undefined off-grid
        dist_names = [n for n in rows if n.startswith('dist_')]
        result['markets'][market] = {'methods': rows, 'selected_probability_map': choose(prob_names), 'selected_distribution_fix': choose(dist_names)}
        print('select', market, result['markets'][market]['selected_probability_map'], result['markets'][market]['selected_distribution_fix'], flush=True)
    # store full specs for the final stage (frozen)
    result['specs'] = specs
    jdump(OUT / 'selection_2024.json', result)


# ------------------------------------------------------------------------------------------------------------------------------------------ final
def recommendation(v24, v25, name):
    """Pre-stated rule. PROMOTE: Brier gain CI excludes zero on BOTH 2024 and 2025, slope within [0.90, 1.10] on 2025, ECE and log loss not worse, main-line Brier not worse.
    REJECT: 2025 Brier worse than raw. Otherwise SHADOW."""
    if name == 'raw':
        return 'NO CORRECTION NEEDED' if abs(v25['slope'] - 1) <= 0.1 else 'SHADOW'
    g24, g25 = v24['paired_brier_gain'], v25['paired_brier_gain']
    if g25['point'] < 0:
        return 'REJECT'
    ok = g24['ci95'][0] > 0 and g25['ci95'][0] > 0 and 0.9 <= v25['slope'] <= 1.1 and v25['ece_gain'] >= 0 and v25['logloss_gain'] >= 0 and v25['main_brier_gain'] >= 0
    return 'PROMOTE' if ok else 'SHADOW'


def stage_final():
    sel = json.loads((OUT / 'selection_2024.json').read_text(encoding='utf-8'))
    ctx = prepare(2025)
    specs24 = sel['specs']
    res = {'frozen_selection': 'selection_2024.json (written before 2025 was loaded)', 'markets': {}}
    cand = {}
    refit_specs, _ = fit_all(ctx, cm.DEV + cm.VAL)
    refit_pooled_inputs = {m: (c['long'][split_mask(c['long'], cm.DEV + cm.VAL)].p_v2.to_numpy(), c['long'][split_mask(c['long'], cm.DEV + cm.VAL)].y.to_numpy()) for m, c in ctx.items()}
    refit_pooled = cm.pooled_fit(refit_pooled_inputs, sel['pooled_kappa'])
    for market, c in ctx.items():
        long = c['long']
        mh, mv = split_mask(long, cm.HOLD), split_mask(long, cm.VAL)
        lh = long[mh]
        y, g = lh.y.to_numpy(), lh.player_id.to_numpy()
        raw = lh.p_v2.to_numpy()
        main = lh.is_main.to_numpy()
        info = sel['markets'][market]
        base_table = {float(k): v for k, v in specs24[market]['shrink_base']['table'].items()}
        base_p = cm.base_rate_apply(lh.line.to_numpy(), base_table, specs24[market]['shrink_base']['overall'])
        entry = {'n_rows_2025': int(len(lh)), 'n_main_lines_2025': int(main.sum()),
                 'baselines_2025': {'v2_raw': cm.bootstrap_metrics(raw, y, g, draws=DRAWS),
                                    'v1': cm.point_metrics(lh.p_v1.to_numpy(), y), 'naive_trailing_mean': cm.point_metrics(lh.p_naive.to_numpy(), y),
                                    'base_rate_by_line_2021_23': cm.point_metrics(base_p, y)},
                 'v2_vs_v1_brier_gain': cm.paired_brier_gain(lh.p_v1.to_numpy(), raw, y, g),
                 'v2_vs_naive_brier_gain': cm.paired_brier_gain(lh.p_naive.to_numpy(), raw, y, g),
                 'v2_vs_base_rate_brier_gain': cm.paired_brier_gain(base_p, raw, y, g),
                 'reliability_v2_raw': cm.reliability(raw, y), 'favored_side_v2_raw': favored_side(raw, y), 'line_selection_2025': line_selection(c, cm.HOLD)}
        entry['methods'] = {}
        for kind_name, name in (('probability_map', info['selected_probability_map']), ('distribution_fix', info['selected_distribution_fix'])):
            spec = specs24[market][name]
            p = apply_method(c, market, spec, mh)
            full = cm.bootstrap_metrics(p, y, g, draws=DRAWS, base_p=raw)
            v24 = info['methods'][name]
            raw_main, p_main = cm.point_metrics(raw[main], y[main]), cm.point_metrics(p[main], y[main])
            summary = {'selected_for': kind_name, 'method': name, 'holdout_2025_all_lines': full, 'holdout_2025_main_line': p_main, 'raw_main_line': raw_main,
                       'paired_brier_gain': cm.paired_brier_gain(raw, p, y, g), 'segments': segment_gains(lh, raw, p, y)}
            summary['favored_side_buckets_calibrated'] = favored_side(p, y)
            summary['slope'] = full['point']['slope']
            summary['ece_gain'] = entry['baselines_2025']['v2_raw']['point']['ece'] - full['point']['ece']
            summary['logloss_gain'] = entry['baselines_2025']['v2_raw']['point']['logloss'] - full['point']['logloss']
            summary['main_brier_gain'] = raw_main['brier'] - p_main['brier']
            summary['recommendation'] = recommendation(v24, summary, name)
            entry['methods'][kind_name] = summary
        entry['recommendation'] = entry['methods']['probability_map']['recommendation']
        res['markets'][market] = entry
        # deployment candidate: parameters refit on 2021-2024 for the selected probability map (same family; not scored on 2025)
        name = info['selected_probability_map']
        dep = refit_pooled[market] if name == 'pooled_platt' else refit_specs[market][name]
        dname = info['selected_distribution_fix']
        cand[market] = dict(selected=name, dep=dep, train=specs24[market][name], entry=entry, v24=info['methods'][name], dist_name=dname, dist_spec=specs24[market][dname], pos_mean=ctx[market]['pos_mean'])
        print('final', market, name, entry['recommendation'], flush=True)
    jdump(OUT / 'final_2025.json', res)
    jdump(CANDIDATES, build_candidates(cand))


def segment_gains(l, raw, p, y):
    out = {}
    for name, mask in (('weeks 1-6', l.week.to_numpy() <= 6), ('weeks 7+', l.week.to_numpy() > 6), ('k<=2', l.k.to_numpy() <= 2), ('k>=6', l.k.to_numpy() >= 6), ('over-favored', raw >= .5), ('under-favored', raw < .5),
                       ('abs offset >=2', np.abs(l.off.to_numpy()) >= 2)):
        if mask.sum() >= 300:
            out[name] = {'n': int(mask.sum()), 'brier_raw': float(((raw[mask] - y[mask]) ** 2).mean()), 'brier_new': float(((p[mask] - y[mask]) ** 2).mean())}
    for pos in sorted(set(l.position)):
        mask = (l.position == pos).to_numpy()
        if mask.sum() >= 300:
            out['position ' + pos] = {'n': int(mask.sum()), 'brier_raw': float(((raw[mask] - y[mask]) ** 2).mean()), 'brier_new': float(((p[mask] - y[mask]) ** 2).mean())}
    return out


def public_spec(spec):
    s = {k: v for k, v in spec.items() if k not in ('table', 'overall', 'pooled', 'kappa', 'w') or k in ('w',)}
    return s


def build_candidates(cand):
    markets = {}
    for market, c in cand.items():
        name, dep, train, entry = c['selected'], c['dep'], c['train'], c['entry']
        pm = entry['methods']['probability_map']
        base = {'method': name, 'recommendation': entry['recommendation'], 'version': VERSION, 'base_model': 'champion-v2 (v1 for markets outside the policy)',
                'training_window': '2021-2023', 'tuning_window': '2024', 'holdout_window': '2025 (scored once, selection frozen before it was loaded)',
                'deployment_refit_window': '2021-2024 (parameters under `deploy`; NOT holdout-scored)',
                'holdout_2025': {'n': int(pm['holdout_2025_all_lines']['point']['n']), 'brier_raw': entry['baselines_2025']['v2_raw']['point']['brier'], 'brier_calibrated': pm['holdout_2025_all_lines']['point']['brier'],
                                 'logloss_raw': entry['baselines_2025']['v2_raw']['point']['logloss'], 'logloss_calibrated': pm['holdout_2025_all_lines']['point']['logloss'],
                                 'slope_raw': entry['baselines_2025']['v2_raw']['point']['slope'], 'slope_calibrated': pm['holdout_2025_all_lines']['point']['slope'],
                                 'ece_raw': entry['baselines_2025']['v2_raw']['point']['ece'], 'ece_calibrated': pm['holdout_2025_all_lines']['point']['ece'],
                                 'brier_gain_ci95': pm['paired_brier_gain']['ci95']}}
        def spec_out(s):
            if s['method'] in ('platt', 'pooled_platt'):
                return {'a': s['a'], 'b': s['b']}
            if s['method'] == 'isotonic':
                return {'x': s['x'], 'y': s['y']}
            if s['method'] == 'shrink_const':
                return {'w': s['w'], 'target': s['overall']}
            if s['method'] == 'shrink_base':
                return {'w': s['w'], 'base_rate_by_line': s['table'], 'base_rate_default': s['overall']}
            return {k: v for k, v in s.items() if k != 'method'}
        dm = entry['methods']['distribution_fix']
        dspec = {k: v for k, v in c['dist_spec'].items() if k != 'method'}
        if 'w' in dspec:
            dspec['pos_lam'] = c['pos_mean']
        base['distribution_fix_upstream'] = {'method': c['dist_name'], 'parameters': dspec, 'recommendation': dm['recommendation'],
                                             'note': 'changes the Champion distribution itself (needs build_pipeline/index.html changes), not a probability-level map; fitted on 2021-2023',
                                             'holdout_2025': {'brier_raw': entry['baselines_2025']['v2_raw']['point']['brier'], 'brier_new': dm['holdout_2025_all_lines']['point']['brier'],
                                                              'slope_new': dm['holdout_2025_all_lines']['point']['slope'], 'ece_new': dm['holdout_2025_all_lines']['point']['ece'],
                                                              'brier_gain_ci95': dm['paired_brier_gain']['ci95'], 'main_line_brier_raw': dm['raw_main_line']['brier'], 'main_line_brier_new': dm['holdout_2025_main_line']['brier']}}
        over = {**base, 'parameters': spec_out(train), 'deploy': spec_out(dep)}
        # Under is the complement of the calibrated Over so that p_over + p_under = 1 - push is preserved. Explicit Under-side form for the JS side that works on p_under directly:
        def under_form(sp):
            if 'a' in sp:
                return {'a': -sp['a'], 'b': sp['b'], 'input': 'logit(p_under_given_no_push)'}
            if 'w' in sp:
                return {'w': sp['w'], 'target': 1 - sp['target'], 'input': 'p_under_given_no_push'} if 'target' in sp else {'derived_from': 'Over'}
            return {'derived_from': 'Over: p_under = (1 - push) - calibrated_over'}
        under = {**base, 'parameters': under_form(spec_out(train)), 'deploy': under_form(spec_out(dep))}
        markets[market] = {'Over': over, 'Under': under}
    return {'schema': 'going-calibration-candidates-1', 'version': VERSION, 'status': 'CANDIDATE - not wired into index.html; shadow/evaluate before any use',
            'apply': {'logistic': "p' = 1 / (1 + exp(-(a + b * logit(p_over_given_no_push)))); p_over_out = p' * (1 - push); p_under_out = (1 - push) - p_over_out. Clip p to [1e-6, 1-1e-6].",
                      'isotonic': "p' = linear interpolation of (x, y) knots, clamped at the ends; same push handling.",
                      'shrink_const': "p' = w * p + (1 - w) * target (target = market over-rate, dev window; Under uses 1 - target)",
                      'domain': 'validated only for lines within about +/-50% of the player median (main line and 4 ladder steps each side); do not apply to degenerate lines (e.g. rushing yards 0.5 for a non-rusher) or when the player is a different position than the Champion policy covers',
                      'hierarchy': 'pooled_platt = per-market logistic pulled toward the all-market logistic by kappa pseudo-observations (kappa tuned on 2024)',
                      'markets_in_js': 'receptions, rec_yds, rush_yds, pass_yds, pass_tds, rush_tds, rec_tds, atd (market ids as in nfl_betting.json)'},
            'markets': markets}


if __name__ == '__main__':
    stage = sys.argv[1] if len(sys.argv) > 1 else 'diag'
    {'diag': stage_diag, 'select': stage_select, 'final': stage_final}[stage]()
