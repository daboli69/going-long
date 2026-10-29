"""Pre-registered evaluation of the frozen live models against Kalshi in-game quotes.

    python -m nba_xgb.live_final --window final     # 2026-02-01 onward; run ONCE after docs/NBA_LIVE_FROZEN.json is committed
    python -m nba_xgb.live_final --window debug     # development window, frozen models are IN-SAMPLE there: code check only, never a result
Quote-based returns use bid/ask closes of 1-minute candles: they are not fills and say nothing about depth.
"""
import argparse
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from . import fair_value as FV, live_market as LM, live_model as M, live_value as LV
from .avail_study import OUT, DOCS

FINAL_START = '2026-02-01'
LOT = 100                    # contracts per order for fee rounding
QUOTE_AGE_S = 60.0           # candle resolution; counted as fresh


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def clustered(df, cols):
    X = sm.add_constant(df[cols])
    return sm.Logit(df.y, X).fit(disp=0, cov_type='cluster', cov_kwds={'groups': df.game_id.astype('category').cat.codes})


def boot_mean(df, col, draws=4000, seed=7):
    g = df.groupby('game_id')[col].agg(['sum', 'size'])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), (draws, len(g)))
    b = g['sum'].values[idx].sum(1) / g['size'].values[idx].sum(1)
    return float(g['sum'].sum() / g['size'].sum()), [float(x) for x in np.percentile(b, [2.5, 97.5])]


def price(S, fz):
    S = S.copy()
    sg = fz['sigma_g']
    S['mu_K'] = sg * stats.norm.ppf(np.clip(S.k_pre, 0.02, 0.98))
    S['p_C'] = S.k_mid
    S['p_A'] = M.p_home_win(fz['models']['A_full'], S.assign(L=S.L.fillna(0.0)))
    SK = S.copy()
    SK['mu_close'] = SK.mu_K
    S['p_B_K'] = M.p_home_win(fz['models']['B_close'], SK)
    return S


def block_signals(S, fz, block_min=10):
    """Conservative-EV signals on the home winner contract, first qualifying state per game per side per block."""
    rows = []
    for gid, g in S.groupby('game_id'):
        g = g.sort_values('ts')
        taken = set()
        for r in g.itertuples(index=False):
            if np.isnan(r.p_B_K) or np.isnan(r.h_bid) or np.isnan(r.h_ask) or r.h_ask <= r.h_bid:
                continue
            blk = int((r.t // 60) // block_min)
            se = LV.se_total(fz, 'B_close', r.tau)
            v = FV.value_kalshi_yes(float(r.p_B_K), se, float(r.h_bid), float(r.h_ask), QUOTE_AGE_S, contracts=LOT)
            if v.status != 'actionable' or (blk, v.side) in taken:
                continue
            taken.add((blk, v.side))
            fee = FV.kalshi_fee(v.quote, LOT) / LOT
            win = r.y if v.side == 'buy_yes' else 1.0 - r.y
            rows.append({'game_id': gid, 'game_date': r.game_date, 'ts': r.ts, 'tau': r.tau, 'period': r.period, 'side': v.side, 'price': v.quote,
                         'p_model': v.p_model, 'p_low': v.p_low, 'ev_model': v.ev_at_quote, 'ev_cons': v.ev_at_quote_conservative,
                         'net': win - v.quote - fee, 'margin_state': r.m, 'k_pre': r.k_pre, 'k_mid': r.k_mid})
    return pd.DataFrame(rows)


def evaluate(window='final'):
    fz = LV.load_frozen()
    S = LM.build(lag=0, log=lambda *a: None)
    if window == 'final':
        S = S[S.game_date >= FINAL_START]
        assert S.game_date.min() >= FINAL_START
    else:
        S = S[S.game_date < FINAL_START]
    S = price(S, fz)
    sub = S.dropna(subset=['p_C', 'p_A', 'p_B_K']).copy()
    assert len(sub) > 5000 and sub.game_id.nunique() > 100, f'window {window}: too little data ({len(sub)} rows)'
    for c in ('C', 'A', 'B_K'):
        sub[f'll_{c}'] = M.logloss(sub.y.values, sub[f'p_{c}'].values)
        sub[f'bs_{c}'] = (sub[f'p_{c}'] - sub.y) ** 2
    out = {'window': window, 'in_sample_debug': window != 'final', 'rows': int(len(sub)), 'games': int(sub.game_id.nunique()),
           'dates': [sub.game_date.min(), sub.game_date.max()], 'mean_ll': {c: float(sub[f'll_{c}'].mean()) for c in ('C', 'A', 'B_K')},
           'mean_brier': {c: float(sub[f'bs_{c}'].mean()) for c in ('C', 'A', 'B_K')}, 'paired_ll': {}}
    for a, b in (('A', 'C'), ('B_K', 'C'), ('B_K', 'A')):
        sub['d'] = sub[f'll_{a}'] - sub[f'll_{b}']
        m, ci = boot_mean(sub, 'd')
        out['paired_ll'][f'{a}-{b}'] = {'mean': m, 'ci95': ci}
    # H1 / H2a: encompassing regression
    sub['z_C'], sub['z_B'], sub['z_A'] = logit(sub.p_C), logit(sub.p_B_K), logit(sub.p_A)
    r = clustered(sub, ['z_C', 'z_B'])
    out['H1_encompassing_B_K'] = {k: {'coef': float(r.params[k]), 'se': float(r.bse[k]), 'p_two_sided': float(r.pvalues[k])} for k in r.params.index}
    out['H1_encompassing_B_K']['b_m_one_sided_p'] = float(r.pvalues['z_B'] / 2 if r.params['z_B'] > 0 else 1 - r.pvalues['z_B'] / 2)
    r2 = clustered(sub, ['z_C', 'z_A'])
    out['encompassing_A'] = {k: {'coef': float(r2.params[k]), 'se': float(r2.bse[k]), 'p_two_sided': float(r2.pvalues[k])} for k in r2.params.index}
    # H2b: does the gap predict the market's own correction over the next 10 minutes?
    sub = sub.sort_values(['game_id', 'ts'])
    sub['z_future'] = sub.groupby('game_id').z_C.shift(-5)           # 2-minute grid: five rows ahead = ten minutes
    sub['dz'] = sub.z_future - sub.z_C
    sub['gap'] = sub.z_C - sub.z_B
    x = sub.dropna(subset=['dz', 'gap'])
    rr = sm.OLS(x.dz, sm.add_constant(x[['gap']])).fit(cov_type='cluster', cov_kwds={'groups': x.game_id.astype('category').cat.codes})
    out['H2b_correction'] = {'coef_gap': float(rr.params['gap']), 'se': float(rr.bse['gap']), 'p': float(rr.pvalues['gap']), 'n': int(len(x))}
    # H2c: quote-based economics
    sig = block_signals(sub, fz)
    out['H2c'] = {'signals': int(len(sig)), 'games_with_signal': int(sig.game_id.nunique()) if len(sig) else 0}
    if len(sig) > 10:
        m, ci = boot_mean(sig, 'net')
        out['H2c'].update({'mean_net_per_contract': m, 'ci95': ci, 'mean_model_ev_per_contract': float(sig.ev_model.mean()),
                           'mean_conservative_ev': float(sig.ev_cons.mean()), 'share_buy_yes': float((sig.side == 'buy_yes').mean()),
                           'mean_price': float(sig.price.mean())})
        sig = sig.sort_values('ts')
        cum = sig.net.cumsum()
        out['H2c']['max_drawdown_contracts'] = float((cum.cummax() - cum).max())
        sig['third'] = pd.qcut(pd.to_datetime(sig.game_date).rank(method='first'), 3, labels=['early', 'middle', 'late'])
        out['H2c']['by_third'] = {str(k): {'n': int(len(g)), 'mean_net': float(g.net.mean())} for k, g in sig.groupby('third', observed=True)}
        sig['bucket'] = pd.cut(sig.tau, [0, 720, 1440, 2160, 2880], labels=['last 12m', '12-24m', '24-36m', 'first 12m'])
        out['H2c']['by_time_remaining'] = {str(k): {'n': int(len(g)), 'mean_net': float(g.net.mean())} for k, g in sig.groupby('bucket', observed=True)}
        out['H2c']['by_side'] = {k: {'n': int(len(g)), 'mean_net': float(g.net.mean())} for k, g in sig.groupby('side')}
        sig.to_parquet(OUT / f'live_signals_{window}.parquet', index=False)
    # coverage and calibration of the margin distribution (B_K)
    SK = sub.assign(mu_close=sub.mu_K)
    mm, sm_, _, _ = M.moments(fz['models']['B_close'], SK)
    nu = fz['models']['B_close'].nu_m
    z = (sub.final_margin.values - mm) / sm_
    out['margin_interval_coverage_B_K'] = {'50': float((np.abs(z) < stats.t.ppf(0.75, nu)).mean()), '90': float((np.abs(z) < stats.t.ppf(0.95, nu)).mean())}
    sub['bin'] = pd.cut(sub.p_B_K, np.linspace(0, 1, 11))
    out['calibration_B_K'] = sub.groupby('bin', observed=True).agg(n=('y', 'size'), pred=('p_B_K', 'mean'), obs=('y', 'mean')).reset_index().astype({'bin': str}).to_dict('records')
    sub['binC'] = pd.cut(sub.p_C, np.linspace(0, 1, 11))
    out['calibration_Kalshi'] = sub.groupby('binC', observed=True).agg(n=('y', 'size'), pred=('p_C', 'mean'), obs=('y', 'mean')).reset_index().astype({'binC': str}).to_dict('records')
    # strata (descriptive)
    sub['fav'] = np.where(sub.k_pre >= 0.5, 'home favourite', 'home underdog')
    sub['move'] = pd.cut((sub.z_C - logit(sub.k_pre)).abs(), [0, 0.5, 1.0, 2.0, 10], labels=['<0.5', '0.5-1', '1-2', '>2'])
    sub['quarter'] = (sub.t // 720 + 1).astype(int).clip(1, 4)
    sub['dd'] = sub.d
    strata = {}
    for col in ('quarter', 'fav', 'move'):
        strata[col] = {str(k): {'n': int(len(g)), 'll_C': float(g.ll_C.mean()), 'll_B_K': float(g.ll_B_K.mean())} for k, g in sub.groupby(col, observed=True)}
    out['strata'] = strata
    path = OUT / (f'LIVE_FINAL_RESULTS.json' if window == 'final' else 'LIVE_DEBUG_IN_SAMPLE.json')
    if window == 'final' and path.exists():
        raise FileExistsError('the final window has been evaluated already; this protocol allows one pass')
    path.write_text(json.dumps(out, indent=2, default=str), encoding='utf-8')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--window', choices=['final', 'debug'], required=True)
    a = ap.parse_args()
    o = evaluate(a.window)
    print(json.dumps({k: o[k] for k in ('window', 'in_sample_debug', 'rows', 'games', 'dates', 'mean_ll', 'paired_ll', 'H1_encompassing_B_K', 'H2b_correction', 'H2c')}, indent=1, default=str))
