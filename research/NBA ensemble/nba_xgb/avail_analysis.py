"""Post-freeze ablations, strata and diagnostics for the availability study. Reported only; nothing here selects a model."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
from . import avail_study as S, metrics, models

TEST = S.TEST_FOLDS


def run_variant(T, frozen, feats, kind):
    rows = []
    for f in TEST:
        tr, ev = S.train_rows(T, f), S.eval_rows(T, f)
        m = S.LogitNA(feats, frozen['logit_avail_C']) if kind == 'logit' else S.XGBNA(feats, frozen['xgb_avail']['params'], frozen['xgb_avail']['rounds'])
        d = ev[['game_id', 'season', 'game_date', 'home_win']].copy()
        d['p'] = m.fit(tr).predict(ev)
        d['avail_effect_diff'] = ev.avail_effect_diff.values
        rows.append(d)
    return pd.concat(rows, ignore_index=True)


def main(log=print):
    frozen = json.loads((S.DOCS / 'NBA_AVAIL_FROZEN.json').read_text())
    T = S.load_table()
    full = S.BASE + S.AVAIL
    variants = {
        'full': full,
        'drop_availability_shortfall': [c for c in full if c not in ('avail_effect_diff', 'missing_min_diff')],
        'drop_player_quality': [c for c in full if c != 'full_value_diff'],
        'drop_elo': [c for c in full if c != 'elo_diff'],
        'drop_recency': [c for c in full if c != 'recent_net_diff'],
        'drop_rest': [c for c in full if c not in ('rest_diff', 'b2b_home', 'b2b_away')],
        'drop_all_player_features': S.BASE,
        'add_opponent_adjusted_efficiency': full + ['adj_off_diff', 'adj_def_diff'],
        'oracle_actual_minutes_diagnostic': S.BASE + ['oracle_value_diff'],
        'player_features_only': ['full_value_diff', 'avail_effect_diff', 'missing_min_diff', 'home_court'],
    }
    out = {}
    for kind in ('logit', 'xgb'):
        ref = None
        for name, feats in variants.items():
            P = run_variant(T, frozen, feats, kind)
            if name == 'full':
                ref = P
            d = P[['season', 'game_date']].copy()
            d['diff'] = metrics.logloss_vec(P.home_win.values, P.p.values) - metrics.logloss_vec(ref.home_win.values, ref.p.values)
            row = {'log_loss': metrics.logloss(P.home_win.values, P.p.values), 'brier': metrics.brier(P.home_win.values, P.p.values),
                   'by_season': {int(s): metrics.logloss(g.home_win.values, g.p.values) for s, g in P.groupby('season')}}
            if name != 'full':
                row['minus_full'] = metrics.paired_bootstrap(d, 'diff', draws=2000)
                row['minus_full_by_season'] = {int(s): float(g['diff'].mean()) for s, g in d.groupby('season')}
            out[f'{kind}:{name}'] = row
            log(kind, name, round(row['log_loss'], 4), row.get('minus_full', {}).get('mean'))
    # where does the availability information act? strata by size of the availability shortfall
    L = run_variant(T, frozen, full, 'logit')
    B = run_variant(T, frozen, S.BASE, 'logit')
    L['loss_full'] = metrics.logloss_vec(L.home_win.values, L.p.values)
    L['loss_base'] = metrics.logloss_vec(B.home_win.values, B.p.values)
    L['abs_effect'] = L.avail_effect_diff.abs()
    L['stratum'] = pd.qcut(L.abs_effect, 3, labels=['smallest third', 'middle third', 'largest third'])
    out['strata_by_abs_availability_shortfall'] = {
        str(k): {'n': len(g), 'base_loss': float(g.loss_base.mean()), 'avail_loss': float(g.loss_full.mean()),
                 'gain': float((g.loss_base - g.loss_full).mean()), 'abs_effect_mean': float(g.abs_effect.mean())}
        for k, g in L.groupby('stratum', observed=True)}
    # play-model quality on the test seasons, by status
    cands = pd.read_parquet(S.OUT / 'avail_candidates.parquet')
    from . import availability as A
    rows = []
    for t in TEST:
        tr, te = cands[(cands.season >= 2022) & (cands.season < t)], cands[cands.season == t]
        te = te.assign(p=A.predict_play(A.fit_play_model(tr), te))
        rows.append(te)
    C = pd.concat(rows)
    out['play_model_by_status'] = {
        s: {'n': int(len(g)), 'observed_play_rate': float(g.played.mean()), 'predicted_mean': float(g.p.mean()),
            'log_loss': metrics.logloss(g.played.values, g.p.values)} for s, g in C.groupby('status')}
    out['play_model_overall'] = {'log_loss': metrics.logloss(C.played.values, C.p.values),
                                 'status_rate_baseline': None}
    (S.OUT / 'AVAIL_ANALYSIS.json').write_text(json.dumps(out, indent=2, default=float), encoding='utf-8')
    log('saved AVAIL_ANALYSIS.json')


if __name__ == '__main__':
    main()
