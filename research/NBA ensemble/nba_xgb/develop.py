"""Development stage: all selection uses folds 2020-2023 (and 2024 for calibration only)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from . import data, engine, metrics, models

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
OUT = ROOT / 'research_nba_xgb'
DEV_FOLDS = (2020, 2021, 2022, 2023)
CAL_FOLD = 2024
TEST_FOLDS = (2025, 2026)


def engine_params(lag_days=1):
    p = json.loads((DOCS / 'NBA_XGB_ENGINE_PARAMS.json').read_text(encoding='utf-8'))
    e = p['elo']['mov']
    return dict(lag_days=lag_days, elo=dict(k=e['k'], hca=e['hca'], carry=e['carry'], mov=True),
                adj=dict(lam=p['adj_best']['lam'], kappa=p['adj_best']['kappa']),
                recent=dict(half_life=p['recent_best']['half_life'], n0=p['recent_best']['n0'], rho=p['recent_best']['rho']))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_feature_file(lag_days=1, name=None, params=None):
    games, boxes = data.load()
    F = engine.build_features(games, boxes, params or engine_params(lag_days))
    OUT.mkdir(exist_ok=True)
    path = OUT / (name or f'features_lag{lag_days}.parquet')
    F.to_parquet(path, index=False)
    return F, path


def pooled(y_list, p_list):
    return metrics.logloss(np.concatenate(y_list), np.concatenate(p_list))


def run_dev(F, log=print):
    ev = {f: models.eval_frame(F, f) for f in DEV_FOLDS}
    tr = {f: models.training_frame(F, f) for f in DEV_FOLDS}
    ys = [ev[f].home_win.values for f in DEV_FOLDS]
    res = {'folds': list(DEV_FOLDS), 'n_eval': {int(f): len(ev[f]) for f in DEV_FOLDS}}

    # Baseline 1: calibrated Elo
    p_elo = [models.Logit(models.ELO_FEATS).fit(tr[f]).predict(ev[f]) for f in DEV_FOLDS]
    res['elo_cal'] = {'pooled': pooled(ys, p_elo), 'by_fold': [metrics.logloss(y, p) for y, p in zip(ys, p_elo)]}
    # constant home rate reference
    p_const = [np.full(len(ev[f]), tr[f].home_win.mean()) for f in DEV_FOLDS]
    res['constant'] = {'pooled': pooled(ys, p_const)}
    log('elo', res['elo_cal']['pooled'], 'const', res['constant']['pooled'])

    # Baseline 2: logistic, choose C
    lg = {}
    for C in models.C_GRID:
        ps = [models.Logit(models.CORE, C).fit(tr[f]).predict(ev[f]) for f in DEV_FOLDS]
        lg[C] = {'pooled': pooled(ys, ps), 'by_fold': [metrics.logloss(y, p) for y, p in zip(ys, ps)]}
    bestC = min(lg, key=lambda c: lg[c]['pooled'])
    res['logit_grid'] = {str(c): v for c, v in lg.items()}
    res['logit_best_C'] = bestC
    log('logit', bestC, lg[bestC]['pooled'])

    # XGBoost search with staged rounds (rounds act as the early-stopping choice, scored on dev folds only)
    configs = models.sample_configs(30)
    table = []
    for ci, cfg in enumerate(configs):
        per_fold = {r: [] for r in models.R_GRID}
        for f in DEV_FOLDS:
            staged = models.xgb_staged(tr[f], ev[f], models.CORE, cfg)
            for r, p in staged.items():
                per_fold[r].append(metrics.logloss_vec(ev[f].home_win.values, p))
        row = {'config': cfg, 'curve': {}, 'fold_curve': {}}
        for r, lst in per_fold.items():
            row['curve'][r] = float(np.mean(np.concatenate(lst)))
            row['fold_curve'][r] = [float(x.mean()) for x in lst]
        r_best = min(row['curve'], key=row['curve'].get)
        row.update(best_rounds=int(r_best), best_loss=row['curve'][r_best], best_by_fold=row['fold_curve'][r_best])
        table.append(row)
        log(f'xgb cfg {ci:02d} depth={cfg["max_depth"]} lr={cfg["learning_rate"]} best_rounds={r_best} loss={row["best_loss"]:.5f}')
    best_all = min(table, key=lambda r: r['best_loss'])
    shallow = [r for r in table if r['config']['max_depth'] <= 3]
    best_sh = min(shallow, key=lambda r: r['best_loss'])
    wins = sum(a < b - 0.0005 for a, b in zip(best_all['best_by_fold'], best_sh['best_by_fold']))
    chosen = best_all if (best_all['config']['max_depth'] <= 3 or wins >= 3) else best_sh
    res['xgb_table'] = [{'config': r['config'], 'best_rounds': r['best_rounds'], 'best_loss': r['best_loss'],
                         'best_by_fold': r['best_by_fold']} for r in table]
    res['xgb_choice'] = {'best_overall_depth': best_all['config']['max_depth'], 'best_overall_loss': best_all['best_loss'],
                         'best_shallow_loss': best_sh['best_loss'], 'deep_wins_folds': int(wins),
                         'chosen': chosen['config'], 'rounds': chosen['best_rounds'], 'loss': chosen['best_loss'],
                         'rounds_at_grid_edge': chosen['best_rounds'] >= models.R_MAX}
    log('xgb chosen', res['xgb_choice'])
    return res, tr, ev


def prune(F, res, log=print):
    """Leave-one-group-out on dev folds with the selected XGB config; drop groups whose removal helps."""
    cfg, rounds = res['xgb_choice']['chosen'], res['xgb_choice']['rounds']
    C = res['logit_best_C']
    ev = {f: models.eval_frame(F, f) for f in DEV_FOLDS}
    tr = {f: models.training_frame(F, f) for f in DEV_FOLDS}
    y = np.concatenate([ev[f].home_win.values for f in DEV_FOLDS])

    def score(feats):
        px = np.concatenate([models.XGB(feats, cfg, rounds).fit(tr[f]).predict(ev[f]) for f in DEV_FOLDS])
        pl = np.concatenate([models.Logit(feats, C).fit(tr[f]).predict(ev[f]) for f in DEV_FOLDS])
        return metrics.logloss(y, px), metrics.logloss(y, pl)

    full = score(models.CORE)
    out = {'full': {'xgb': full[0], 'logit': full[1]}, 'drop': {}}
    keep = list(models.CORE)
    for g, cols in models.GROUPS.items():
        if g == 'context':
            continue
        feats = [c for c in models.CORE if c not in cols]
        s = score(feats)
        out['drop'][g] = {'xgb': s[0], 'logit': s[1], 'xgb_delta_if_removed': s[0] - full[0]}
        log('LOGO', g, out['drop'][g])
        if full[0] - s[0] >= 0.0002:
            keep = [c for c in keep if c not in cols]
    out['final_features'] = keep
    return out


def oos_predictions(F, feats, cfg, rounds, C, folds, window=None, exclude=()):
    """Out-of-sample predictions of the three model families for each fold."""
    rows = []
    for f in folds:
        tr, ev = models.training_frame(F, f, window, exclude), models.eval_frame(F, f)
        base = ev[['game_id', 'season', 'game_date', 'home_win']].copy()
        base['elo_cal'] = models.Logit(models.ELO_FEATS).fit(tr).predict(ev)
        base['logit'] = models.Logit(feats, C).fit(tr).predict(ev)
        base['xgb'] = models.XGB(feats, cfg, rounds).fit(tr).predict(ev)
        rows.append(base)
    return pd.concat(rows, ignore_index=True)


def select_calibration(F, feats, cfg, rounds, C, log=print):
    folds = (*DEV_FOLDS, CAL_FOLD)
    P = oos_predictions(F, feats, cfg, rounds, C, folds)
    fit, test = P[P.season.isin(DEV_FOLDS)], P[P.season == CAL_FOLD]
    out = {}
    for m in ('elo_cal', 'logit', 'xgb'):
        scores = {}
        for method in ('none', 'platt', 'isotonic'):
            cal = models.Calibrator(method).fit(fit[m].values, fit.home_win.values)
            scores[method] = metrics.logloss(test.home_win.values, cal.predict(test[m].values))
        out[m] = {'scores_fold_2024': scores, 'chosen': min(scores, key=scores.get)}
        log('calibration', m, out[m])
    return out, P


def main(log=print):
    F, path = build_feature_file(1)
    log('features', path, F.shape)
    res, _, _ = run_dev(F, log)
    pr = prune(F, res, log)
    feats = pr['final_features']
    cfg, rounds, C = res['xgb_choice']['chosen'], res['xgb_choice']['rounds'], res['logit_best_C']
    cal, P = select_calibration(F, feats, cfg, rounds, C, log)
    res.update(prune=pr, calibration=cal)
    (OUT / 'DEV_RESULTS.json').write_text(json.dumps(res, indent=2, default=float), encoding='utf-8')
    P.to_parquet(OUT / 'dev_oos_predictions.parquet', index=False)
    frozen = {
        'frozen_at_utc': pd.Timestamp.now(tz='UTC').isoformat(),
        'note': 'Written from development folds 2020-2023 (+2024 for calibration only). No 2025/2026 outcome was used.',
        'engine_params': engine_params(1), 'engine_params_file_sha256': file_hash(DOCS / 'NBA_XGB_ENGINE_PARAMS.json'),
        'canonical_manifest_sha256': file_hash(data.CANON / 'MANIFEST.json'),
        'features': feats, 'xgb': {'params': cfg, 'rounds': rounds, 'seed': models.SEED}, 'logit_C': C,
        'calibration': {k: v['chosen'] for k, v in cal.items()},
        'dev_folds': list(DEV_FOLDS), 'calibration_selection_fold': CAL_FOLD, 'test_folds': list(TEST_FOLDS),
        'refit_schedule': 'annual, before each season, on all labelled seasons >= 2016 and < target season',
        'feature_file_sha256': file_hash(path)}
    (DOCS / 'NBA_XGB_FROZEN.json').write_text(json.dumps(frozen, indent=2, default=float), encoding='utf-8')
    log('FROZEN', json.dumps(frozen, indent=2, default=float))


if __name__ == '__main__':
    main()
