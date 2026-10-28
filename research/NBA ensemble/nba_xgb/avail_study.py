"""Does knowing who plays beat knowing team strength? Development, freeze and one-pass test (see docs/NBA_AVAIL_PREREGISTRATION.md)."""
from __future__ import annotations
import hashlib
import json
import stat
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from . import metrics, models

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research_nba_xgb'
DOCS = ROOT / 'docs'
BASE = ['elo_diff', 'recent_net_diff', 'rest_diff', 'b2b_home', 'b2b_away', 'home_court']
AVAIL = ['full_value_diff', 'avail_effect_diff', 'missing_min_diff']
AV_COLS = AVAIL + ['avail_value_diff', 'oracle_value_diff']
FIRST = 2017
DEV_FOLD = 2024
TEST_FOLDS = (2025, 2026)
CAL_FOLDS = (2022, 2023)


def load_table():
    F = pd.read_parquet(OUT / 'features_lag1.parquet')
    A = pd.read_parquet(OUT / 'avail_features.parquet')
    keep = ['game_id', 'rapm_refit_day', 'full_value_diff', 'avail_effect_diff', 'missing_min_diff', 'avail_value_diff',
            'oracle_value_diff']
    T = F.merge(A[keep], on='game_id', how='left')
    T['has_avail'] = T.full_value_diff.notna().astype(float)
    return T


def train_rows(T, fold, window=None):
    return T[T.eligible & T.season.between(FIRST, fold - 1)]


def eval_rows(T, fold):
    return T[T.eligible & (T.season == fold)]


def matrix(df, feats, na_zero=True):
    X = df[feats].values.astype(float)
    if na_zero:
        X = np.nan_to_num(X, nan=0.0)
        if any(f in AV_COLS for f in feats):
            X = np.column_stack([X, df.has_avail.values])
    return X


class LogitNA:
    def __init__(self, feats, C):
        self.feats, self.C = list(feats), C

    def fit(self, df):
        X = matrix(df, self.feats)
        self.sc = StandardScaler().fit(X)
        self.m = LogisticRegression(C=self.C, max_iter=3000).fit(self.sc.transform(X), df.home_win.values)
        return self

    def predict(self, df):
        return self.m.predict_proba(self.sc.transform(matrix(df, self.feats)))[:, 1]


class EloCal:
    def fit(self, df):
        self.m = LogisticRegression(penalty=None, max_iter=1000).fit(df[models.ELO_FEATS].values, df.home_win.values)
        return self

    def predict(self, df):
        return self.m.predict_proba(df[models.ELO_FEATS].values)[:, 1]


class XGBNA:
    def __init__(self, feats, cfg, rounds):
        self.feats, self.cfg, self.rounds = list(feats), dict(cfg), int(rounds)

    def fit(self, df):
        self.m = models.make_xgb(self.cfg, self.rounds).fit(df[self.feats].values.astype(float), df.home_win.values)
        return self

    def predict(self, df):
        return self.m.predict_proba(df[self.feats].values.astype(float))[:, 1]


def staged_xgb(train, test, feats, cfg, grid=models.R_GRID):
    m = models.make_xgb(cfg, max(grid)).fit(train[feats].values.astype(float), train.home_win.values)
    X = test[feats].values.astype(float)
    return {r: m.predict_proba(X, iteration_range=(0, r))[:, 1] for r in grid}


def develop(T, log=print):
    tr, ev = train_rows(T, DEV_FOLD), eval_rows(T, DEV_FOLD)
    y = ev.home_win.values
    res = {'dev_fold': DEV_FOLD, 'n_train': len(tr), 'n_train_with_avail': int(tr.has_avail.sum()), 'n_eval': len(ev)}
    for name, feats in (('base', BASE), ('avail', BASE + AVAIL)):
        scores = {C: metrics.logloss(y, LogitNA(feats, C).fit(tr).predict(ev)) for C in models.C_GRID}
        res[f'logit_{name}'] = {'C_scores': scores, 'C': min(scores, key=scores.get)}
        log('logit', name, res[f'logit_{name}']['C'], round(min(scores.values()), 5))
    res['elo_cal_loss'] = metrics.logloss(y, EloCal().fit(tr).predict(ev))
    frozen_old = json.loads((DOCS / 'NBA_XGB_FROZEN.json').read_text())
    res['xgb_base'] = {'params': frozen_old['xgb']['params'], 'rounds': frozen_old['xgb']['rounds'], 'source': 'carried from NBA_XGB_FROZEN.json'}
    res['xgb_base']['dev_loss'] = metrics.logloss(y, XGBNA(BASE, res['xgb_base']['params'], res['xgb_base']['rounds']).fit(tr).predict(ev))
    table = []
    for cfg in models.sample_configs(20, seed=models.SEED + 1):
        curve = {r: metrics.logloss(y, p) for r, p in staged_xgb(tr, ev, BASE + AVAIL, cfg).items()}
        rb = min(curve, key=curve.get)
        table.append({'config': cfg, 'rounds': int(rb), 'loss': curve[rb]})
        log('xgb avail cfg depth', cfg['max_depth'], 'lr', cfg['learning_rate'], 'rounds', rb, round(curve[rb], 5))
    best_all = min(table, key=lambda r: r['loss'])
    shallow = [r for r in table if r['config']['max_depth'] <= 3]
    best_sh = min(shallow, key=lambda r: r['loss'])
    choice = best_all if (best_all['config']['max_depth'] <= 3 or best_all['loss'] < best_sh['loss'] - 0.0005) else best_sh
    res['xgb_avail'] = {'params': choice['config'], 'rounds': choice['rounds'], 'dev_loss': choice['loss'],
                        'note': 'single dev fold: deeper config adopted only if >0.0005 better than best depth<=3'}
    res['xgb_avail_table'] = table
    return res


def make_model(kind, frozen):
    if kind == 'elo_cal':
        return EloCal()
    if kind == 'logit_base':
        return LogitNA(BASE, frozen['logit_base_C'])
    if kind == 'logit_avail':
        return LogitNA(BASE + AVAIL, frozen['logit_avail_C'])
    if kind == 'xgb_base':
        return XGBNA(BASE, frozen['xgb_base']['params'], frozen['xgb_base']['rounds'])
    if kind == 'xgb_avail':
        return XGBNA(BASE + AVAIL, frozen['xgb_avail']['params'], frozen['xgb_avail']['rounds'])
    raise ValueError(kind)


KINDS = ('elo_cal', 'logit_base', 'logit_avail', 'xgb_base', 'xgb_avail')


def oos(T, frozen, folds, kinds=KINDS):
    rows = []
    for f in folds:
        tr, ev = train_rows(T, f), eval_rows(T, f)
        d = ev[['game_id', 'season', 'game_date', 'home_win', 'tipoff_utc']].copy()
        for k in kinds:
            d[k] = make_model(k, frozen).fit(tr).predict(ev)
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def select_calibration(T, frozen, log=print):
    P = oos(T, frozen, (*CAL_FOLDS, DEV_FOLD))
    fit, test = P[P.season.isin(CAL_FOLDS)], P[P.season == DEV_FOLD]
    chosen = {}
    for k in KINDS:
        s = {}
        for method in ('none', 'platt'):
            cal = models.Calibrator(method).fit(fit[k].values, fit.home_win.values)
            s[method] = metrics.logloss(test.home_win.values, cal.predict(test[k].values))
        chosen[k] = {'scores': s, 'method': min(s, key=s.get)}
        log('calibration', k, chosen[k])
    return chosen


def file_hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def freeze(log=print):
    T = load_table()
    res = develop(T, log)
    frozen = {'frozen_at_utc': pd.Timestamp.now(tz='UTC').isoformat(),
              'note': 'Selected on development fold 2024 only; calibrators evaluated on 2024 with fits on 2022-2023. No 2025/2026 outcome used here.',
              'base_features': BASE, 'avail_features': AVAIL,
              'logit_base_C': res['logit_base']['C'], 'logit_avail_C': res['logit_avail']['C'],
              'xgb_base': res['xgb_base'], 'xgb_avail': res['xgb_avail'],
              'folds': {'train_start': FIRST, 'dev': DEV_FOLD, 'cal': list(CAL_FOLDS), 'test': list(TEST_FOLDS)},
              'rapm_tuning_sha256': file_hash(DOCS / 'NBA_AVAIL_RAPM_TUNING.json'),
              'avail_features_sha256': file_hash(OUT / 'avail_features.parquet'),
              'rapm_ratings_sha256': file_hash(OUT / 'rapm_ratings.parquet'),
              'stints_sha256': file_hash(OUT / 'stints.parquet'),
              'base_features_sha256': file_hash(OUT / 'features_lag1.parquet')}
    frozen['calibration'] = select_calibration(T, frozen, log)
    (OUT / 'AVAIL_DEV_RESULTS.json').write_text(json.dumps(res, indent=2, default=float), encoding='utf-8')
    (DOCS / 'NBA_AVAIL_FROZEN.json').write_text(json.dumps(frozen, indent=2, default=float), encoding='utf-8')
    log(json.dumps({k: v for k, v in frozen.items() if k in ('logit_base_C', 'logit_avail_C', 'xgb_avail', 'calibration')}, indent=1, default=float))


def run_test(log=print):
    frozen = json.loads((DOCS / 'NBA_AVAIL_FROZEN.json').read_text())
    for k in ('rapm_ratings_sha256', 'avail_features_sha256', 'stints_sha256', 'base_features_sha256'):
        name = {'rapm_ratings_sha256': 'rapm_ratings.parquet', 'avail_features_sha256': 'avail_features.parquet',
                'stints_sha256': 'stints.parquet', 'base_features_sha256': 'features_lag1.parquet'}[k]
        if file_hash(OUT / name) != frozen[k]:
            raise RuntimeError(f'{name} changed after the freeze')
    T = load_table()
    out = []
    for f in TEST_FOLDS:
        fit_folds = (*CAL_FOLDS, *[x for x in TEST_FOLDS if x < f], DEV_FOLD)
        fit_folds = tuple(sorted(set(range(CAL_FOLDS[0], f))))
        calP = oos(T, frozen, fit_folds)
        tr, ev = train_rows(T, f), eval_rows(T, f)
        for k in KINDS:
            raw = make_model(k, frozen).fit(tr).predict(ev)
            cal = models.Calibrator(frozen['calibration'][k]['method']).fit(calP[k].values, calP.home_win.values)
            p = cal.predict(raw)
            out.append(pd.DataFrame({'game_id': ev.game_id.values, 'season': f, 'game_date': ev.game_date.values,
                                     'prediction_cutoff_utc': ev.prediction_cutoff_utc.astype(str).values, 'model': k,
                                     'p_home_raw': raw, 'p_home': p, 'model_version': hashlib.sha256(
                                         json.dumps(frozen, sort_keys=True, default=str).encode()).hexdigest()[:16],
                                     'train_seasons': f'{FIRST}-{f - 1}'}))
        log('test fold', f, len(ev))
    pred = pd.concat(out, ignore_index=True)
    path = OUT / 'avail_batch_predictions_2025_2026.csv'
    if path.exists():
        raise FileExistsError('test predictions already written; frozen files are immutable')
    pred.to_csv(path, index=False)
    path.chmod(stat.S_IREAD)
    log('written', path, len(pred), file_hash(path))


if __name__ == '__main__':
    import sys
    {'freeze': freeze, 'test': run_test}[sys.argv[1]]()
