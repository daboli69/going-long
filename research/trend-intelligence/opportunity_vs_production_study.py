"""E12 study: Expected Opportunity vs Actual Production (see opportunity_vs_production_spec.json, registered before this ran).

    python research/trend-intelligence/opportunity_vs_production_study.py CACHE_DIR OUT_JSON

CACHE_DIR holds wk_YYYY.csv (nflverse stats_player_week) and ep_YYYY.parquet (ffverse/ffopportunity ep_weekly), 2020-2025.
Aggregate results only. Nothing here is a betting-return test.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SPEC_SHA = hashlib.sha256((HERE / 'opportunity_vs_production_spec.json').read_bytes()).hexdigest()
POS = ['QB', 'RB', 'WR', 'TE']
B = 2000
FAMILY = 16
ALPHA = 0.05 / FAMILY


def load(cache):
    cache = Path(cache)
    wk, ep = [], []
    for s in range(2020, 2026):
        w = pd.read_csv(cache / f'wk_{s}.csv', low_memory=False)
        wk.append(w[(w.season_type == 'REG') & w.position.isin(POS)])
        e = pd.read_parquet(cache / f'ep_{s}.parquet')
        e['season'] = e.season.astype(int)
        e['week'] = e.week.astype(int)
        ep.append(e)
    wk, ep = pd.concat(wk), pd.concat(ep)
    ep = ep[['player_id', 'season', 'week', 'total_fantasy_points_exp', 'total_fantasy_points', 'total_touchdown_diff']].rename(
        columns={'total_fantasy_points_exp': 'exp', 'total_fantasy_points': 'act', 'total_touchdown_diff': 'td_diff'})
    df = wk.merge(ep, on=['player_id', 'season', 'week'], how='inner').dropna(subset=['exp', 'act'])
    df['yds'] = df[['passing_yards', 'rushing_yards', 'receiving_yards']].fillna(0).sum(axis=1)
    df['tds'] = df[['passing_tds', 'rushing_tds', 'receiving_tds']].fillna(0).sum(axis=1)
    df['rec'] = df.receptions.fillna(0)
    df['ppr'] = df.fantasy_points_ppr
    df['res'] = df.act - df.exp
    df['td_res'] = df.td_diff.fillna(0) * 6.0
    df['nontd_res'] = df.res - df.td_res
    for c in ('targets', 'carries', 'attempts'):
        df[c] = df[c].fillna(0)
    return df.sort_values(['player_id', 'season', 'week']).reset_index(drop=True)


def features(df, k):
    g = df.groupby('player_id', sort=False)
    out = df[['player_id', 'season', 'week', 'position']].copy()
    for name, col in (('act', 'act'), ('exp', 'exp'), ('res', 'res'), ('tgt', 'targets'), ('car', 'carries'), ('att', 'attempts'),
                      ('td_res', 'td_res'), ('nontd_res', 'nontd_res')):
        out[name] = g[col].transform(lambda s: s.rolling(k, min_periods=k).mean())
    out['act12'] = g['act'].transform(lambda s: s.rolling(12, min_periods=12).mean())
    for tag, col in (('ppr', 'ppr'), ('rec', 'rec'), ('yds', 'yds'), ('tds', 'tds')):
        nxt = [g[col].shift(-i) for i in (1, 2, 3)]
        out[f'y1_{tag}'] = nxt[0]
        out[f'y3_{tag}'] = pd.concat(nxt, axis=1).mean(axis=1, skipna=False)
    return out.dropna(subset=['act', 'act12'])


def design(f, kind):
    if kind == 'base':
        cols = [f.act, f.tgt, f.car, f.att, f.act12]
    elif kind == 'chal':
        cols = [f.act, f.tgt, f.car, f.att, f.act12, f.exp]
    else:  # split (exploratory)
        cols = [f.td_res, f.nontd_res, f.exp, f.tgt, f.car, f.att, f.act12]
    return np.column_stack([np.ones(len(f))] + [np.asarray(c, float) for c in cols])


def ols(X, y, w=None):
    if w is None:
        w = np.ones(len(y))
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=1e-10)
    return beta


def res_coef(beta):
    """Challenger is y ~ act + exp + ...; with res = act - exp the coefficient on res is b_act and on exp is b_act + b_exp."""
    return beta[1], beta[1] + beta[6]


def cluster_boot(ids, stat, rng, n=B):
    codes, uniq = pd.factorize(ids)
    C = len(uniq)
    out = np.empty(n)
    for i in range(n):
        cnt = np.bincount(rng.integers(0, C, C), minlength=C)
        out[i] = stat(cnt[codes])
    return out


def cell(f, outcome, pos, rng):
    fp = f[f.position == pos].dropna(subset=[outcome])
    dev, val, hold = fp[fp.season.between(2021, 2023)], fp[fp.season == 2024], fp[fp.season == 2025]
    if min(len(dev), len(val), len(hold)) < 200:
        return {'n': [len(dev), len(val), len(hold)], 'verdict': 'INSUFFICIENT_DATA'}
    res = {'n': [int(len(dev)), int(len(val)), int(len(hold))]}
    yd = dev[outcome].to_numpy(float)
    Xc = design(dev, 'chal')
    bb, bc = ols(design(dev, 'base'), yd), ols(Xc, yd)

    def evaluate(b_b, b_c, test):
        y = test[outcome].to_numpy(float)
        return (y - design(test, 'base') @ b_b) ** 2, (y - design(test, 'chal') @ b_c) ** 2

    seb, sec = evaluate(bb, bc, val)
    res['val_mse_gain_pct'] = round(100 * (seb.sum() - sec.sum()) / seb.sum(), 3)
    tr = fp[fp.season.between(2021, 2024)]
    yt = tr[outcome].to_numpy(float)
    bb2, bc2 = ols(design(tr, 'base'), yt), ols(design(tr, 'chal'), yt)
    seb2, sec2 = evaluate(bb2, bc2, hold)
    d = seb2 - sec2
    res['hold_mse_gain_pct'] = round(100 * d.sum() / seb2.sum(), 3)
    cb = cluster_boot(hold.player_id.to_numpy(), lambda w: (w * d).sum() / (w * seb2).sum(), rng)
    lo, hi = np.quantile(cb, [ALPHA / 2, 1 - ALPHA / 2]) * 100
    res['hold_gain_ci_bonf'] = [round(float(lo), 3), round(float(hi), 3)]
    bres, bexp = res_coef(bc)
    cbs = cluster_boot(dev.player_id.to_numpy(), lambda w: res_coef(ols(Xc, yd, w))[0], rng, 500)
    res['b_res_dev'] = round(float(bres), 4)
    res['b_res_dev_ci_bonf'] = [round(float(x), 4) for x in np.quantile(cbs, [ALPHA / 2, 1 - ALPHA / 2])]
    res['b_exp_equiv_dev'] = round(float(bexp), 4)
    b2res, _ = res_coef(bc2)
    res['b_res_refit_2021_24'] = round(float(b2res), 4)
    ok = res['val_mse_gain_pct'] >= 1 and res['hold_mse_gain_pct'] >= 1 and res['hold_gain_ci_bonf'][0] > 0 and np.sign(bres) == np.sign(b2res)
    res['verdict'] = 'PREDICTIVE' if ok else ('INCONCLUSIVE' if res['hold_gain_ci_bonf'][1] >= 1 else 'DESCRIPTIVE_ONLY')
    return res


def exploratory(f, pos, outcome):
    fp = f[f.position == pos].dropna(subset=[outcome])
    tr, ho = fp[fp.season.between(2021, 2024)], fp[fp.season == 2025]
    yt = tr[outcome].to_numpy(float)
    b, bbase = ols(design(tr, 'split'), yt), ols(design(tr, 'base'), yt)
    y = ho[outcome].to_numpy(float)
    seb = ((y - design(ho, 'base') @ bbase) ** 2).sum()
    ses = ((y - design(ho, 'split') @ b) ** 2).sum()
    return {'b_td_res': round(float(b[1]), 4), 'b_nontd_res': round(float(b[2]), 4), 'b_exp': round(float(b[3]), 4),
            'hold_mse_gain_pct': round(100 * (seb - ses) / seb, 3)}


def tertiles(f, pos):
    """Descriptive: baseline error (actual next-3 PPR minus baseline prediction) by trailing-residual tertile, holdout 2025."""
    fp = f[f.position == pos].dropna(subset=['y3_ppr'])
    tr, ho = fp[fp.season.between(2021, 2024)], fp[fp.season == 2025].copy()
    b = ols(design(tr, 'base'), tr.y3_ppr.to_numpy(float))
    ho['err'] = ho.y3_ppr - design(ho, 'base') @ b
    q = pd.qcut(ho.res, 3, labels=['low_residual', 'mid', 'high_residual'])
    return {str(k): round(float(v), 3) for k, v in ho.groupby(q, observed=True).err.mean().items()}


def main(cache, out):
    df = load(cache)
    rng = np.random.default_rng(20261009)
    results = {'spec_sha256': SPEC_SHA, 'rows': int(len(df)), 'cells': {}, 'exploratory': {}, 'tertiles_hold_y3_ppr_k6': {}}
    for k in (3, 6):
        f = features(df, k)
        for pos in POS:
            for h in ('y1', 'y3'):
                for tag in ('ppr', 'rec', 'yds', 'tds'):
                    results['cells'][f'{pos}|k{k}|{h}_{tag}'] = cell(f, f'{h}_{tag}', pos, rng)
            if k == 6:
                results['exploratory'][pos] = {'y3_ppr': exploratory(f, pos, 'y3_ppr'), 'y1_ppr': exploratory(f, pos, 'y1_ppr')}
                results['tertiles_hold_y3_ppr_k6'][pos] = tertiles(f, pos)
    Path(out).write_text(json.dumps(results, indent=1))
    print('spec', SPEC_SHA[:16], 'rows', len(df))
    for key, r in results['cells'].items():
        print(key, r.get('n'), r.get('val_mse_gain_pct'), r.get('hold_mse_gain_pct'), r.get('hold_gain_ci_bonf'), r.get('b_res_dev'),
              r.get('b_exp_equiv_dev'), r.get('b_res_refit_2021_24'), r['verdict'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
