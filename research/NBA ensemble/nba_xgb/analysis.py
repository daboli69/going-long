"""Post-freeze analyses: ablations, sensitivity, SHAP, strata. Reported only; nothing here selects the model."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from . import data, engine, metrics, models
from .develop import OUT, DOCS, engine_params, DEV_FOLDS
from .pipeline import load_frozen

TEST = (2025, 2026)
ALL_FOLDS = (2021, 2022, 2023, 2024, 2025, 2026)


def oos(F, feats, frozen, folds, window=None, exclude=(), cfg=None, rounds=None, C=None):
    rows = []
    for f in folds:
        tr, ev = models.training_frame(F, f, window, exclude), models.eval_frame(F, f)
        d = ev[['game_id', 'season', 'game_date', 'home_win', 'gp_min']].copy()
        d['elo_cal'] = models.Logit(models.ELO_FEATS).fit(tr).predict(ev)
        d['logit'] = models.Logit(feats, C or frozen['logit_C']).fit(tr).predict(ev)
        d['xgb'] = models.XGB(feats, cfg or frozen['xgb']['params'], rounds or frozen['xgb']['rounds']).fit(tr).predict(ev)
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def lossrow(P, folds=TEST):
    d = P[P.season.isin(folds)]
    return {m: metrics.logloss(d.home_win.values, d[m].values) for m in ('elo_cal', 'logit', 'xgb')} | {
        'brier_xgb': metrics.brier(d.home_win.values, d.xgb.values), 'brier_logit': metrics.brier(d.home_win.values, d.logit.values)}


def paired(P, a, b, folds=TEST):
    d = P[P.season.isin(folds)].copy()
    d['diff'] = metrics.logloss_vec(d.home_win.values, d[a].values) - metrics.logloss_vec(d.home_win.values, d[b].values)
    return metrics.paired_bootstrap(d, 'diff', draws=2000)


def ablations(F, frozen):
    feats = frozen['features']
    base = oos(F, feats, frozen, ALL_FOLDS)
    out = {'frozen_features': feats, 'base': lossrow(base)}
    variants = {}
    for g in ('elo', 'recent', 'schedule'):
        variants[f'drop_{g}'] = [c for c in feats if c not in models.GROUPS[g]]
    variants['add_adjusted_split'] = feats + models.GROUPS['adjusted']
    variants['swap_adjusted_net_instead'] = feats + ['adj_net_diff']
    variants['add_recent_off_def_split'] = feats + ['recent_off_diff', 'recent_def_diff']
    variants['add_four_factors'] = feats + ['ff_efg_diff', 'ff_tov_diff', 'ff_orb_diff', 'ff_ftr_diff']
    variants['add_games_played_min'] = feats + ['gp_min']
    variants['only_elo'] = ['elo_diff', 'home_court']
    variants['only_adjusted'] = models.GROUPS['adjusted'] + ['home_court']
    variants['only_recent'] = ['recent_net_diff', 'home_court']
    variants['only_schedule'] = models.GROUPS['schedule'] + ['home_court']
    variants['elo_plus_recent'] = ['elo_diff', 'recent_net_diff', 'home_court']
    out['variants'] = {}
    for name, fs in variants.items():
        P = oos(F, fs, frozen, ALL_FOLDS)
        row = {'features': fs, 'test': lossrow(P)}
        for m in ('xgb', 'logit'):
            # paired difference of this variant against the frozen feature set, same games
            d = P[P.season.isin(TEST)][['season', 'game_date', 'home_win']].copy()
            b = base[base.season.isin(TEST)]
            d['diff'] = metrics.logloss_vec(d.home_win.values, P[P.season.isin(TEST)][m].values) - \
                metrics.logloss_vec(d.home_win.values, b[m].values)
            row[f'{m}_minus_frozen'] = metrics.paired_bootstrap(d, 'diff', draws=2000)
        row['by_season_xgb_minus_logit'] = {int(s): float(metrics.logloss(g.home_win.values, g.xgb.values) -
                                                           metrics.logloss(g.home_win.values, g.logit.values))
                                            for s, g in P[P.season.isin(ALL_FOLDS)].groupby('season')}
        out['variants'][name] = row
        print('ablation', name, row['test'], flush=True)
    return out, base


def stability(base):
    rows = {}
    for s, g in base.groupby('season'):
        rows[int(s)] = {m: metrics.logloss(g.home_win.values, g[m].values) for m in ('elo_cal', 'logit', 'xgb')} | {'n': len(g)}
    return rows


def sensitivity(F, frozen):
    out = {}
    feats = frozen['features']
    params = engine_params(1)

    def run(name, Fv, **kw):
        P = oos(Fv, feats if 'feats' not in kw else kw.pop('feats'), frozen, ALL_FOLDS[-3:] + (), **kw)
        d = P[P.season.isin(TEST)]
        out[name] = lossrow(P) | {
            'xgb_minus_logit': paired(P, 'xgb', 'logit'), 'xgb_minus_elo_cal': paired(P, 'xgb', 'elo_cal'),
            'by_season': {int(s): {m: metrics.logloss(g.home_win.values, g[m].values) for m in ('elo_cal', 'logit', 'xgb')}
                          for s, g in P.groupby('season')}}
        print('sens', name, {k: round(v, 4) for k, v in out[name].items() if isinstance(v, float)}, flush=True)

    # training window length and COVID seasons
    for w in (3, 5):
        run(f'train_window_{w}_seasons', F, window=w)
    run('train_window_all', F)
    run('train_exclude_2020_2021', F, exclude=(2020, 2021))

    def rebuild(name, **changes):
        p = json.loads(json.dumps(params))
        for k, v in changes.items():
            if isinstance(v, dict):
                p[k].update(v)
            else:
                p[k] = v
        games, boxes = data.load()
        Fv = engine.build_features(games, boxes, p)
        run(name, Fv)

    for h in (10, 20, 80, 160):
        rebuild(f'recent_half_life_{h}', recent={'half_life': h})
    for n0 in (5, 40):
        rebuild(f'recent_n0_{n0}', recent={'n0': n0})
    rebuild('recent_rho_0.0_no_prior_carry', recent={'rho': 0.0})
    plain = json.loads((DOCS / 'NBA_XGB_ENGINE_PARAMS.json').read_text())['elo']['plain']
    rebuild('elo_plain_no_mov', elo={'k': plain['k'], 'hca': plain['hca'], 'carry': plain['carry'], 'mov': False})
    rebuild('elo_k10', elo={'k': 10.0})
    rebuild('elo_k30', elo={'k': 30.0})
    rebuild('elo_carry_0.5', elo={'carry': 0.5})
    rebuild('elo_carry_0.9', elo={'carry': 0.9})
    rebuild('lag_2_days', lag_days=2)
    return out


def small_sample_strata(F, frozen):
    P = oos(F, frozen['features'], frozen, ALL_FOLDS)
    P = P.copy()
    P['stratum'] = pd.cut(P.gp_min, [-1, 9, 29, 200], labels=['<10 games', '10-29 games', '>=30 games'])
    out = {}
    for name, g in P[P.season.isin(TEST)].groupby('stratum', observed=True):
        out[str(name)] = {'n': len(g)} | {m: metrics.logloss(g.home_win.values, g[m].values) for m in ('elo_cal', 'logit', 'xgb')}
    return out


def deeper_xgb(F, frozen):
    """Does any deeper configuration reproducibly beat the frozen stump model? Report-only check on the test seasons."""
    table = json.loads((OUT / 'DEV_RESULTS.json').read_text())['xgb_table']
    out = {}
    for depth in (2, 3, 4, 6):
        best = min((r for r in table if r['config']['max_depth'] == depth), key=lambda r: r['best_loss'], default=None)
        if best is None:
            continue
        P = oos(F, frozen['features'], frozen, ALL_FOLDS, cfg=best['config'], rounds=best['best_rounds'])
        out[f'depth_{depth}'] = {'config': best['config'], 'rounds': best['best_rounds'], 'dev_loss': best['best_loss'],
                                 'test': lossrow(P), 'xgb_minus_frozen_stump': None,
                                 'xgb_minus_logit': paired(P, 'xgb', 'logit')}
    return out


def shap_report(F, frozen):
    import xgboost as xgb
    feats = frozen['features']
    out = {}
    for T in TEST:
        tr, ev = models.training_frame(F, T), models.eval_frame(F, T)
        m = models.XGB(feats, frozen['xgb']['params'], frozen['xgb']['rounds']).fit(tr)
        contrib = m.m.get_booster().predict(xgb.DMatrix(ev[feats].values, feature_names=None), pred_contribs=True)
        out[int(T)] = {}
        for j, f in enumerate(feats):
            x, s = ev[f].values, contrib[:, j]
            lin = np.corrcoef(x, s)[0, 1] if np.std(s) > 0 and np.std(x) > 0 else float('nan')
            out[int(T)][f] = {'mean_abs_shap_logodds': float(np.abs(s).mean()), 'corr_with_feature': float(lin),
                              'r2_linear_in_feature': float(lin ** 2) if lin == lin else None}
        # deeper variant: interaction mass
    table = json.loads((OUT / 'DEV_RESULTS.json').read_text())['xgb_table']
    best3 = min((r for r in table if r['config']['max_depth'] == 3), key=lambda r: r['best_loss'])
    T = 2026
    tr, ev = models.training_frame(F, T), models.eval_frame(F, T)
    m = models.XGB(feats, best3['config'], best3['best_rounds']).fit(tr)
    inter = m.m.get_booster().predict(xgb.DMatrix(ev[feats].values), pred_interactions=True)
    off = np.abs(inter).sum(0)
    diag = np.abs(np.stack([inter[:, j, j] for j in range(len(feats))], 1)).sum()
    out['depth3_variant_interaction_share'] = float((off.sum() - np.trace(off)) / off.sum())
    return out


def main():
    frozen = load_frozen()
    F = pd.read_parquet(OUT / 'features_lag1.parquet')
    res = {}
    res['ablation'], base = ablations(F, frozen)
    res['stability_by_season'] = stability(base)
    res['strata'] = small_sample_strata(F, frozen)
    res['deeper_xgb'] = deeper_xgb(F, frozen)
    res['shap'] = shap_report(F, frozen)
    res['sensitivity'] = sensitivity(F, frozen)
    (OUT / 'ANALYSIS.json').write_text(json.dumps(res, indent=2, default=float), encoding='utf-8')
    print('saved ANALYSIS.json')


if __name__ == '__main__':
    main()
