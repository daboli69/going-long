"""Development-window comparison of live models with Kalshi in-game quotes (games dated up to 2026-01-31 only).

Everything here is exploratory design work: timestamp lag, how well Kalshi is calibrated, how Model A/B compare, and the first look at the encompassing regression.
The final window (2026-02-01 onward) is never read in this module.
"""
import json
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from . import live_market as LM, live_model as M
from .avail_study import OUT
from .live_dev import load as load_snap, boot_diff

DEV_END = '2026-01-31'


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def sigma_g():
    """Margin scale mapping a closing win probability to a closing margin: MLE of P(home win) = Phi(spread / sigma) on 2022-2024."""
    d = load_snap()
    g = d[(d.season.between(2022, 2024)) & d.mu_close.notna()].drop_duplicates('game_id')
    from scipy.optimize import minimize_scalar
    f = lambda s: -np.mean(g.y * stats.norm.logcdf(g.mu_close / s) + (1 - g.y) * stats.norm.logcdf(-g.mu_close / s))
    return float(minimize_scalar(f, bounds=(5, 25), method='bounded').x)


def price_states(S: pd.DataFrame, models: dict, sg: float) -> pd.DataFrame:
    S = S.copy()
    S['mu_K'] = sg * stats.norm.ppf(np.clip(S.k_pre, 0.02, 0.98))
    S['p_A'] = M.p_home_win(models['A'], S)
    S['p_A_avail'] = M.p_home_win(models['A_avail'], S)
    SB = S.copy()
    SB['mu_close'] = SB.mu_close_espn
    S['p_B_espn'] = np.where(SB.mu_close.notna(), M.p_home_win(models['B_close'], SB.assign(mu_close=SB.mu_close.fillna(0))), np.nan)
    SK = S.copy()
    SK['mu_close'] = SK.mu_K
    S['p_B_K'] = M.p_home_win(models['B_close'], SK)
    return S


def cluster_logit(df, cols):
    X = sm.add_constant(df[cols])
    res = sm.Logit(df.y, X).fit(disp=0, cov_type='cluster', cov_kwds={'groups': df.game_id.astype('category').cat.codes})
    return res


def main(lag=0):
    models = pd.read_pickle(OUT / 'live_models_dev.pkl')
    S = LM.build(lag=lag, log=lambda *a: None)
    S = S[S.game_date <= DEV_END]
    assert len(S) > 5000 and S.game_date.max() <= DEV_END, 'development window must be non-empty and end by 2026-01-31'
    sg = sigma_g()
    S = price_states(S, models, sg)
    S['p_C'] = S.k_mid
    sub = S.dropna(subset=['p_C', 'p_A', 'p_A_avail', 'p_B_K', 'p_B_espn']).copy()
    for c in ('C', 'A', 'A_avail', 'B_K', 'B_espn'):
        sub[f'll_{c}'] = M.logloss(sub.y.values, sub[f'p_{c}'].values)
    out = {'lag_s': lag, 'sigma_g': sg, 'rows': int(len(sub)), 'games': int(sub.game_id.nunique()), 'window': [sub.game_date.min(), sub.game_date.max()],
           'mean_ll': {c: float(sub[f'll_{c}'].mean()) for c in ('C', 'A', 'A_avail', 'B_K', 'B_espn')}, 'paired': {}}
    for a, b in (('A', 'C'), ('A_avail', 'C'), ('B_K', 'C'), ('B_espn', 'C'), ('B_K', 'A_avail')):
        m, ci = boot_diff(sub, a, b)
        out['paired'][f'{a}-{b}'] = {'mean': m, 'ci95': ci}
        print(f'lag {lag:3d}s  {a:8s} minus {b:8s} {m:+.4f} [{ci[0]:+.4f},{ci[1]:+.4f}]')
    print('mean ll', {k: round(v, 4) for k, v in out['mean_ll'].items()})
    # calibration of the market itself
    sub['bin'] = pd.cut(sub.p_C, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
    cal = sub.groupby('bin', observed=True).agg(n=('y', 'size'), pred=('p_C', 'mean'), obs=('y', 'mean'))
    out['calibration_kalshi'] = cal.reset_index().astype({'bin': str}).to_dict('records')
    print(cal.round(3))
    # encompassing regressions (exploratory)
    sub['z_C'] = logit(sub.p_C)
    for name in ('B_K', 'A_avail', 'A'):
        sub[f'z_{name}'] = logit(sub[f'p_{name}'])
        r = cluster_logit(sub, ['z_C', f'z_{name}'])
        out[f'encompass_{name}'] = {k: {'coef': float(r.params[k]), 'se': float(r.bse[k]), 'p': float(r.pvalues[k])} for k in r.params.index}
        print(f'encompassing y ~ z_C + z_{name}:', {k: (round(float(r.params[k]), 3), round(float(r.bse[k]), 3)) for k in ('z_C', f'z_{name}')})
    out['timing'] = {'median_quote_age_note': 'candle bid/ask carried forward; age not recorded per minute'}
    return out, sub


def lag_scan():
    """Choose the state lag on development data: the lag whose model-probability changes best match changes in the Kalshi mid."""
    models = pd.read_pickle(OUT / 'live_models_dev.pkl')
    sg = sigma_g()
    res = {}
    for lag in (-60, -30, 0, 30, 60, 90, 120):
        S = LM.build(step=1, lag=lag, log=lambda *a: None)
        S = S[S.game_date <= DEV_END]
        S = price_states(S, models, sg)
        S = S.sort_values(['game_id', 'ts'])
        S['dk'] = S.groupby('game_id').k_mid.diff()
        S['dm'] = S.groupby('game_id').p_B_K.diff()
        x = S.dropna(subset=['dk', 'dm'])
        res[lag] = float(np.corrcoef(x.dk, x.dm)[0, 1])
        print('lag', lag, 'corr of 1-minute changes', round(res[lag], 4), len(x), flush=True)
    return res


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'lags':
        r = lag_scan()
        (OUT / 'LIVE_LAG_SCAN_DEV.json').write_text(json.dumps(r, indent=2), encoding='utf-8')
    else:
        lag = int(sys.argv[1]) if len(sys.argv) > 1 else 0
        o, sub = main(lag)
        (OUT / f'LIVE_KALSHI_DEV_lag{lag}.json').write_text(json.dumps(o, indent=2, default=str), encoding='utf-8')
