"""Freeze the live pricing models: one refit on all data before 2026-02-01, bootstrap parameter uncertainty, calibration slack.

Writes research_nba_xgb/live_models_frozen.pkl and docs/NBA_LIVE_FROZEN.json. After this file is committed the final window (2026-02-01 onward) may be evaluated once.
"""
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from scipy import stats
from . import live_model as M
from .avail_study import OUT, DOCS
from .live_dev import load as load_snap

FINAL_START = '2026-02-01'
B_DRAWS = 25


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def sigma_g(d):
    g = d[d.mu_close.notna()].drop_duplicates('game_id')
    from scipy.optimize import minimize_scalar
    f = lambda s: -np.mean(g.y * stats.norm.logcdf(g.mu_close / s) + (1 - g.y) * stats.norm.logcdf(-g.mu_close / s))
    return float(minimize_scalar(f, bounds=(5, 25), method='bounded').x)


def main(log=print):
    d = load_snap()
    train = d[(d.season <= 2025) | ((d.season == 2026) & (d.game_date < FINAL_START))]
    assert train.game_date.max() < FINAL_START, 'training data must end before the final window'
    models = {'A_full': M.fit(train, 'mu_avail', use_lineup=True),
              'A_base': M.fit(train, 'mu_base'),
              'B_close': M.fit(train.dropna(subset=['mu_close']), 'mu_close')}
    sg = sigma_g(train)
    for k, p in models.items():
        log(k, 'a1', round(p.a1, 3), 'am', round(p.am, 4), 'aL', round(p.aL, 3), 'nu', round(p.nu_m, 1), round(p.nu_t, 1), p.fitted_on)
    # parameter bootstrap over games
    dev = d[(d.season == 2025) | ((d.season == 2026) & (d.game_date < FINAL_START))].dropna(subset=['mu_close', 'mu_avail', 'L']).copy()
    gids = train.game_id.unique()
    groups = dict(tuple(train.groupby('game_id')))
    rng = np.random.default_rng(20261029)
    draws = {'A_full': [], 'B_close': []}
    for b in range(B_DRAWS):
        pick = rng.choice(gids, len(gids))
        bs = pd.concat([groups[g] for g in pick], ignore_index=True)
        pa = M.fit(bs, 'mu_avail', use_lineup=True)
        pb = M.fit(bs.dropna(subset=['mu_close']), 'mu_close')
        draws['A_full'].append(M.p_home_win(pa, dev))
        draws['B_close'].append(M.p_home_win(pb, dev))
        log('bootstrap', b + 1, '/', B_DRAWS, flush=True) if False else log('bootstrap', b + 1, '/', B_DRAWS)
    dev['sd_A_full'] = np.std(np.vstack(draws['A_full']), axis=0)
    dev['sd_B_close'] = np.std(np.vstack(draws['B_close']), axis=0)
    dev['p_A_full'] = M.p_home_win(models['A_full'], dev)
    dev['p_B_close'] = M.p_home_win(models['B_close'], dev)
    dev['tau_bucket'] = pd.cut(dev.tau, [0, 360, 720, 1440, 2160, 2880], labels=False)
    # calibration slack: root-mean-square gap between predicted and observed frequency by probability bin (honest hold-out fits from live_dev)
    dm = pd.read_pickle(OUT / 'live_models_dev.pkl')
    hold = dev.copy()
    slack = {}
    for name, pm, col in (('A_full', dm['A_lineup'], 'mu_base'), ('B_close', dm['B_close'], 'mu_close')):
        p = M.p_home_win(pm, hold.assign(L=hold.L.fillna(0)))
        bins = pd.cut(p, np.linspace(0, 1, 11))
        t = pd.DataFrame({'p': p, 'y': hold.y, 'bin': bins}).groupby('bin', observed=True).agg(n=('y', 'size'), p=('p', 'mean'), y=('y', 'mean'))
        slack[name] = float(np.sqrt(np.average((t.y - t.p) ** 2, weights=t.n)))
    se_tab = {}
    for name in ('A_full', 'B_close'):
        t = dev.groupby('tau_bucket')[f'sd_{name}'].mean()
        se_tab[name] = {int(k): float(v) for k, v in t.items()}
    out = {'frozen_at_utc': pd.Timestamp.now(tz='UTC').isoformat(), 'training_end': str(train.game_date.max()), 'final_window_start': FINAL_START,
           'sigma_g': sg, 'calibration_slack_rms': slack, 'parameter_sd_by_tau_bucket': se_tab, 'bootstrap_draws': B_DRAWS,
           'tau_bucket_edges_seconds': [0, 360, 720, 1440, 2160, 2880],
           'params': {k: {a: (list(b) if isinstance(b, tuple) else b) for a, b in vars(p).items()} for k, p in models.items()},
           'inputs_sha256': {f: sha(OUT / f) for f in ('live_snapshots.parquet', 'pregame_priors.parquet', 'rapm_ratings.parquet')},
           'dev_hold_out_models_file': 'live_models_dev.pkl'}
    pd.to_pickle({'models': models, 'sigma_g': sg, 'slack': slack, 'se': se_tab}, OUT / 'live_models_frozen.pkl')
    (DOCS / 'NBA_LIVE_FROZEN.json').write_text(json.dumps(out, indent=2, default=float), encoding='utf-8')
    log(json.dumps({k: out[k] for k in ('sigma_g', 'calibration_slack_rms', 'parameter_sd_by_tau_bucket')}, indent=1))


if __name__ == '__main__':
    main()
