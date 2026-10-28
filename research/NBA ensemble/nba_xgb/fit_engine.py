"""Fit strength-engine parameters on 2016-2021 only (protocol: docs/NBA_XGB_PREREGISTRATION.md)."""
from __future__ import annotations
import itertools
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression
from . import data, engine

FIT_SEASONS = (2016, 2021)
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'NBA_XGB_ENGINE_PARAMS.json'


def logloss(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def single_feature_loss(x, home_court, y):
    m = LogisticRegression(penalty=None, max_iter=500).fit(np.column_stack([x, home_court]), y)
    return logloss(y, m.predict_proba(np.column_stack([x, home_court]))[:, 1]), m


def fit_masks(prep):
    g = prep.games
    return ((g.season.between(*FIT_SEASONS)) & g.completed & g.verified).values


def fit_elo(prep, p, mask):
    y = prep.games.home_win.values[mask]
    hc = (~prep.g_neutral).astype(float)[mask]

    def loss(theta, mov):
        k, hca, carry = theta
        if not (1 <= k <= 80 and 0 <= hca <= 200 and 0.3 <= carry <= 1.0):
            return 10.0
        snaps = engine.elo_snapshots(prep, k, hca, carry, mov)
        d = engine.elo_features(prep, p, snaps, carry)[mask]
        pr = 1.0 / (1.0 + 10.0 ** (-(d + hca * hc) / 400.0))
        return logloss(y, pr)

    results = {}
    for mov in (True, False):
        best = None
        for start in ([20, 65, 0.75], [10, 80, 0.85], [30, 50, 0.6]):
            r = minimize(loss, start, args=(mov,), method='Nelder-Mead', options={'xatol': 0.05, 'fatol': 1e-6, 'maxiter': 120})
            if best is None or r.fun < best.fun:
                best = r
        results['mov' if mov else 'plain'] = {'k': float(best.x[0]), 'hca': float(best.x[1]),
                                              'carry': float(best.x[2]), 'logloss': float(best.fun), 'mov': mov}
        print('elo', results['mov' if mov else 'plain'], flush=True)
    return results


def fit_adjusted(prep, p, mask):
    rows = np.where(mask)[0]
    y = prep.games.home_win.values[mask]
    hc = (~prep.g_neutral).astype(float)[mask]
    table = []
    for lam, kappa in itertools.product((5, 10, 20, 40, 80, 160), (0.0, 0.25, 0.5, 0.75, 1.0)):
        adj = engine.AdjustedStrength(prep, lam, kappa)
        off, de = engine.adjusted_features(prep, p, adj, rows=rows)
        loss, _ = single_feature_loss((off + de)[mask], hc, y)
        table.append({'lam': lam, 'kappa': kappa, 'logloss': loss})
        print('adj', table[-1], flush=True)
    best = min(table, key=lambda r: r['logloss'])
    return best, table


def fit_recent(prep, p, mask):
    y = prep.games.home_win.values[mask]
    hc = (~prep.g_neutral).astype(float)[mask]
    table = []
    for h, rho in itertools.product((5, 10, 20, 40, 80, 160), (0.0, 0.3, 0.5, 0.7, 0.9)):
        for n0 in (2, 5, 10, 20, 40):
            # n0 enters the season roll-over prior, so snapshots are recomputed for every combination
            snaps_n, _ = engine.recent_snapshots(prep, h, n0, rho)
            eh, ea, _ = engine.recent_features(prep, p, snaps_n, n0, rho)
            loss, _ = single_feature_loss((eh[:, 0] - ea[:, 0])[mask], hc, y)
            table.append({'half_life': h, 'n0': n0, 'rho': rho, 'logloss': loss})
        print('recent h', h, 'rho', rho, 'best so far', min(t['logloss'] for t in table), flush=True)
    best = min(table, key=lambda r: r['logloss'])
    return best, table


def main():
    games, boxes = data.load()
    prep = engine.prepare(games, boxes)
    p = engine.cutoff_index(prep, 1)
    mask = fit_masks(prep)
    out = {'fit_seasons': FIT_SEASONS, 'n_games': int(mask.sum()),
           'base_rate_loss': logloss(prep.games.home_win.values[mask], np.full(mask.sum(), prep.games.home_win.values[mask].mean()))}
    elo = fit_elo(prep, p, mask)
    out['elo'] = elo
    out['adj_best'], out['adj_grid'] = fit_adjusted(prep, p, mask)
    out['recent_best'], out['recent_grid'] = fit_recent(prep, p, mask)
    OUT.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('saved', OUT)


if __name__ == '__main__':
    main()
