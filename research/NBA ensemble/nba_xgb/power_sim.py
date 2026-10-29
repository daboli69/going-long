"""Simulation-based power analysis for paired log-loss comparisons (run BEFORE any new scoring).

Truth model: logit p_true = logit(p_A) + lam * (logit(p_B) - logit(p_A)), where A and B are two real predictors on the 2024 development fold
(structure only; outcomes are simulated, never the real ones). lam = 0 means B adds nothing; lam = 1 means B is exactly right.
For each lam the true expected log-loss gap E[LL_A - LL_B] is computed analytically; outcomes are then simulated by resampling game dates with replacement
(keeps the within-day clustering) until N games are reached, and the Diebold-Mariano statistic with Newey-West variance on daily mean differences is
computed. Power = share of replicates with |DM| > 2.394 (alpha 0.0167 two-sided, the Bonferroni level for three primary comparisons).
"""
import json
import numpy as np
import pandas as pd
from . import avail_study as S

Z = 2.394
rng = np.random.default_rng(20261029)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sig(z):
    return 1 / (1 + np.exp(-z))


def dm_stat(daily):
    n = len(daily)
    mu = daily.mean()
    e = daily - mu
    L = int(np.floor(n ** (1 / 3)))
    var = e @ e / n
    for k in range(1, L + 1):
        var += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / n
    return mu / np.sqrt(var / n) if var > 0 else 0.0


def expected_gap(pa, pb, pt):
    ll = lambda q: -(pt * np.log(q) + (1 - pt) * np.log(1 - q))
    return float(np.mean(ll(pa) - ll(pb)))


def simulate(df, a, b, lams, sizes, reps=400):
    pa, pb = df[a].values, df[b].values
    days = df.groupby('game_date').indices
    day_keys = list(days)
    out = {}
    for lam in lams:
        pt = sig(logit(pa) + lam * (logit(pb) - logit(pa)))
        gap = expected_gap(np.clip(pa, 1e-6, 1 - 1e-6), np.clip(pb, 1e-6, 1 - 1e-6), pt)
        row = {'true_gap': gap, 'power': {}}
        for N in sizes:
            hits = 0
            for _ in range(reps):
                idx, n = [], 0
                while n < N:
                    ix = days[day_keys[rng.integers(len(day_keys))]]
                    idx.append(ix)
                    n += len(ix)
                daily = []
                for ix in idx:
                    y = (rng.random(len(ix)) < pt[ix]).astype(float)
                    la = -(y * np.log(pa[ix]) + (1 - y) * np.log(1 - pa[ix]))
                    lb = -(y * np.log(pb[ix]) + (1 - y) * np.log(1 - pb[ix]))
                    daily.append((la - lb).mean())
                hits += abs(dm_stat(np.array(daily))) > Z
            row['power'][N] = hits / reps
        out[f'{lam:.2f}'] = row
        print(a, b, f'lam={lam:.2f} gap={gap:+.4f}', row['power'], flush=True)
    return out


def main():
    frozen = json.loads((S.DOCS / 'NBA_AVAIL_FROZEN.json').read_text())
    T = S.load_table()
    P = S.oos(T, frozen, (S.DEV_FOLD,))
    P = P.assign(**{k: P[k].clip(0.02, 0.98) for k in S.KINDS})
    sizes = [1230, 2459, 3689, 5000]
    res = {'basis': 'development fold 2024 predictions (structure only)', 'alpha': 0.0167, 'sizes': sizes, 'reps': 400,
           'availability_vs_base_logistic': simulate(P, 'logit_base', 'logit_avail', [0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0], sizes),
           'xgb_vs_logistic': simulate(P, 'logit_avail', 'xgb_avail', [0.25, 0.5, 0.75, 1.0, 1.5], sizes)}
    for key in ('availability_vs_base_logistic', 'xgb_vs_logistic'):
        mde = {}
        for N in sizes:
            ok = [(v['true_gap'], v['power'][N]) for k, v in res[key].items() if v['power'][N] >= 0.8 and v['true_gap'] > 0]
            mde[N] = min(g for g, _ in ok) if ok else None
        res[key + '_smallest_gap_with_80pct_power'] = mde
    # the true null is where the expected gap is ~0 (not lam=0): the rejection rate there must be near the nominal 1.67%
    for key in ('availability_vs_base_logistic', 'xgb_vs_logistic'):
        near_null = [v for v in res[key].values() if abs(v['true_gap']) < 0.0005]
        assert near_null, f'{key}: no grid point near a zero true gap, the size check would cover nothing'
        assert all(v['power'][2459] < 0.08 for v in near_null), f'{key}: rejection rate at a true null is far above nominal'
    (S.OUT / 'POWER_SIMULATION.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if 'smallest' in k}, indent=1))


if __name__ == '__main__':
    main()
