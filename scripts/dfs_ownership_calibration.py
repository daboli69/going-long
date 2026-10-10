"""Calibrate and validate the Classic LINEUP ownership statistic against archived contests.

PRIVATE-DATA TOOL. Reads the licensed stat-api archive (ownership_frame.parquet, normalized/contest_*/lineups.parquet and
classic_ownership_model.json) READ-ONLY and writes ONE small JSON of aggregate calibration constants to --out. Nothing from the
archive (players, lineups, usernames, per-contest rows) is written. Put --out OUTSIDE the repository. The constants are meant to be
merged by hand into the private classic_ownership_model.json as a "lineup_calibration" block, which the public code reads if present.

Definitions (all in percent):
  player ownership   o_i   = share of contest lineups that hold player i
  lineup sum         A     = sum of o_i over the 9 roster slots of one lineup
  field-typical sum  Abar  = mean of A over the contest's lineups = sum_i o_i**2 / 100 (an exact identity; checked below)
  model sum          P     = same sum using MODEL ownership; sq = sum_i model_i**2 / 100 is the model's field-typical sum
The salary-only model is calibrated per player but shrunk toward the mean, so sq (and P) understate Abar. The calibration maps
(P, sq) -> expected realised A:   level = exp(a) * sq**b ;  A_hat = level * (1 + s * (clamp(P/sq) - 1))
Held-out: contests are ordered by date; the first 2/3 fit the constants, the last 1/3 scores them.
"""
import argparse, json, sys
import numpy as np
import pandas as pd


def model_ownership(group, model):
    spec = model['models']['salary_only']
    out = pd.Series(np.nan, index=group.index)
    for pos in model['positions']:
        g = group[group.position == pos]
        if g.empty:
            continue
        cfg = spec[pos]
        s = (g.salary - 5000) / 1000
        higher = np.array([(g.salary > x).sum() for x in g.salary])
        feats = {'s': s.values, 's2': (s ** 2).values, 'lrank': np.log1p(higher)}
        eta = sum(b * feats[n] for n, b in zip(cfg['features'], cfg['beta']))
        e = np.exp(eta - eta.max())
        out[g.index] = np.minimum(100, model['slot_totals'][pos] * e / e.sum())
    return out


def load_contests(root, model, min_lineups=2000):
    frame = pd.read_parquet(root + '/ownership_frame.parquet')
    frame = frame[frame.game_type == 'classic']
    contests = []
    for cid, g in frame.groupby('contest_id'):
        g = g.drop_duplicates('player_key').copy()
        if g.field_pct.sum() < 850:  # incomplete ownership coverage
            continue
        try:
            lineups = pd.read_parquet(f'{root}/normalized/contest_{cid}/lineups.parquet')
        except Exception:
            continue
        seats = lineups[[f'seat{i}' for i in range(9)]]
        own = dict(zip(g.player_key, g.field_pct))
        a = seats.apply(lambda c: c.map(own))
        keep = a.notna().all(axis=1)
        if keep.sum() < min_lineups:
            continue
        pred = model_ownership(g, model)
        pm = dict(zip(g.player_key, pred))
        s = seats[keep]
        contests.append(dict(cid=int(cid), date=str(g.date.iloc[0]), A=a[keep].sum(axis=1).values,
                             P=s.apply(lambda c: c.map(pm)).sum(axis=1).values, sq=float((pred ** 2).sum() / 100),
                             identity=float((g.field_pct ** 2).sum() / 100)))
    contests.sort(key=lambda c: c['date'])
    return contests


def fit(contests):
    x = np.array([[1, np.log(c['sq'])] for c in contests])
    y = np.array([np.log(c['A'].mean()) for c in contests])
    (a, b) = np.linalg.lstsq(x, y, rcond=None)[0]
    num = den = 0.0
    for c in contests:
        level = np.exp(a) * c['sq'] ** b
        r = np.clip(c['P'] / c['sq'], .4, 1.6) - 1
        z = c['A'] / level - 1
        num += (r * z).sum(); den += (r * r).sum()
    return dict(a=float(a), b=float(b), s=float(max(0.0, min(1.0, num / den))), clamp=[.4, 1.6])


def predict(c, p):
    level = np.exp(p['a']) * c['sq'] ** p['b']
    return level * (1 + p['s'] * (np.clip(c['P'] / c['sq'], *p['clamp']) - 1)), level


def score(contests, p):
    naive = np.mean([np.abs(c['P'] - c['A']).mean() for c in contests])
    cal = np.mean([np.abs(predict(c, p)[0] - c['A']).mean() for c in contests])
    rel_n = np.mean([c['sq'] / c['A'].mean() - 1 for c in contests])
    rel_c = np.mean([predict(c, p)[1] / c['A'].mean() - 1 for c in contests])
    ratio = np.concatenate([c['A'] / predict(c, p)[0] for c in contests])
    return dict(contests=len(contests), lineups=int(sum(len(c['A']) for c in contests)),
                lineup_mae_uncalibrated=float(naive), lineup_mae_calibrated=float(cal),
                field_level_bias_uncalibrated=float(rel_n), field_level_bias_calibrated=float(rel_c),
                field_level_mae_pct_calibrated=float(np.mean([abs(predict(c, p)[1] / c['A'].mean() - 1) for c in contests])),
                within_contest_corr_P_vs_A=float(np.mean([np.corrcoef(c['P'], c['A'])[0, 1] for c in contests])),
                realised_over_estimate_p10_p90=[float(np.quantile(ratio, .1)), float(np.quantile(ratio, .9))])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--archive', required=True, help='path to the private StatApi folder (read-only)')
    ap.add_argument('--out', required=True, help='aggregate JSON to write (outside the repository)')
    ap.add_argument('--merged-out', help='optional: write a COPY of classic_ownership_model.json with the lineup_calibration block added (private file; keep outside the repository)')
    args = ap.parse_args()
    model = json.load(open(args.archive + '/classic_ownership_model.json'))
    contests = load_contests(args.archive, model)
    if len(contests) < 12:
        sys.exit('Too few archived Classic contests for a held-out calibration.')
    ident = max(abs(c['A'].mean() - c['identity']) / c['identity'] for c in contests)
    k = len(contests) * 2 // 3
    train, test = contests[:k], contests[k:]
    p_train = fit(train)
    report = dict(schema='going-classic-lineup-calibration-v1', contests=len(contests),
                  split=dict(train=[train[0]['date'], train[-1]['date'], len(train)], test=[test[0]['date'], test[-1]['date'], len(test)]),
                  identity_max_rel_diff=float(ident), heldout=score(test, p_train), train_fit=score(train, p_train),
                  params=fit(contests), params_train_only=p_train,
                  note='Aggregate constants only. heldout = constants fitted on earlier contests scored on later contests.')
    json.dump(report, open(args.out, 'w'), indent=1)
    if args.merged_out:
        json.dump({**model, 'lineup_calibration': {k: report[k] for k in ('schema', 'contests', 'split', 'heldout', 'params', 'note')}}, open(args.merged_out, 'w'))
    print(json.dumps({k: report[k] for k in ('contests', 'split', 'identity_max_rel_diff', 'heldout', 'params')}, indent=1))


if __name__ == '__main__':
    main()
