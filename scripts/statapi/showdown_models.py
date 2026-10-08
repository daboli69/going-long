"""Private Showdown models trained on the archived stat-api fields. Only information available BEFORE lock is used as a feature:
  salary, position, team, rank/share of salary inside the pool, pool size, field size (the DK salary file and contest listing have all of these).
Actual ownership, scores and results are used only as TARGETS. Out-of-fold predicted ownership feeds the duplication model so actual ownership never leaks into it.

Models are log-linear so their coefficients can be exported to a PRIVATE json that the browser loads from the user's disk. They must not be committed or served publicly
(stat-api licence: no publishing of the data or anything made from it).

    python scripts/statapi/showdown_models.py <archive_root>        -> <archive_root>/showdown_models.json , showdown_models_report.json
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HOLDOUT_FROM = '2025-01-01'  # contests on/after this date are never used to fit anything that is reported as validation
POS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']


def pool_features(pool):
    """Per-player rows (one per player and role) with pre-lock features. `pool` has contest_id, slot, player_key, position, team, salary, entries."""
    out = pool.copy()
    out['role'] = np.where(out.slot.isin(['CPT', 'MVP']), 'CPT', 'FLEX')
    g = out.groupby(['contest_id', 'role'])
    out['salary_rank'] = g.salary.rank(ascending=False, method='first')
    out['rank_pct'] = out.salary_rank / g.salary.transform('size')
    out['salary_share'] = out.salary / g.salary.transform('sum')
    out['log_salary'] = np.log(out.salary.clip(lower=100))
    out['n_pool'] = g.salary.transform('size')
    out['log_entries'] = np.log(out.entries)
    team_sal = out.groupby(['contest_id', 'role', 'team']).salary.transform('sum')
    out['team_salary_share'] = team_sal / g.salary.transform('sum')
    for p in POS:
        out['pos_' + p] = (out.position == p).astype(float)
    out['top3'] = (out.salary_rank <= 3).astype(float)
    return out


OWN_FEATURES = ['log_salary', 'rank_pct', 'salary_share', 'n_pool', 'log_entries', 'team_salary_share', 'top3'] + ['pos_' + p for p in POS]


class LogLinear:
    """Ridge regression of log(ownership + 0.1) so the output is positive and relative errors matter; exportable as plain coefficients."""

    def __init__(self, alpha=3.0):
        self.alpha = alpha

    def fit(self, X, y):
        X = np.asarray(X, float)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1
        Z = (X - self.mu) / self.sd
        t = np.log(np.asarray(y, float) + 0.1)
        self.b0 = t.mean()
        self.w = np.linalg.solve(Z.T @ Z + self.alpha * np.eye(Z.shape[1]), Z.T @ (t - self.b0))
        resid = t - (self.b0 + Z @ self.w)
        self.smear = float(np.mean(np.exp(resid)))  # Duan smearing so the back-transformed mean is not biased low
        return self

    def predict(self, X):
        Z = (np.asarray(X, float) - self.mu) / self.sd
        return np.clip(self.smear * np.exp(self.b0 + Z @ self.w) - 0.1 * self.smear, 0, 100)

    def export(self, names):
        return {'features': names, 'mean': self.mu.tolist(), 'sd': self.sd.tolist(), 'intercept': float(self.b0), 'coef': self.w.tolist(), 'smear': self.smear}


BINS = 30
TOTAL = {'CPT': 100.0, 'FLEX': 500.0}


def group_of(position):
    return np.where(position == 'QB', 'QB', np.where(np.isin(position, ['DST', 'K']), 'DK', 'SKILL'))


class TableOwnership:
    """Mean ownership by (position group, absolute salary rank bin), normalised inside each slate so CPT sums to 100% and FLEX to 500%. Exportable as a small table."""

    def __init__(self, role):
        self.role = role

    def fit(self, rows, target):
        rows = rows.assign(grp=group_of(rows.position.to_numpy()), rb=np.minimum(rows.salary_rank - 1, BINS - 1).astype(int))
        overall = rows[target].mean()
        t = rows.groupby(['grp', 'rb'])[target].mean()
        self.table = {g: [float(t.get((g, b), np.nan)) for b in range(BINS)] for g in ('QB', 'SKILL', 'DK')}
        for g in self.table:  # fill empty bins from the previous bin, then the overall mean
            last = overall
            for b in range(BINS):
                if np.isnan(self.table[g][b]):
                    self.table[g][b] = last
                last = self.table[g][b]
        return self

    def raw(self, rows):
        grp = group_of(rows.position.to_numpy())
        rb = np.minimum(rows.salary_rank.to_numpy() - 1, BINS - 1).astype(int)
        return np.array([self.table[g][b] for g, b in zip(grp, rb)])

    def predict(self, rows):
        raw = pd.Series(self.raw(rows), index=rows.index)
        total = raw.groupby(rows.contest_id).transform('sum')
        return (raw * TOTAL[self.role] / total).clip(0, 100).to_numpy()

    def export(self):
        return {'kind': 'rank_table', 'bins': BINS, 'table': self.table, 'total': TOTAL[self.role], 'note': 'rank = 1 + number of same-role players with higher salary; last bin covers all lower ranks'}


def load_showdown(root):
    root = Path(root)
    df = pd.read_parquet(root / 'ownership_frame.parquet')
    sd = df[df.game_type == 'showdown'].copy()
    sd = sd[sd.salary.notna() & sd.position.notna() & sd.team.notna()]
    return pool_features(sd)


def fit_ownership(sd):
    models, report = {}, {}
    for role, target in (('CPT', 'cpt_field_pct'), ('FLEX', 'flex_field_pct')):
        rows = sd[(sd.role == role) & sd[target].notna()]
        train, test = rows[rows.date < HOLDOUT_FROM], rows[rows.date >= HOLDOUT_FROM]
        m = TableOwnership(role).fit(train, target)
        pred = m.predict(test)
        report[role] = {'train_rows': int(len(train)), 'test_rows': int(len(test)), 'test_contests': int(test.contest_id.nunique()), 'mae': float((test[target] - pred).abs().mean()),
                        'corr': float(np.corrcoef(test[target], pred)[0, 1]), 'bias': float((pred - test[target]).mean()), 'naive_mae_constant': float((test[target] - train[target].mean()).abs().mean())}
        models[role] = TableOwnership(role).fit(rows, target).export()  # tonight's model uses every archived contest
    return models, report


def oof_ownership(sd):
    """Out-of-fold predicted CPT/FLEX ownership for every archived row (contest-grouped folds) so the duplication model never sees actual ownership."""
    sd = sd.copy()
    ids = sorted(sd.contest_id.unique())
    sd['fold'] = sd.contest_id.map({c: i % 5 for i, c in enumerate(ids)})
    sd['own_pred'] = np.nan
    for role, target in (('CPT', 'cpt_field_pct'), ('FLEX', 'flex_field_pct')):
        for f in range(5):
            tr = sd[(sd.role == role) & (sd.fold != f) & sd[target].notna()]
            te = sd[(sd.role == role) & (sd.fold == f)]
            m = TableOwnership(role).fit(tr, target)
            sd.loc[te.index, 'own_pred'] = m.predict(te)
    return sd


def lineup_rows(root, sd, per_contest=4000, seed=7):
    """One row per sampled lineup: duplicate count in the whole field, plus pre-lock lineup features built from OUT-OF-FOLD predicted ownership."""
    rng = np.random.default_rng(seed)
    parts = []
    for cid, g in sd.groupby('contest_id'):
        lin = pd.read_parquet(Path(root) / 'normalized' / f'contest_{cid}' / 'lineups.parquet')
        seat_cols = [c for c in lin.columns if c.startswith('seat')]
        seats = lin[seat_cols].to_numpy()
        counts = collections.Counter(map(tuple, seats))
        idx = rng.choice(len(lin), size=min(per_contest, len(lin)), replace=False)
        cpt = g[g.role == 'CPT'].drop_duplicates('player_key').set_index('player_key')
        flex = g[g.role == 'FLEX'].drop_duplicates('player_key').set_index('player_key')
        sub = seats[idx]
        keep = np.isin(sub[:, 0], cpt.index.to_numpy()) & np.isin(sub[:, 1:], flex.index.to_numpy()).all(axis=1)
        sub = sub[keep]
        if len(sub) == 0:
            continue
        dup = np.array([counts[tuple(r)] for r in sub])
        c_own, c_rank, c_sal, c_pos = cpt.own_pred.reindex(sub[:, 0]).to_numpy(), cpt.rank_pct.reindex(sub[:, 0]).to_numpy(), cpt.salary.reindex(sub[:, 0]).to_numpy(), cpt.position.reindex(sub[:, 0]).to_numpy()
        c_team = cpt.team.reindex(sub[:, 0]).to_numpy()
        f_own = np.column_stack([flex.own_pred.reindex(sub[:, j]).to_numpy() for j in range(1, 6)])
        f_rank = np.column_stack([flex.rank_pct.reindex(sub[:, j]).to_numpy() for j in range(1, 6)])
        f_sal = np.column_stack([flex.salary.reindex(sub[:, j]).to_numpy() for j in range(1, 6)])
        f_team = np.column_stack([flex.team.reindex(sub[:, j]).to_numpy() for j in range(1, 6)])
        same = (f_team == c_team[:, None]).sum(axis=1) + 1
        salary = c_sal + f_sal.sum(axis=1)
        parts.append(pd.DataFrame({'contest_id': cid, 'date': g.date.iloc[0], 'entries': len(lin), 'dup': dup, 'cpt_own': c_own, 'sum_flex_own': f_own.sum(axis=1), 'min_flex_own': f_own.min(axis=1),
                                   'log_prod_own': np.log(np.maximum(c_own, 0.05) / 100) + np.log(np.clip(f_own, 0.05, 100) / 100).sum(axis=1), 'salary_used': salary, 'unused': 50000 - salary,
                                   'cpt_salary_rank_pct': c_rank, 'max_team': np.maximum(same, 6 - same), 'n_stars': (f_rank <= 0.1).sum(axis=1) + (c_rank <= 0.1).astype(int),
                                   'cpt_pos_QB': (c_pos == 'QB').astype(float), 'log_entries': np.log(len(lin))}))
    out = pd.concat(parts, ignore_index=True)
    return out.dropna(subset=DUP_FEATURES + ['dup'])


DUP_FEATURES = ['cpt_own', 'sum_flex_own', 'min_flex_own', 'log_prod_own', 'unused', 'cpt_salary_rank_pct', 'max_team', 'n_stars', 'cpt_pos_QB', 'log_entries']


class DupModel:
    """Linear model of log(dup count) on pre-lock lineup features; exportable. dup >= 1 always (the lineup itself)."""

    def fit(self, X, dup, alpha=3.0):
        X = np.asarray(X, float)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1
        Z = (X - self.mu) / self.sd
        t = np.log(np.asarray(dup, float))
        self.b0 = t.mean()
        self.w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (t - self.b0))
        self.resid_sd = float(np.std(t - (self.b0 + Z @ self.w)))
        return self

    def predict_log(self, X):
        return self.b0 + ((np.asarray(X, float) - self.mu) / self.sd) @ self.w

    def export(self):
        return {'features': DUP_FEATURES, 'mean': self.mu.tolist(), 'sd': self.sd.tolist(), 'intercept': float(self.b0), 'coef': self.w.tolist(), 'resid_sd': self.resid_sd}


def fit_duplication(lineups):
    train, test = lineups[lineups.date < HOLDOUT_FROM], lineups[lineups.date >= HOLDOUT_FROM]
    m = DupModel().fit(train[DUP_FEATURES], train.dup)
    pl = m.predict_log(test[DUP_FEATURES])
    t = np.log(test.dup.to_numpy())
    # scale by field size: dup counts grow with the field, which the log_entries feature already carries
    report = {'train_lineups': int(len(train)), 'test_lineups': int(len(test)), 'test_contests': int(test.contest_id.nunique()),
              'corr_log': float(np.corrcoef(pl, t)[0, 1]), 'mae_log': float(np.abs(pl - t).mean()), 'mae_log_constant': float(np.abs(t - np.log(train.dup).mean()).mean()),
              'rank_corr': float(pd.Series(pl).corr(pd.Series(t), method='spearman'))}
    # decision-relevant check: lineups the model calls low-duplication (bottom decile) vs top decile, actual duplicate counts
    q = pd.qcut(pl, 10, labels=False, duplicates='drop')
    report['actual_median_dup_by_predicted_decile'] = [float(np.median(test.dup.to_numpy()[q == d])) for d in sorted(set(q))]
    report['actual_unique_share_by_predicted_decile'] = [float((test.dup.to_numpy()[q == d] == 1).mean()) for d in sorted(set(q))]
    final = DupModel().fit(lineups[DUP_FEATURES], lineups.dup)
    return final.export(), report


def main(root):
    sd = load_showdown(root)
    own_models, own_report = fit_ownership(sd)
    sd = oof_ownership(sd)
    lineups = lineup_rows(root, sd)
    dup_model, dup_report = fit_duplication(lineups)
    Path(root, 'showdown_models.json').write_text(json.dumps({'schema': 'going-private-showdown-models-v1', 'ownership': own_models, 'duplication': dup_model, 'salary_cap': 50000,
                                                              'notice': 'Derived from licensed stat-api data. Private research file: do not publish, commit or serve.'}, indent=1), encoding='utf-8')
    Path(root, 'showdown_models_report.json').write_text(json.dumps({'ownership_holdout': own_report, 'duplication_holdout': dup_report, 'archived_showdown_contests': int(sd.contest_id.nunique())}, indent=1), encoding='utf-8')
    print(json.dumps({'ownership_holdout': own_report, 'duplication_holdout': dup_report}, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
