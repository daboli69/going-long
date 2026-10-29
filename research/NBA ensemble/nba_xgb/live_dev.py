"""Development comparison of live-state models. Fit 2022-2024; evaluate 2025 and 2026 through 2026-01-31. The 2026-02-01 onward window stays untouched."""
import json
import numpy as np
import pandas as pd
from scipy import stats
from . import live_model as M, market_benchmark as MB
from .avail_study import OUT, DOCS

FINAL_START = '2026-02-01'


def load():
    d = pd.read_parquet(OUT / 'live_snapshots.parquet')
    sp = MB.spreads().rename(columns={'home_team_spread': 'spread'})
    d = d.merge(sp, on='game_id', how='left')
    d['mu_close'] = d.spread                       # home points favoured by the closing spread (ESPN-embedded, capture time unknown)
    d['y'] = (d.final_margin > 0).astype(float)
    return d


def boot_diff(df, a, b, col='ll', draws=2000, seed=1):
    """Game-clustered paired bootstrap of mean(a - b) on a per-row loss column."""
    rng = np.random.default_rng(seed)
    g = df.groupby('game_id').apply(lambda x: pd.Series({'d': (x[f'{col}_{a}'] - x[f'{col}_{b}']).sum(), 'n': len(x)}), include_groups=False)
    d, n = g.d.values, g.n.values
    idx = rng.integers(0, len(d), (draws, len(d)))
    boot = d[idx].sum(1) / n[idx].sum(1)
    return float(d.sum() / n.sum()), [float(x) for x in np.percentile(boot, [2.5, 97.5])]


def main():
    d = load()
    tr = d[d.season.between(2022, 2024)]
    dev = d[(d.season == 2025) | ((d.season == 2026) & (d.game_date < FINAL_START))].copy()
    assert len(dev) > 20000 and dev.game_date.max() < FINAL_START
    models = {}
    models['A'] = M.fit(tr, 'mu_base')
    models['A_avail'] = M.fit(tr, 'mu_avail')
    models['A_lineup'] = M.fit(tr, 'mu_base', use_lineup=True)
    trB = tr.dropna(subset=['mu_close'])
    models['B_close'] = M.fit(trB, 'mu_close')
    for k, p in models.items():
        print(k, {a: round(b, 4) if isinstance(b, float) else b for a, b in vars(p).items() if a in ('a1', 'aL', 'rho', 'p_home_ot')}, p.sm, p.fitted_on)
    devB = dev.dropna(subset=['mu_close', 'mu_base', 'mu_avail']).copy()
    for k, p in models.items():
        sub = devB if not p.use_lineup else devB.dropna(subset=['L'])
        devB.loc[sub.index, f'p_{k}'] = M.p_home_win(p, sub)
    # pregame-only and state-only baselines
    sg = float(np.std(tr.final_margin - tr.mu_base))
    devB['p_pregame'] = stats.norm.cdf(devB.mu_base / sg)
    from sklearn.linear_model import LogisticRegression
    Xs = lambda x: np.column_stack([x.m / np.sqrt(x.tau / 60 + 1), x.m / np.sqrt(x.tau / 60 + 1) ** 2, x.tau / REG])
    REG = 2880.0
    st = LogisticRegression(C=100, max_iter=500).fit(Xs(tr), (tr.final_margin > 0).astype(int))
    devB['p_state_only'] = st.predict_proba(Xs(devB))[:, 1]
    cols = ['p_pregame', 'p_state_only', 'p_A', 'p_A_avail', 'p_B_close']
    sub = devB.dropna(subset=cols + ['p_A_lineup']).copy()
    for c in cols + ['p_A_lineup']:
        sub[f'll_{c[2:]}'] = M.logloss(sub.y.values, sub[c].values)
    out = {'rows': int(len(sub)), 'games': int(sub.game_id.nunique()), 'window': f"{sub.game_date.min()}..{sub.game_date.max()}", 'mean_log_loss': {}}
    for c in cols + ['p_A_lineup']:
        out['mean_log_loss'][c] = float(sub[f'll_{c[2:]}'].mean())
    print(json.dumps(out, indent=1))
    pairs = [('A', 'pregame'), ('A', 'state_only'), ('A_avail', 'A'), ('A_lineup', 'A'), ('B_close', 'A'), ('B_close', 'A_avail')]
    out['paired_vs'] = {}
    for a, b in pairs:
        m, ci = boot_diff(sub, a, b)
        out['paired_vs'][f'{a}-{b}'] = {'mean': m, 'ci95': ci}
        print(f'{a:10s} minus {b:10s} {m:+.4f} [{ci[0]:+.4f},{ci[1]:+.4f}]')
    # by time remaining bucket
    sub['bucket'] = pd.cut(sub.tau, [0, 360, 720, 1440, 2160, 2880], labels=['last 6m', '6-12m', '12-24m', '24-36m', 'first 12m'])
    out['by_bucket'] = {str(k): {c: float(g[f'll_{c[2:]}'].mean()) for c in ('p_state_only', 'p_A', 'p_B_close', 'p_A_lineup')} for k, g in sub.groupby('bucket', observed=True)}
    print(pd.DataFrame(out['by_bucket']).round(4))
    # calibration of A
    sub['bin'] = pd.cut(sub.p_A, [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1.0])
    cal = sub.groupby('bin', observed=True).agg(n=('y', 'size'), pred=('p_A', 'mean'), obs=('y', 'mean'))
    print(cal.round(3))
    out['calibration_A'] = cal.reset_index().astype({'bin': str}).to_dict('records')
    # CRPS of margin distribution
    mm, sm, mt, st_ = M.moments(models['A'], sub)
    out['crps_margin_A'] = float(M.crps_normal(sub.final_margin.values, mm, sm).mean())
    mm2, sm2, _, _ = M.moments(models['B_close'], sub)
    out['crps_margin_B'] = float(M.crps_normal(sub.final_margin.values, mm2, sm2).mean())
    out['rmse_total_A'] = float(np.sqrt(((sub.final_total - mt) ** 2).mean()))
    print('CRPS margin A', out['crps_margin_A'], 'B', out['crps_margin_B'], '| total RMSE A', out['rmse_total_A'])
    (OUT / 'LIVE_DEV_RESULTS.json').write_text(json.dumps(out, indent=2, default=str), encoding='utf-8')
    pd.to_pickle(models, OUT / 'live_models_dev.pkl')


if __name__ == '__main__':
    main()
