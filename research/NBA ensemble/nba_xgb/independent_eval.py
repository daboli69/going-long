"""Independent evaluation of frozen predictions.

Deliberately imports nothing from this package: it reads (a) a frozen long prediction CSV and (b) the ORIGINAL archived
ESPN schedule and team-box parquet files, derives outcomes itself, reconciles IDs/counts, and computes every metric
with its own code. Usage:
    python nba_xgb/independent_eval.py PREDICTIONS.csv [PREDICTIONS2.csv ...] --archive data/raw/archive --out report.json
Run it by path (not -m) so the package cannot be imported by accident.
"""
import argparse
import glob
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def latest(archive, kind, season):
    files = sorted(glob.glob(str(Path(archive) / f'{kind}_{season}' / '*.parquet')))
    return files[-1] if files else None


def outcomes_from_source(archive, seasons):
    """Home-win labels straight from the original schedule/box files, cross-checked against box points."""
    rows = []
    for s in seasons:
        sch = pd.read_parquet(latest(archive, 'schedule', s))
        box = pd.read_parquet(latest(archive, 'team_box', s), columns=['game_id', 'team_id', 'team_score', 'team_home_away', 'season_type'])
        sch = sch[sch.season_type.eq(2) & sch.status_type_completed.eq(True)]
        sch = sch[~sch.notes_headline.fillna('').str.contains(r'(?:Cup|Tournament).*Championship', case=False, regex=True)]
        sch = sch[~sch.status_type_name.fillna('').str.contains('POSTPONED|CANCEL', case=False)]
        h = box[box.team_home_away == 'home'].set_index('game_id').team_score.astype(float)
        a = box[box.team_home_away == 'away'].set_index('game_id').team_score.astype(float)
        d = pd.DataFrame({'game_id': sch.game_id.astype(str), 'sched_home': pd.to_numeric(sch.home_score, errors='coerce').values,
                          'sched_away': pd.to_numeric(sch.away_score, errors='coerce').values})
        d['box_home'] = d.game_id.map(h.rename(index=str))
        d['box_away'] = d.game_id.map(a.rename(index=str))
        d['season'] = s
        d['tipoff_utc'] = pd.to_datetime(sch.date.values, utc=True)
        rows.append(d)
    o = pd.concat(rows, ignore_index=True).drop_duplicates('game_id')
    o['agree'] = (o.sched_home == o.box_home) & (o.sched_away == o.box_away)
    o['home_win'] = (o.sched_home > o.sched_away).astype(float)
    return o


# ---------------------------------------------------------------- metrics (own implementation)
def ll_vec(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def auc(y, p):
    r = pd.Series(p).rank().values
    n1 = y.sum()
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def newton_logit(X, y, offset=0.0):
    beta = np.zeros(X.shape[1])
    for _ in range(60):
        mu = 1 / (1 + np.exp(-(offset + X @ beta)))
        W = mu * (1 - mu)
        H = (X * W[:, None]).T @ X + 1e-10 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - mu))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    return beta


def calib(y, p):
    z = np.log(np.clip(p, 1e-9, 1 - 1e-9) / (1 - np.clip(p, 1e-9, 1 - 1e-9)))
    b2 = newton_logit(np.column_stack([np.ones_like(z), z]), y)
    b1 = newton_logit(np.ones((len(z), 1)), y, offset=z)
    return float(b1[0]), float(b2[1])


def metric_row(y, p):
    ci, sl = calib(y, p)
    return {'n': int(len(y)), 'log_loss': float(ll_vec(y, p).mean()), 'brier': float(((p - y) ** 2).mean()),
            'accuracy': float(((p >= .5) == (y == 1)).mean()), 'auc': auc(y, p), 'calibration_intercept': ci, 'calibration_slope': sl}


def date_bootstrap(df, col, draws=4000, seed=7, block=None):
    rng = np.random.default_rng(seed)
    blocks = []
    for _, g in df.groupby('season'):
        t = g.groupby('game_date')[col].agg(['sum', 'size']).sort_index()
        blocks.append((t['sum'].values, t['size'].values))
    num, den = np.zeros(draws), np.zeros(draws)
    for s, c in blocks:
        k = len(s)
        if block is None:
            idx = rng.integers(0, k, (draws, k))
        else:
            nb = -(-k // block)
            st = rng.integers(0, k, (draws, nb))
            idx = ((st[:, :, None] + np.arange(block)) % k).reshape(draws, -1)[:, :k]
        num += s[idx].sum(1)
        den += c[idx].sum(1)
    b = num / den
    mean = sum(s.sum() for s, _ in blocks) / sum(c.sum() for _, c in blocks)
    return {'mean': float(mean), 'ci95': [float(x) for x in np.percentile(b, [2.5, 97.5])],
            'ci975': [float(x) for x in np.percentile(b, [1.25, 98.75])],
            'ci983': [float(x) for x in np.percentile(b, [0.85, 99.15])]}


def dm_test(df, col):
    """Diebold-Mariano on daily mean loss differentials, Newey-West (Bartlett) variance, bandwidth floor(n^(1/3))."""
    d = df.groupby('game_date')[col].mean().sort_index().values
    n = len(d)
    mu = d.mean()
    e = d - mu
    L = int(np.floor(n ** (1 / 3)))
    var = (e @ e) / n
    for k in range(1, L + 1):
        var += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / n
    stat = mu / np.sqrt(var / n)
    from math import erf, sqrt
    p = 2 * (1 - 0.5 * (1 + erf(abs(stat) / sqrt(2))))
    return {'mean_daily_diff': float(mu), 'dm_stat': float(stat), 'p_value': float(p), 'days': int(n), 'bandwidth': L}


def brier_decomposition(y, p, bins=10):
    b = np.minimum((p * bins).astype(int), bins - 1)
    ybar = y.mean()
    rel = res = 0.0
    for k in range(bins):
        m = b == k
        if m.any():
            pk, ok, nk = p[m].mean(), y[m].mean(), m.sum()
            rel += nk * (pk - ok) ** 2
            res += nk * (ok - ybar) ** 2
    n = len(y)
    return {'reliability': float(rel / n), 'resolution': float(res / n), 'uncertainty': float(ybar * (1 - ybar))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', default='xgb:elo_cal,xgb:logit,logit:elo_cal', help='a:b model pairs, a minus b')
    ap.add_argument('predictions', nargs='+')
    ap.add_argument('--archive', default='data/raw/archive')
    ap.add_argument('--out', default=None)
    ap.add_argument('--expect-sha', nargs='*', default=[], help='optional sha256 values, one per predictions file')
    a = ap.parse_args()
    report = {'inputs': {}, 'reconciliation': {}, 'metrics': {}, 'paired': {}}
    frames = []
    for i, f in enumerate(a.predictions):
        h = sha(f)
        report['inputs'][f] = h
        if a.expect_sha and a.expect_sha[i] != h:
            sys.exit(f'hash mismatch for {f}')
        frames.append(pd.read_csv(f, dtype={'game_id': str}))
    P = pd.concat(frames, ignore_index=True)
    models = sorted(P.model.unique())
    seasons = sorted(P.season.unique())
    o = outcomes_from_source(a.archive, seasons)
    o_ok = o[o.agree]
    # reconciliation
    rec = {'prediction_rows': len(P), 'models': models, 'duplicates_model_game': int(P.duplicated(['model', 'game_id']).sum()),
           'games_per_model': {m: int(P[P.model == m].game_id.nunique()) for m in models},
           'game_sets_identical_across_models': len({frozenset(P[P.model == m].game_id) for m in models}) == 1,
           'predictions_without_source_outcome': int((~P.game_id.isin(o_ok.game_id)).sum()),
           'source_games_with_score_disagreement_box_vs_schedule': o[~o.agree].game_id.tolist(),
           'probabilities_outside_open_unit_interval': int(((P.p_home <= 0) | (P.p_home >= 1)).sum()),
           }
    report['reconciliation'] = rec
    assert len(P) > 0 and len(o_ok) > 0 and all(v > 0 for v in rec['games_per_model'].values()), 'nothing to evaluate'
    assert rec['predictions_without_source_outcome'] == 0, 'predictions exist that cannot be matched to a source outcome'
    assert rec['duplicates_model_game'] == 0 and rec['game_sets_identical_across_models'], 'prediction sets differ across models'
    tip = o.set_index('game_id').tipoff_utc
    cut = pd.to_datetime(P.prediction_cutoff_utc, utc=True)
    rec['predictions_with_cutoff_at_or_after_tipoff'] = int((cut.values >= P.game_id.map(tip).values).sum())
    n_before = len(P)
    P = P.merge(o_ok[['game_id', 'home_win']], on='game_id', how='inner')
    assert len(P) == n_before > 0, 'joining outcomes dropped or emptied the prediction table'
    # the prediction file may legitimately omit a quarantined game; report source games with no prediction
    for s in seasons:
        src = set(o_ok[o_ok.season == s].game_id)
        pred = set(P[P.season == s].game_id)
        rec.setdefault('source_games_without_prediction', {})[int(s)] = sorted(src - pred)
    for name, grp in [('all', P)] + [(f'season_{s}', P[P.season == s]) for s in seasons]:
        report['metrics'][name] = {m: metric_row(g.home_win.values, g.p_home.values) for m, g in grp.groupby('model')}
    edges = [0, .3, .4, .5, .6, .7, .8, 1.0001]
    report['reliability'] = {}
    for m, g in P.groupby('model'):
        b = pd.cut(g.p_home, edges, right=False)
        t = g.groupby(b, observed=True).agg(n=('home_win', 'size'), mean_p=('p_home', 'mean'), observed=('home_win', 'mean'))
        t['se'] = np.sqrt(t.observed * (1 - t.observed) / t.n)
        report['reliability'][m] = [{'bin': str(k), **{c: float(v[c]) for c in t.columns}, 'n': int(v['n'])} for k, v in t.iterrows()]
    # paired differences on identical games
    W = P.pivot_table(index=['game_id', 'season', 'game_date'], columns='model', values='p_home').reset_index()
    y = P.drop_duplicates('game_id').set_index('game_id').home_win
    W['y'] = W.game_id.map(y).values
    report['brier_decomposition'] = {m: brier_decomposition(g.home_win.values, g.p_home.values) for m, g in P.groupby('model')}
    for a_m, b_m in [tuple(x.split(':')) for x in a.pairs.split(',')]:
        if a_m in W and b_m in W:
            W['d_ll'] = ll_vec(W.y.values, W[a_m].values) - ll_vec(W.y.values, W[b_m].values)
            W['d_br'] = (W[a_m] - W.y) ** 2 - (W[b_m] - W.y) ** 2
            entry = {}
            for scope, grp in [('all', W)] + [(f'season_{s}', W[W.season == s]) for s in seasons]:
                entry[scope] = {'diebold_mariano_newey_west': dm_test(grp, 'd_ll'),
                                'log_loss_diff_date_bootstrap': date_bootstrap(grp, 'd_ll'),
                                'log_loss_diff_7day_block_bootstrap': date_bootstrap(grp, 'd_ll', block=7),
                                'brier_diff_date_bootstrap': date_bootstrap(grp, 'd_br')}
            report['paired'][f'{a_m}_minus_{b_m}'] = entry
    text = json.dumps(report, indent=2)
    if a.out:
        Path(a.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
