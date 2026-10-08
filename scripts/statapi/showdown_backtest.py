"""Backtest of Showdown lineup construction against the ARCHIVED actual fields (private; needs the local stat-api archive).

For each archived Showdown contest we build lineups from pre-lock inputs only (salaries, the provider's archived projection and spread, out-of-fold predicted ownership, the duplication
model), then score them with the ACTUAL player points against the whole historical field: rank percentile, top-1%, cash (inside the paid places), payout and ROI with the field's
own payout schedule, and whether an identical lineup existed in the field.

Selection of the construction weights uses contests before 2025-01-01 only. Contests from 2025-01-01 on are evaluated once with the weights frozen.

Limits (stated in the report): the provider's projection engine is current and flagged backfilled/fallback, so projection quality here is optimistic; payouts ignore the prize split
among tied identical lineups beyond averaging; our lineups are not added to the field; fields are sampled (coverage recorded).
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from statapi import showdown_models as sm  # noqa: E402

K = 18  # candidate pool: the 18 best by projection / value
HOLDOUT_FROM = sm.HOLDOUT_FROM
TYPES = ['balanced', 'ceiling', 'lowdup', 'leverage', 'best']


def candidates(pool_c):
    flex = pool_c[pool_c.role == 'FLEX'].set_index('player_key')
    cpt = pool_c[pool_c.role == 'CPT'].set_index('player_key')
    common = [k for k in flex.index if k in cpt.index and pd.notna(flex.at[k, 'proj_pts']) and flex.at[k, 'salary'] > 0]
    f = flex.loc[common]
    score = f.proj_pts.rank(ascending=False) + 0.5 * (f.proj_pts / f.salary).rank(ascending=False)
    keep = list(score.sort_values().index[:K])
    return keep, flex.loc[keep], cpt.loc[keep]


def build_lineups(flex, cpt, dup_model, own_cpt, own_flex, entries):
    n = len(flex)
    ids = flex.index.to_numpy()
    teams = flex.team.to_numpy()
    sal_f, sal_c = flex.salary.to_numpy(float), cpt.salary.to_numpy(float)
    mean_f = flex.proj_pts.to_numpy(float)
    sd_f = flex.proj_sd.fillna(flex.proj_pts * 0.5).to_numpy(float)
    pos = flex.position.to_numpy()
    rank_pct_f = flex.rank_pct.to_numpy(float)
    rank_pct_c = cpt.rank_pct.to_numpy(float)
    combos = np.array(list(itertools.combinations(range(n), 5)))
    out = []
    for c in range(n):
        mask = ~(combos == c).any(axis=1)
        cm = combos[mask]
        salary = sal_c[c] + sal_f[cm].sum(axis=1)
        ok = salary <= 50000
        tm = np.array([[teams[c] != teams[j] for j in row] for row in cm[ok]]).any(axis=1) if ok.any() else np.array([], bool)
        cm, salary = cm[ok][tm], salary[ok][tm]
        if len(cm) == 0:
            continue
        mean = 1.5 * mean_f[c] + mean_f[cm].sum(axis=1)
        # variance: independent players plus a measured quarterback-pass catcher covariance on the same team (0.30 average of the QB~WR1/WR2/TE1 estimates)
        var = (1.5 * sd_f[c]) ** 2 + (sd_f[cm] ** 2).sum(axis=1)
        qb_c = pos[c] == 'QB'
        for j in range(cm.shape[1]):
            for k in range(j + 1, cm.shape[1]):
                pj, pk = cm[:, j], cm[:, k]
                pair = ((pos[pj] == 'QB') & np.isin(pos[pk], ['WR', 'TE']) & (teams[pj] == teams[pk])) | ((pos[pk] == 'QB') & np.isin(pos[pj], ['WR', 'TE']) & (teams[pj] == teams[pk]))
                var += 2 * 0.30 * pair * sd_f[pj] * sd_f[pk]
        if qb_c:
            mate = np.isin(pos[cm], ['WR', 'TE']) & (teams[cm] == teams[c])
            var += 2 * 0.30 * (1.5 * sd_f[c]) * (sd_f[cm] * mate).sum(axis=1)
        sd = np.sqrt(var)
        oc, of = own_cpt[c], own_flex[cm]
        # duplication features exactly as in showdown_models.lineup_rows
        team_counts = np.array([max((teams[c] == teams[cm[i]]).sum() + 1, len(cm[i]) + 1 - (teams[c] == teams[cm[i]]).sum()) for i in range(len(cm))]) if False else None
        same = (teams[cm] == teams[c]).sum(axis=1) + 1
        max_team = np.maximum(same, 6 - same)
        n_stars = (rank_pct_f[cm] <= 0.1).sum(axis=1) + int(rank_pct_c[c] <= 0.1)
        feats = np.column_stack([np.full(len(cm), oc), of.sum(axis=1), of.min(axis=1), np.log(max(oc, 0.05) / 100) + np.log(np.clip(of, 0.05, 100) / 100).sum(axis=1), 50000 - salary,
                                 np.full(len(cm), rank_pct_c[c]), max_team, n_stars, np.full(len(cm), float(qb_c)), np.full(len(cm), np.log(entries))])
        logdup = dup_model.predict_log(feats)
        for i in range(len(cm)):
            pass
        out.append((np.full(len(cm), c), cm, salary, mean, sd, logdup, oc + of.sum(axis=1)))
    cap = np.concatenate([o[0] for o in out])
    flexi = np.concatenate([o[1] for o in out])
    return ids, cap, flexi, np.concatenate([o[2] for o in out]), np.concatenate([o[3] for o in out]), np.concatenate([o[4] for o in out]), np.concatenate([o[5] for o in out]), np.concatenate([o[6] for o in out])


def objective(kind, mean, sd, logdup, own_sum, lam, gamma):
    if kind == 'balanced':
        return mean
    if kind == 'ceiling':
        return mean + 1.2816 * sd
    if kind == 'lowdup':
        return mean - lam * logdup
    if kind == 'leverage':
        return mean - gamma * own_sum
    return mean + 1.2816 * sd - lam * logdup  # best


def pick(score, cap, flexi, count=20, max_shared=3):
    order = np.argsort(-score)
    chosen = []
    for i in order[:20000]:
        members = set([('C', cap[i])] + [('F', x) for x in flexi[i]])
        if all(len(members & s) <= max_shared + 0 for s in chosen):
            chosen.append(members)
            yield i
            if len(chosen) >= count:
                return


def evaluate_contest(contest, pool_c, lineups_field, dup_model, lam, gamma, kinds=TYPES):
    keep, flex, cpt = candidates(pool_c)
    if len(keep) < 8:
        return None
    entries = len(lineups_field)
    own_c = cpt.own_pred.to_numpy(float)
    own_f = flex.own_pred.to_numpy(float)
    ids, cap, flexi, salary, mean, sd, logdup, own_sum = build_lineups(flex, cpt, dup_model, own_c, own_f, entries)
    pts_c = cpt.fantasy_points.to_numpy(float)
    pts_f = flex.fantasy_points.to_numpy(float)
    field_pts = np.sort(lineups_field.points.to_numpy())[::-1]
    field_pay = lineups_field.sort_values('points', ascending=False).payout_cents.fillna(0).to_numpy()
    seat_cols = [c for c in lineups_field.columns if c.startswith('seat')]
    field_keys = set(map(tuple, np.column_stack([lineups_field[seat_cols[0]].to_numpy(), np.sort(lineups_field[seat_cols[1:]].to_numpy(), axis=1)])))
    fee = contest['entry_fee_cents']
    paid = contest['paid_places']
    res = {}
    for kind in kinds:
        sc = objective(kind, mean, sd, logdup, own_sum, lam, gamma)
        rows = []
        for i in pick(sc, cap, flexi):
            actual = pts_c[cap[i]] * 1.0 + pts_f[flexi[i]].sum()
            if np.isnan(actual):
                continue
            rank = 1 + int((field_pts > actual + 1e-9).sum())
            tie = int((np.abs(field_pts - actual) <= 1e-9).sum())
            pay = field_pay[min(rank - 1 + tie // 2, len(field_pay) - 1)] if rank <= len(field_pay) else 0.0
            key = (ids[cap[i]],) + tuple(np.sort(ids[flexi[i]]))
            rows.append({'rank_pct': rank / entries, 'top1': float(rank <= max(1, 0.01 * entries)), 'cash': float(rank <= paid * entries / max(contest['entry_count'], 1)),
                         'payout': pay * contest['payout_scale'], 'fee': fee / 100.0, 'unique': float(key not in field_keys), 'pred_logdup': float(logdup[i]), 'unused': 50000 - salary[i]})
        res[kind] = rows
    return res


def run(root, lam, gamma, split, kinds=TYPES, max_contests=None):
    sd = sm.load_showdown(root)
    sd = sm.oof_ownership(sd)
    sd = sd[sd.proj_pts.notna()]
    lineups_all = None
    models = json.load(open(Path(root) / 'showdown_models.json', encoding='utf-8'))['duplication']
    dup = sm.DupModel()
    dup.mu, dup.sd, dup.b0, dup.w = np.array(models['mean']), np.array(models['sd']), models['intercept'], np.array(models['coef'])
    meta = pd.read_parquet(Path(root) / 'ownership_frame.parquet', columns=['contest_id', 'entry_fee_cents', 'entries']).drop_duplicates('contest_id').set_index('contest_id')
    all_rows = {k: [] for k in kinds}
    n = 0
    for cid, g in sd.groupby('contest_id'):
        date = g.date.iloc[0]
        if (split == 'train' and date >= HOLDOUT_FROM) or (split == 'test' and date < HOLDOUT_FROM):
            continue
        lin = pd.read_parquet(Path(root) / 'normalized' / f'contest_{cid}' / 'lineups.parquet')
        info = json.load(open(Path(root) / 'normalized' / f'contest_{cid}' / 'validation.json', encoding='utf-8'))['contest_meta']
        vr = json.load(open(Path(root) / 'normalized' / f'contest_{cid}' / 'validation.json', encoding='utf-8'))
        prize = (info['prize_pool_cents'] or 0) / 100.0
        # the archive's payout field is in DOLLARS for almost every contest (its total matches the prize pool in dollars); a few are in cents
        scale = 0.01 if prize and vr['total_payout_cents'] / prize > 10 else 1.0
        contest = {'payout_scale': scale, 'entry_fee_cents': info['entry_fee_cents'] or 0, 'paid_places': info['paid_places'] or 0, 'entry_count': info['entry_count']}
        if contest['entry_fee_cents'] <= 0:
            continue
        out = evaluate_contest(contest, g, lin, dup, lam, gamma, kinds)
        if not out:
            continue
        for k, rows in out.items():
            for r in rows:
                r['contest_id'], r['date'] = cid, date
            all_rows[k] += rows
        n += 1
        if max_contests and n >= max_contests:
            break
    return {k: pd.DataFrame(v) for k, v in all_rows.items()}, n


def summarize(frames):
    out = {}
    for k, df in frames.items():
        if df.empty:
            continue
        df = df.copy()
        df['roi'] = (df.payout - df.fee) / df.fee
        per_contest = df.groupby('contest_id').agg(top1=('top1', 'mean'), cash=('cash', 'mean'), roi=('roi', 'mean'), unique=('unique', 'mean'), rank_pct=('rank_pct', 'mean'))
        out[k] = {'lineups': int(len(df)), 'contests': int(df.contest_id.nunique()), 'top1_rate': float(df.top1.mean()), 'cash_rate': float(df.cash.mean()), 'mean_roi': float(df.roi.mean()),
                  'median_rank_pct': float(df.rank_pct.median()), 'unique_share': float(df.unique.mean()), 'mean_unused_salary': float(df.unused.mean()),
                  'roi_contest_cluster_se': float(per_contest.roi.std() / np.sqrt(max(len(per_contest), 1)))}
    return out


if __name__ == '__main__':
    root = sys.argv[1]
    split = sys.argv[2]  # train | test
    lam = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    gamma = float(sys.argv[4]) if len(sys.argv) > 4 else 0.1
    frames, n = run(root, lam, gamma, split)
    print(json.dumps({'split': split, 'contests': n, 'lambda': lam, 'gamma': gamma, 'results': summarize(frames)}, indent=1))
