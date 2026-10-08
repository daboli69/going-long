"""First-wave pre-registered experiments. Specs are plain dicts: they are hashed into the ledger BEFORE a run and the run refuses a changed spec.

Common design
* chronological, rolling-origin: a model is trained only on seasons strictly earlier than the season it is tested on
* features for season N come only from season N-1 Fantasy Points snapshots (completed, retrospective, regular season) and, for weekly work,
  from earlier weeks of season N; the Fantasy Points file of season N is used only as an outcome (E1, E2, E5)
* fixed ridge penalty (10), no tuning on test data; paired cluster-bootstrap CIs; decision rules fixed in the spec
"""
import numpy as np
import pandas as pd

from fp_ingest.identity import canonical_team

from . import data
from .stats import Ridge, mae, paired_bootstrap, rmse, spearman, verdict, BOOTSTRAPS

ROLE_FEATURES = ['Receiving.RTE', 'Receiving.RTE %', 'Receiving.TPRR', 'Receiving.YPRR', 'Receiving.TGT %', 'Receiving.AY Share', 'Receiving.aDOT',
                 'Advanced.1READ %', 'Advanced.DESIGN %', 'Advanced.CTGT %', 'Advanced.WIDE RTE %', 'Advanced.SLOT RTE %', 'Advanced.INLINE RTE %',
                 'FPTS.XFP/G', 'Advanced.EZTGT']
RULE = {'min_relative_improvement': 0.01, 'min_years_better': 2, 'reject_below_relative_improvement': 0.0025}
COMMON = {'metric': 'mean absolute error (primary), RMSE and Spearman (secondary)', 'ridge_alpha': 10, 'bootstrap': 'cluster by player/team, 2000 draws, seed 20261008',
          'decision_rule': {'PROMISING': 'relative MAE improvement >= 1% over the baseline AND the Bonferroni-adjusted CI of the paired difference excludes 0 AND better in >= 2 of the 3 test seasons',
                            'REJECTED': 'relative improvement < 0.25% OR the CI lies entirely on the wrong side',
                            'INCONCLUSIVE': 'anything else'}, **{'rule_numbers': RULE}}

SPECS = {
    'E1': {**COMMON, 'id': 'E1', 'title': 'Prior-season role profile -> next-season receiving volume and yards (WR/TE)',
           'hypothesis': 'Route participation, targets per route, first-read/designed-target share, alignment mix and XFP of season N-1 improve prediction of season N '
                         'per-game targets, receptions and receiving yards beyond the player\'s own prior per-game production.',
           'football_rationale': 'Targets follow routes run, how often a player is the first read and where he lines up; production-only baselines mix role with luck and '
                                 'with a one-off team context. Role is closer to the cause of volume.',
           'unit': 'WR/TE player-season pair (N-1 -> N) with >= 8 games in both seasons', 'features_role': ROLE_FEATURES,
           'baselines': {'B0': 'prior-season per-game value of the same outcome', 'B1': 'ridge on prior per-game targets, receptions, yards, games played, TE flag'},
           'challenger': 'C1 = B1 + role features', 'primary_comparison': 'C1 vs B1', 'outcomes': ['targets/g', 'receptions/g', 'receiving yards/g'],
           'splits': {'pairs': ['2021->2022', '2022->2023', '2023->2024', '2024->2025'], 'test': ['2022->2023', '2023->2024', '2024->2025'], 'rolling_origin': True},
           'multiple_testing': 'Bonferroni over 3 outcomes (98.33% CI)', 'sources': ['Fantasy Points receiving_advanced, receiving_basic 2021-2025 (retrospective, regular season)'],
           'leakage': 'features from season N-1 only; season N file used as outcome only', 'markets': ['receptions', 'receiving yards']},
    'E6': {**COMMON, 'id': 'E6', 'exploratory': True,
           'title': 'EXPLORATORY follow-up to E1: three compact role features instead of fifteen',
           'hypothesis': 'E1 failed in the first test seasons and recovered in the last, the pattern of an over-parameterised model trained on ~100 rows. A compact set '
                         '(targets per route run, route participation, first-read share) may add to the production baseline without that overfit.',
           'football_rationale': 'Same as E1; fewer degrees of freedom.', 'unit': 'as E1', 'features_role': ['Receiving.TPRR', 'Receiving.RTE %', 'Advanced.1READ %'],
           'baselines': {'B1': 'as E1'}, 'challenger': 'C6 = B1 + 3 compact role features', 'primary_comparison': 'C6 vs B1', 'outcomes': ['targets/g', 'receptions/g', 'receiving yards/g'],
           'splits': {'test': ['2022->2023', '2023->2024', '2024->2025'], 'rolling_origin': True}, 'multiple_testing': 'Bonferroni over 3 outcomes (98.33% CI)',
           'sources': ['as E1'], 'leakage': 'as E1',
           'markets': ['receptions', 'receiving yards'],
           'limitations': 'POST-HOC: designed after seeing E1 on the same seasons. Exploratory only: a PROMISING result is capped at NEEDS PROSPECTIVE DATA and may not support promotion.'},
    'E2': {**COMMON, 'id': 'E2', 'title': 'Expected fantasy points / expected TDs vs actual: does opportunity predict next season better than results?',
           'hypothesis': 'XFP/G of season N-1 adds to FP/G of N-1 in predicting FP/G of N (regression toward opportunity); XTD/G adds to TD/G in predicting next-season TD/G.',
           'football_rationale': 'Results include touchdown and efficiency variance that does not persist; opportunity volume does.',
           'unit': 'WR/TE/RB player-season pair with >= 8 games in both seasons',
           'baselines': {'B0': 'prior-season FP/G (TD/G)', 'B1': 'ridge on prior FP/G (and TD/G), games, position flags'}, 'challenger': 'C2 = B1 + XFP/G (and XTD/G)',
           'primary_comparison': 'C2 vs B1', 'outcomes': ['FP/G (PPR)', 'TD/G'],
           'splits': {'pairs': ['2021->2022', '2022->2023', '2023->2024', '2024->2025'], 'test': ['2022->2023', '2023->2024', '2024->2025'], 'rolling_origin': True},
           'multiple_testing': 'Bonferroni over 2 outcomes (97.5% CI)', 'sources': ['Fantasy Points efficiency 2021-2025'],
           'leakage': 'features from season N-1 only', 'markets': ['receiving/rushing yards', 'anytime TD', 'fantasy points']},
    'E3': {**COMMON, 'id': 'E3', 'title': 'Weekly application: do prior-season role features add to what GOING already knows in-season (rolling usage)?',
           'hypothesis': 'Prior-season role features (E1 set) improve weekly target/reception/yard predictions beyond prior-season per-game averages AND the player\'s own '
                         'rolling in-season usage, most strongly in weeks 1-4 and fading as in-season evidence accumulates.',
           'football_rationale': 'Early in a season rolling usage is a handful of games; role history is a better estimate of the true role. Later the sample dominates.',
           'unit': 'WR/TE player-week (regular season weeks 1-18) with prior-season >= 8 games and Fantasy Points prior features; only players who recorded stats that week',
           'baselines': {'B1': 'ridge on prior-season per-game targets/receptions/yards (nflverse weekly) + TE flag',
                         'B2': 'B1 + mean of the player\'s earlier weeks this season (prior average if none), number of earlier appearances'},
           'challenger': 'C3 = B2 + role features', 'primary_comparison': 'C3 vs B2 in weeks 1-4', 'descriptive_buckets': ['weeks 5-8', 'weeks 9-13', 'weeks 14-18'],
           'outcomes': ['targets', 'receptions', 'receiving yards'],
           'splits': {'test': [2023, 2024, 2025], 'train': 'all earlier seasons, all weeks', 'rolling_origin': True},
           'multiple_testing': 'Bonferroni over 3 outcomes for the primary weeks 1-4 bucket (98.33% CI); other buckets descriptive only',
           'sources': ['Fantasy Points receiving_advanced 2021-2024 (as prior features)', 'nflverse weekly player stats 2021-2025'],
           'leakage': 'prior-season features only; rolling means use weeks strictly before the target week', 'markets': ['receptions', 'receiving yards'],
           'limitations': 'conditions on the player appearing in the weekly stats; does not model who plays'},
    'E4': {**COMMON, 'id': 'E4', 'title': 'Matchup interaction: receiver man-coverage advantage x opponent man-coverage rate',
           'hypothesis': 'A receiver who produced better per route against man than zone (prior season) outperforms his baseline more when the opponent played more man '
                         'coverage (prior season); the interaction term improves weekly receiving-yard prediction beyond main effects.',
           'football_rationale': 'Coverage shell changes who wins routes; the interaction is the matchup, not either part alone.',
           'unit': 'as E3 for seasons 2023-2025 (the 2021 coverage scale is not comparable, so opponent coverage uses 2022+ prior seasons)',
           'baselines': {'D0': 'E3 challenger C3', 'D1': 'D0 + man-vs-zone advantage + opponent man rate (main effects)'}, 'challenger': 'D2 = D1 + advantage x opponent man rate',
           'primary_comparison': 'D2 vs D1', 'outcomes': ['receiving yards', 'targets'],
           'definitions': {'advantage': '(Man YPRR - Zone YPRR) * min(1, Man RTE/100), zero when Man RTE < 40 or Zone RTE < 100',
                           'opponent_man_rate': 'opponent prior-season Man/Zone MAN % centred and scaled over teams in that season'},
           'splits': {'test': [2024, 2025], 'train': 'earlier seasons from 2023', 'rolling_origin': True},
           'multiple_testing': 'Bonferroni over 2 outcomes (97.5% CI)', 'rule_numbers': {'min_relative_improvement': 0.005, 'min_years_better': 2, 'reject_below_relative_improvement': 0.001},
           'sources': ['Fantasy Points receiving_man_vs_zone, coverage_matrix 2022-2024 (prior seasons)', 'nflverse weekly stats 2022-2025'],
           'leakage': 'prior-season coverage and receiver splits only', 'markets': ['receiving yards', 'receptions']},
    'E5': {**COMMON, 'id': 'E5', 'title': 'Team pass-rate persistence: does game-script-split pass rate beat overall pass rate?',
           'hypothesis': 'Neutral/leading/trailing pass rates of season N-1 predict season N overall pass rate better than the overall pass rate alone.',
           'football_rationale': 'Overall pass rate mixes the offense\'s preference with how often it was ahead or behind.',
           'unit': 'team-season pair', 'baselines': {'B0': 'prior overall pass rate', 'B1': 'ridge on prior overall pass rate'},
           'challenger': 'C5 = B1 + neutral, leading and trailing pass rates', 'primary_comparison': 'C5 vs B1', 'outcomes': ['overall pass rate'],
           'splits': {'test': ['2022->2023', '2023->2024', '2024->2025'], 'rolling_origin': True}, 'multiple_testing': 'single outcome (95% CI)',
           'sources': ['Fantasy Points run_pass_report 2021-2025'], 'leakage': 'season N-1 only', 'markets': ['game totals', 'receptions', 'carries'],
           'limitations': 'about 96 test team-seasons: low power, so INCONCLUSIVE is the expected honest outcome unless the effect is large'},
}


# ------------------------------------------------------------------ shared helpers
def _fit_predict(train, test, cols, target):
    model = Ridge().fit(train[cols], train[target])
    return model.predict(test[cols]), model


def _compare(frames_by_year, models, target, group_col, confidence, rule, base_name, new_name, bucket=None):
    """Rolling-origin comparison. frames_by_year: {test_year: (train_df, test_df)}. models: {name: columns}."""
    per_year, all_base, all_new, all_groups, y_all = {}, [], [], [], []
    better = 0
    for year, (train, test) in frames_by_year.items():
        preds = {name: _fit_predict(train, test, cols, target)[0] for name, cols in models.items()}
        y = test[target].to_numpy()
        row = {name: {'mae': mae(y, p), 'rmse': rmse(y, p), 'spearman': spearman(y, p)} for name, p in preds.items()}
        row['n'] = int(len(test))
        per_year[str(year)] = row
        better += row[new_name]['mae'] < row[base_name]['mae']
        all_base.append(y - preds[base_name])
        all_new.append(y - preds[new_name])
        all_groups.append(test[group_col].to_numpy())
        y_all.append(y)
    base_err, new_err, groups = np.concatenate(all_base), np.concatenate(all_new), np.concatenate(all_groups)
    delta = paired_bootstrap(base_err, new_err, groups, confidence=confidence)
    base_mae = float(np.abs(base_err).mean())
    label, rel = verdict(delta, base_mae, better, len(frames_by_year), rule)
    return {'per_test_year': per_year, 'pooled': {'base_mae': base_mae, 'new_mae': float(np.abs(new_err).mean()), 'n': int(len(base_err)), **delta,
                                                 'relative_improvement': rel, 'years_better': int(better), 'years_total': len(frames_by_year)},
            'verdict': label}


def _worst(verdicts):
    order = ['PROMISING', 'INCONCLUSIVE', 'REJECTED']
    labels = set(verdicts)
    if labels == {'PROMISING'}:
        return 'PROMISING'
    if 'PROMISING' in labels:
        return 'INCONCLUSIVE'
    return 'REJECTED' if labels == {'REJECTED'} else 'INCONCLUSIVE'


def _train_test(pairs, test_years, year_col='season'):
    out = {}
    for year in test_years:
        train = pd.concat([p for y, p in pairs.items() if y < year], ignore_index=True)
        out[year] = (train, pairs[year])
    return out


# ------------------------------------------------------------------ E1
def e1_pairs(root, manifest):
    data_by_year = {}
    for season in range(2022, 2026):
        adv = data.prior_features(root, manifest, season, 'receiving_advanced')
        prev = data.prior_features(root, manifest, season, 'receiving_basic')
        now = data.outcome_frame(root, manifest, season, 'receiving_basic')
        data.assert_no_same_season(season - 1, season)
        left = adv[['player_id', 'pos', 'games'] + ROLE_FEATURES].rename(columns={'games': 'games_prev'})
        left = left[left.pos.isin(['WR', 'TE']) & (left.games_prev >= 8)]
        prev = prev[['player_id', 'Receiving.TGT', 'Receiving.REC', 'Receiving.YDS']].rename(columns={'Receiving.TGT': 'p_tgt', 'Receiving.REC': 'p_rec', 'Receiving.YDS': 'p_yds'})
        out = now[['player_id', 'games', 'Receiving.TGT', 'Receiving.REC', 'Receiving.YDS']].rename(columns={'games': 'games_next', 'Receiving.TGT': 'y_tgt', 'Receiving.REC': 'y_rec', 'Receiving.YDS': 'y_yds'})
        frame = left.merge(prev, on='player_id').merge(out, on='player_id')
        frame = frame[frame.games_next >= 8].dropna(subset=ROLE_FEATURES + ['p_tgt', 'p_rec', 'p_yds', 'y_tgt', 'y_rec', 'y_yds']).copy()
        frame['is_te'] = (frame.pos == 'TE').astype(float)
        for k in ('tgt', 'rec', 'yds'):
            frame['b_' + k] = frame['p_' + k] / frame.games_prev
            frame['t_' + k] = frame['y_' + k] / frame.games_next
        frame['rte_g'] = frame['Receiving.RTE'] / frame.games_prev
        frame['season'] = season
        data_by_year[season] = frame
    return data_by_year


def run_e1(root, manifest, exp_id='E1'):
    spec = SPECS[exp_id]
    pairs = e1_pairs(root, manifest)
    folds = _train_test(pairs, [2023, 2024, 2025])
    base_cols = ['b_tgt', 'b_rec', 'b_yds', 'games_prev', 'is_te']
    role_cols = (ROLE_FEATURES + ['rte_g']) if exp_id == 'E1' else list(spec['features_role'])
    results, verdicts = {}, []
    for outcome, target, own in (('targets/g', 't_tgt', 'b_tgt'), ('receptions/g', 't_rec', 'b_rec'), ('receiving yards/g', 't_yds', 'b_yds')):
        frames = {}
        for year, (train, test) in folds.items():
            train, test = train.copy(), test.copy()
            for frame in (train, test):
                frame['B0'] = frame[own]
            frames[year] = (train, test)
        res = _compare(frames, {'B1': base_cols, 'C1': base_cols + role_cols}, target, 'player_id', 1 - 0.05 / 3, spec['rule_numbers'], 'B1', 'C1')
        res['challenger_columns'] = role_cols
        # B0 reference (no model): prior per-game value
        b0 = {str(y): mae(te[target], te[own]) for y, (tr, te) in frames.items()}
        res['B0_mae_by_year'] = b0
        full = Ridge().fit(pd.concat(list(pairs.values())[:3])[base_cols + role_cols], pd.concat(list(pairs.values())[:3])[target])
        res['standardized_coefficients_trained_2022_2024'] = {c: float(v) for c, v in zip(base_cols + role_cols, full.coef_)}
        results[outcome] = res
        verdicts.append(res['verdict'])
    return {'sample_sizes': {str(y): int(len(f)) for y, f in pairs.items()}, 'outcomes': results}, _worst(verdicts)


# ------------------------------------------------------------------ E2
def e2_pairs(root, manifest, min_games_next=8):
    out = {}
    for season in range(2022, 2026):
        prev = data.prior_features(root, manifest, season, 'efficiency')
        now = data.outcome_frame(root, manifest, season, 'efficiency')
        data.assert_no_same_season(season - 1, season)
        cols = ['FPTS.FP/G', 'FPTS.XFP/G', 'FPTS.XTD/G', 'Total.TD']
        left = prev[['player_id', 'pos', 'games'] + cols].rename(columns={'games': 'games_prev'})
        left = left[left.pos.isin(['WR', 'TE', 'RB']) & (left.games_prev >= 8)]
        right = now[['player_id', 'games', 'FPTS.FP/G', 'Total.TD']].rename(columns={'games': 'games_next', 'FPTS.FP/G': 'y_fpg', 'Total.TD': 'y_td'})
        frame = left.merge(right, on='player_id')
        frame = frame[frame.games_next >= min_games_next].dropna(subset=cols + ['y_fpg', 'y_td']).copy()
        frame['fpg'], frame['xfpg'], frame['xtdg'] = frame['FPTS.FP/G'], frame['FPTS.XFP/G'], frame['FPTS.XTD/G']
        frame['tdg'] = frame['Total.TD'] / frame.games_prev
        frame['t_fpg'], frame['t_tdg'] = frame.y_fpg, frame.y_td / frame.games_next
        frame['is_te'], frame['is_rb'] = (frame.pos == 'TE').astype(float), (frame.pos == 'RB').astype(float)
        frame['season'] = season
        out[season] = frame
    return out


def run_e2(root, manifest):
    spec = SPECS['E2']
    pairs = e2_pairs(root, manifest)
    folds = _train_test(pairs, [2023, 2024, 2025])
    results, verdicts = {}, []
    conf = 1 - 0.05 / 2
    for outcome, target, base_cols, extra in (('FP/G (PPR)', 't_fpg', ['fpg', 'games_prev', 'is_te', 'is_rb'], ['xfpg']),
                                              ('TD/G', 't_tdg', ['tdg', 'fpg', 'games_prev', 'is_te', 'is_rb'], ['xtdg'])):
        res = _compare(folds, {'B1': base_cols, 'C2': base_cols + extra}, target, 'player_id', conf, spec['rule_numbers'], 'B1', 'C2')
        own = 'fpg' if outcome.startswith('FP') else 'tdg'
        res['B0_mae_by_year'] = {str(y): mae(te[target], te[own]) for y, (tr, te) in folds.items()}
        full = Ridge().fit(pd.concat([pairs[y] for y in (2022, 2023, 2024)])[base_cols + extra], pd.concat([pairs[y] for y in (2022, 2023, 2024)])[target])
        res['standardized_coefficients_trained_2022_2024'] = {c: float(v) for c, v in zip(base_cols + extra, full.coef_)}
        results[outcome] = res
        verdicts.append(res['verdict'])
    return {'sample_sizes': {str(y): int(len(f)) for y, f in pairs.items()}, 'outcomes': results}, _worst(verdicts)


# ------------------------------------------------------------------ E3 / E4 weekly frame
def _weekly_frame(root, manifest, season, with_matchup=False):
    prior_w = data.weekly(root, season - 1)
    prior_w = prior_w[prior_w.position.isin(['WR', 'TE'])]
    agg = prior_w.groupby('player_id').agg(p_games=('week', 'count'), p_tgt=('targets', 'mean'), p_rec=('receptions', 'mean'), p_yds=('receiving_yards', 'mean')).reset_index()
    agg = agg[agg.p_games >= 8]
    adv = data.prior_features(root, manifest, season, 'receiving_advanced')
    data.assert_no_same_season(season - 1, season)
    adv = adv[['player_id'] + ROLE_FEATURES].dropna()
    base = agg.merge(adv, on='player_id')
    wk = data.weekly(root, season)
    wk = wk[wk.position.isin(['WR', 'TE']) & (wk.week <= 18)].sort_values(['player_id', 'week'])
    wk = wk.merge(base, on='player_id')
    wk['is_te'] = (wk.position == 'TE').astype(float)
    for name, col in (('tgt', 'targets'), ('rec', 'receptions'), ('yds', 'receiving_yards')):
        prev_sum = wk.groupby('player_id')[col].cumsum() - wk[col]
        k = wk.groupby('player_id').cumcount()
        wk['k'] = k
        wk['r_' + name] = np.where(k > 0, prev_sum / k.replace(0, np.nan), wk['p_' + name])
    wk['k0'] = (wk.k == 0).astype(float)
    wk['season'] = season
    if with_matchup:
        prior_mvz = data.prior_features(root, manifest, season, 'receiving_man_vs_zone')
        cov = data.prior_features(root, manifest, season, 'coverage_matrix')
        mvz = prior_mvz[['player_id', 'Man.RTE', 'Zone.RTE', 'Man.YPRR', 'Zone.YPRR']].copy()
        ok = (mvz['Man.RTE'] >= 40) & (mvz['Zone.RTE'] >= 100)
        mvz['adv'] = np.where(ok, (mvz['Man.YPRR'] - mvz['Zone.YPRR']) * np.minimum(1, mvz['Man.RTE'] / 100), 0.0)
        wk = wk.merge(mvz[['player_id', 'adv']], on='player_id', how='left')
        wk['adv'] = wk['adv'].fillna(0.0)
        cov = cov.copy()
        cov['team'] = [canonical_team(t) for t in cov['team_key']]
        rate = cov.set_index('team')['Man/Zone.MAN %']
        z = (rate - rate.mean()) / rate.std()
        wk['opp_man_z'] = [z.get(canonical_team(t), 0.0) if isinstance(t, str) else 0.0 for t in wk.opponent_team]
        wk['adv_x_man'] = wk.adv * wk.opp_man_z
    return wk


def _weekly_folds(frames, test_years, week_filter=None):
    out = {}
    for year in test_years:
        train = pd.concat([f for y, f in frames.items() if y < year], ignore_index=True)
        test = frames[year]
        if week_filter:
            test = test[week_filter(test.week)]
        out[year] = (train, test.copy())
    return out


def run_e3(root, manifest):
    spec = SPECS['E3']
    frames = {s: _weekly_frame(root, manifest, s) for s in range(2022, 2026)}
    b1 = ['p_tgt', 'p_rec', 'p_yds', 'is_te']
    b2 = b1 + ['r_tgt', 'r_rec', 'r_yds', 'k', 'k0']
    c3 = b2 + ROLE_FEATURES
    buckets = {'weeks 1-4': lambda w: w <= 4, 'weeks 5-8': lambda w: (w >= 5) & (w <= 8), 'weeks 9-13': lambda w: (w >= 9) & (w <= 13), 'weeks 14-18': lambda w: w >= 14}
    out, primary = {}, []
    for bucket, flt in buckets.items():
        out[bucket] = {}
        for outcome, target in (('targets', 'targets'), ('receptions', 'receptions'), ('receiving yards', 'receiving_yards')):
            folds = _weekly_folds(frames, [2023, 2024, 2025], flt)
            conf = 1 - 0.05 / 3 if bucket == 'weeks 1-4' else 0.95
            res = _compare(folds, {'B1': b1, 'B2': b2, 'C3': c3}, target, 'player_id', conf, spec['rule_numbers'], 'B2', 'C3')
            res['B1_vs_B2_pooled_delta'] = None
            out[bucket][outcome] = res
            if bucket == 'weeks 1-4':
                primary.append(res['verdict'])
    return {'sample_sizes': {str(y): int(len(f)) for y, f in frames.items()}, 'buckets': out}, _worst(primary)


def run_e4(root, manifest):
    spec = SPECS['E4']
    frames = {s: _weekly_frame(root, manifest, s, with_matchup=True) for s in (2023, 2024, 2025)}
    d0 = ['p_tgt', 'p_rec', 'p_yds', 'is_te', 'r_tgt', 'r_rec', 'r_yds', 'k', 'k0'] + ROLE_FEATURES
    d1 = d0 + ['adv', 'opp_man_z']
    d2 = d1 + ['adv_x_man']
    out, verdicts = {}, []
    for outcome, target in (('receiving yards', 'receiving_yards'), ('targets', 'targets')):
        folds = _weekly_folds(frames, [2024, 2025])
        res = _compare(folds, {'D0': d0, 'D1': d1, 'D2': d2}, target, 'player_id', 1 - 0.05 / 2, spec['rule_numbers'], 'D1', 'D2')
        train = pd.concat([frames[2023], frames[2024]], ignore_index=True)
        model = Ridge().fit(train[d2], train[target])
        res['interaction_standardized_coef_trained_2023_2024'] = float(model.coef_[d2.index('adv_x_man')])
        out[outcome] = res
        verdicts.append(res['verdict'])
    return {'sample_sizes': {str(y): int(len(f)) for y, f in frames.items()}, 'outcomes': out}, _worst(verdicts)


# ------------------------------------------------------------------ E5
def run_e5(root, manifest):
    spec = SPECS['E5']
    pairs = {}
    for season in range(2022, 2026):
        prev = data.prior_features(root, manifest, season, 'run_pass_report')
        now = data.outcome_frame(root, manifest, season, 'run_pass_report')
        data.assert_no_same_season(season - 1, season)
        cols = {'Overall.PASS %': 'p_overall', 'Neutral.PASS %': 'p_neutral', 'Leading By 7+.PASS %': 'p_leading', 'Trailing By 7+.PASS %': 'p_trailing'}
        left = prev[['team_key'] + list(cols)].rename(columns=cols)
        right = now[['team_key', 'Overall.PASS %']].rename(columns={'Overall.PASS %': 'y'})
        frame = left.merge(right, on='team_key').dropna()
        frame['season'] = season
        pairs[season] = frame
    folds = _train_test(pairs, [2023, 2024, 2025])
    res = _compare(folds, {'B1': ['p_overall'], 'C5': ['p_overall', 'p_neutral', 'p_leading', 'p_trailing']}, 'y', 'team_key', 0.95, spec['rule_numbers'], 'B1', 'C5')
    res['B0_mae_by_year'] = {str(y): mae(te['y'], te['p_overall']) for y, (tr, te) in folds.items()}
    return {'sample_sizes': {str(y): int(len(f)) for y, f in pairs.items()}, 'outcomes': {'overall pass rate': res}}, res['verdict']


def run_e6(root, manifest):
    result, status = run_e1(root, manifest, 'E6')
    return result, ('NEEDS PROSPECTIVE DATA' if status == 'PROMISING' else status)


RUNNERS = {'E6': run_e6, 'E1': run_e1, 'E2': run_e2, 'E3': run_e3, 'E4': run_e4, 'E5': run_e5}


# ------------------------------------------------------------------ supplementary sensitivity checks (descriptive; never change a registered verdict)
def _pooled(folds, cols, target, alpha):
    errors = []
    for year, (train, test) in folds.items():
        model = Ridge(alpha).fit(train[cols], train[target])
        errors.append(np.abs(test[target].to_numpy() - model.predict(test[cols])))
    return float(np.concatenate(errors).mean())


def sensitivity(root, manifest):
    """How fragile are E1/E2/E6 to choices that were fixed in advance? Reported next to, never instead of, the registered result."""
    out = {'note': 'descriptive robustness checks added after QA; the registered verdicts are unchanged', 'alphas': [1e-6, 1, 10, 100]}
    pairs = e1_pairs(root, manifest)
    folds = _train_test(pairs, [2023, 2024, 2025])
    base_cols = ['b_tgt', 'b_rec', 'b_yds', 'games_prev', 'is_te']
    for label, role_cols in (('E1', ROLE_FEATURES + ['rte_g']), ('E6', list(SPECS['E6']['features_role']))):
        block = {}
        for outcome, target in (('targets/g', 't_tgt'), ('receptions/g', 't_rec'), ('receiving yards/g', 't_yds')):
            rows = {}
            for alpha in out['alphas']:
                b, c = _pooled(folds, base_cols, target, alpha), _pooled(folds, base_cols + role_cols, target, alpha)
                rows[str(alpha)] = {'baseline_mae': b, 'challenger_mae': c, 'relative_gain': (b - c) / b}
            best_base = min(r['baseline_mae'] for r in rows.values())
            best_chal = min(r['challenger_mae'] for r in rows.values())
            rows['best_challenger_vs_best_baseline_relative_gain'] = (best_base - best_chal) / best_base
            block[outcome] = rows
        out[label] = block
    # E2 FP/G
    block = {}
    for min_games in (8, 4, 1):
        pairs2 = e2_pairs(root, manifest, min_games)
        folds2 = _train_test(pairs2, [2023, 2024, 2025])
        base = ['fpg', 'games_prev', 'is_te', 'is_rb']
        rows = {}
        for alpha in out['alphas']:
            b, c = _pooled(folds2, base, 't_fpg', alpha), _pooled(folds2, base + ['xfpg'], 't_fpg', alpha)
            rows[str(alpha)] = {'baseline_mae': b, 'challenger_mae': c, 'relative_gain': (b - c) / b}
        block[f'min_games_next={min_games}'] = rows
    # stronger simple baseline: add prior targets/g and carries/g (raw volume)
    pairs3 = {}
    for season in range(2022, 2026):
        prev = data.prior_features(root, manifest, season, 'efficiency')
        frame = e2_pairs(root, manifest)[season].merge(prev[['player_id', 'Receiving.TGT', 'Rushing.ATT']], on='player_id')
        frame['tgt_g'] = frame['Receiving.TGT'] / frame.games_prev
        frame['att_g'] = frame['Rushing.ATT'] / frame.games_prev
        pairs3[season] = frame
    folds3 = _train_test(pairs3, [2023, 2024, 2025])
    base = ['fpg', 'games_prev', 'is_te', 'is_rb']
    vol = base + ['tgt_g', 'att_g']
    block['volume_baseline_alpha10'] = {'baseline_mae': _pooled(folds3, base, 't_fpg', 10), 'volume_baseline_mae': _pooled(folds3, vol, 't_fpg', 10),
                                        'xfp_on_top_of_volume_mae': _pooled(folds3, vol + ['xfpg'], 't_fpg', 10),
                                        'xfp_gain_over_volume_baseline': 1 - _pooled(folds3, vol + ['xfpg'], 't_fpg', 10) / _pooled(folds3, vol, 't_fpg', 10)}
    out['E2_fp_per_game'] = block
    return out
