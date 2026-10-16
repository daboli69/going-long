"""E13 / E14: first registered tests of two previously UNTESTED Fantasy Points families on completed seasons (prior season -> next season only).

E13  receiving separation (separation score, win rate overall and vs man/zone) for WR/TE, beyond a baseline that already holds the player's own
     per-game targets, receptions, yards, routes per game and targets per route.
E14  QB pressure / time-to-throw (pressure %, pressure-sack %, time to throw, sack %) for QBs, beyond the QB's own per-game attempts, yards and touchdowns.

Season N features come only from the season N-1 snapshot; the season N snapshot is read only as the outcome. Rolling origin, fixed ridge penalty,
cluster bootstrap, rule from `experiments.RULE`. Specs are hashed in the ledger before any run. Aggregates only; no licensed player rows are written.
"""
import numpy as np
import pandas as pd

from . import data
from .experiments import COMMON, _compare, _train_test, _worst

SEP_OVERALL = ['sep.Overall.SEP SCORE', 'sep.Overall.WIN RATE']
SEP_COVERAGE = ['cov.Man.SEP SCORE', 'cov.Zone.SEP SCORE', 'cov.Man.WIN RATE', 'cov.Zone.WIN RATE']
QB_PRESSURE = ['pa.Passing Advanced.PRESS %', 'pa.Passing Advanced.PRESS SK %', 'pa.Passing Advanced.TTT', 'pa.Passing.SACK %']
QB_QUALITY = ['pa.Passing Advanced.CPOE', 'pa.Passing Advanced.aDOT', 'pa.Passing Advanced.Deep Throw %']

SPECS = {
    'E13': {**COMMON, 'id': 'E13', 'title': 'Prior-season receiver separation -> next-season receiving yards per game (WR/TE)',
            'hypothesis': 'Separation score and win rate (overall, and against man and zone) of season N-1 improve next-season receiving yards per game beyond the '
                          'player\'s own per-game targets, receptions, yards, routes per game and targets per route.',
            'football_rationale': 'Separation is a skill that creates targets and easier catches; but the baseline already contains the volume it would produce, so only the part '
                                  'of separation not already in last year\'s production can add anything.',
            'unit': 'WR/TE single-team player-season pair (N-1 -> N), >= 8 games in both seasons',
            'baselines': {'B1': 'ridge on prior per-game targets, receptions, yards, routes per game, targets per route, games played, TE flag'},
            'challengers': {'SEP_OVERALL': SEP_OVERALL, 'SEP_COVERAGE': SEP_COVERAGE}, 'primary_outcome': 'receiving yards/g', 'secondary_outcomes': ['targets/g'],
            'primary_comparison': 'B1 + each separation block vs B1 on receiving yards/g (2 comparisons)',
            'splits': {'pairs': ['2022->2023', '2023->2024', '2024->2025'], 'test': ['2023->2024', '2024->2025'], 'rolling_origin': True,
                       'note': 'separation tables start in 2022, so only two test seasons exist; the 2-of-2 requirement is therefore strict and power is low'},
            'multiple_testing': 'Bonferroni over 2 primary comparisons (97.5% CI)', 'sources': ['Fantasy Points receiving_separation_by_routes, receiving_separation_by_coverage, receiving_routes_run, receiving_basic'],
            'leakage': 'features from season N-1 only; season N snapshot is the outcome only', 'markets': ['receiving yards', 'receptions'],
            'limitations': 'about 100-150 pairs per season; later-listed team changes are dropped; licensed inputs stay local'},
    'E14': {**COMMON, 'id': 'E14', 'title': 'Prior-season QB pressure and time to throw -> next-season passing yards and touchdowns per game',
            'hypothesis': 'A QB\'s season N-1 pressure rate, pressure-to-sack rate, time to throw and sack rate improve next-season passing yards per game beyond his own per-game '
                          'attempts, yards and touchdowns.',
            'football_rationale': 'Pressure is partly offensive-line and scheme, partly the QB; if it persists it should explain some of the year-to-year change in passing output.',
            'unit': 'single-team QB season pair (N-1 -> N), >= 8 games in both seasons',
            'baselines': {'B1': 'ridge on prior per-game attempts, passing yards, touchdowns and games played'},
            'challengers': {'PRESSURE': QB_PRESSURE}, 'primary_outcome': 'passing yards/g', 'secondary_outcomes': ['passing TD/g', 'QUALITY block (CPOE, aDOT, deep-throw %) descriptive'],
            'primary_comparison': 'B1 + PRESSURE vs B1 on passing yards/g (1 comparison)',
            'splits': {'pairs': ['2021->2022', '2022->2023', '2023->2024', '2024->2025'], 'test': ['2022->2023', '2023->2024', '2024->2025'], 'rolling_origin': True},
            'multiple_testing': 'none (single primary); 95% CI', 'sources': ['Fantasy Points passing_advanced 2021-2025'],
            'leakage': 'features from season N-1 only; season N snapshot is the outcome only', 'markets': ['passing yards', 'passing TDs'],
            'limitations': 'about 25-30 qualifying QBs per season: very low power, INCONCLUSIVE is the expected honest outcome unless the effect is large'},
}


def _clean(frame):
    return frame[~frame.player_id.isna()]


def e13_pairs(root, manifest):
    pairs = {}
    for season in (2023, 2024, 2025):
        data.assert_no_same_season(season - 1, season)
        sep = data.prior_features(root, manifest, season, 'receiving_separation_by_routes')
        cov = data.prior_features(root, manifest, season, 'receiving_separation_by_coverage')
        rr = data.prior_features(root, manifest, season, 'receiving_routes_run')
        basic = data.prior_features(root, manifest, season, 'receiving_basic')
        now = data.outcome_frame(root, manifest, season, 'receiving_basic')
        if any(f is None for f in (sep, cov, rr, basic, now)):
            continue
        left = sep[['player_id', 'pos', 'games'] + [c[4:] for c in SEP_OVERALL]].rename(columns={c[4:]: c for c in SEP_OVERALL}).rename(columns={'games': 'games_prev'})
        left = left.merge(cov[['player_id'] + [c[4:] for c in SEP_COVERAGE]].rename(columns={c[4:]: c for c in SEP_COVERAGE}), on='player_id')
        left = left.merge(rr[['player_id', 'Overall.RTE', 'Overall.TPRR']].rename(columns={'Overall.RTE': 'rte', 'Overall.TPRR': 'tprr'}), on='player_id')
        left = left.merge(basic[['player_id', 'Receiving.TGT', 'Receiving.REC', 'Receiving.YDS']].rename(
            columns={'Receiving.TGT': 'p_tgt', 'Receiving.REC': 'p_rec', 'Receiving.YDS': 'p_yds'}), on='player_id')
        out = now[['player_id', 'games', 'Receiving.TGT', 'Receiving.YDS']].rename(columns={'games': 'games_next', 'Receiving.TGT': 'y_tgt', 'Receiving.YDS': 'y_yds'})
        frame = left[left.pos.isin(['WR', 'TE']) & (left.games_prev >= 8)].merge(out, on='player_id')
        frame = frame[frame.games_next >= 8].dropna().copy()
        frame['is_te'] = (frame.pos == 'TE').astype(float)
        for k in ('tgt', 'rec', 'yds'):
            frame['b_' + k] = frame['p_' + k] / frame.games_prev
        frame['rte_g'] = frame['rte'] / frame.games_prev
        frame['t_yds'] = frame['y_yds'] / frame.games_next
        frame['t_tgt'] = frame['y_tgt'] / frame.games_next
        frame['season'] = season
        pairs[season] = frame
    return pairs


E13_BASE = ['b_tgt', 'b_rec', 'b_yds', 'rte_g', 'tprr', 'games_prev', 'is_te']


def run_e13(root, manifest):
    spec = SPECS['E13']
    pairs = e13_pairs(root, manifest)
    folds = _train_test(pairs, [2024, 2025])
    out, verdicts = {}, []
    for outcome, target, primary in (('receiving yards/g', 't_yds', True), ('targets/g', 't_tgt', False)):
        res = {}
        for name, cols in spec['challengers'].items():
            r = _compare(folds, {'B1': E13_BASE, 'C': E13_BASE + cols}, target, 'player_id', 1 - 0.05 / 2 if primary else 0.95, spec['rule_numbers'], 'B1', 'C')
            res[name] = r
            if primary:
                verdicts.append(r['verdict'])
        out[outcome] = res
    return {'sample_sizes': {str(y): int(len(f)) for y, f in pairs.items()}, 'outcomes': out, 'primary': 'receiving yards/g'}, _worst(verdicts)


def e14_pairs(root, manifest):
    pairs = {}
    for season in range(2022, 2026):
        data.assert_no_same_season(season - 1, season)
        prev = data.prior_features(root, manifest, season, 'passing_advanced')
        now = data.outcome_frame(root, manifest, season, 'passing_advanced')
        if prev is None or now is None:
            continue
        keep = ['player_id', 'games', 'Passing.ATT', 'Passing.YDS', 'Passing.TD'] + [c[3:] for c in QB_PRESSURE + QB_QUALITY]
        left = prev[keep].rename(columns={c[3:]: c for c in QB_PRESSURE + QB_QUALITY}).rename(columns={'games': 'games_prev'})
        left = left.rename(columns={'Passing.ATT': 'p_att', 'Passing.YDS': 'p_yds', 'Passing.TD': 'p_td'})
        res = now[['player_id', 'games', 'Passing.YDS', 'Passing.TD']].rename(columns={'games': 'games_next', 'Passing.YDS': 'y_yds', 'Passing.TD': 'y_td'})
        frame = left[left.games_prev >= 8].merge(res, on='player_id')
        frame = frame[frame.games_next >= 8].dropna().copy()
        for k in ('att', 'yds', 'td'):
            frame['b_' + k] = frame['p_' + k] / frame.games_prev
        frame['t_yds'] = frame['y_yds'] / frame.games_next
        frame['t_td'] = frame['y_td'] / frame.games_next
        frame['season'] = season
        pairs[season] = frame
    return pairs


E14_BASE = ['b_att', 'b_yds', 'b_td', 'games_prev']


def run_e14(root, manifest):
    spec = SPECS['E14']
    pairs = e14_pairs(root, manifest)
    folds = _train_test(pairs, [2023, 2024, 2025])
    out, verdicts = {}, []
    for outcome, target in (('passing yards/g', 't_yds'), ('passing TD/g', 't_td')):
        primary = outcome == 'passing yards/g'
        out[outcome] = {'PRESSURE': _compare(folds, {'B1': E14_BASE, 'C': E14_BASE + QB_PRESSURE}, target, 'player_id', 0.95, spec['rule_numbers'], 'B1', 'C')}
        if primary:
            verdicts.append(out[outcome]['PRESSURE']['verdict'])
    out['passing yards/g']['QUALITY_descriptive'] = _compare(folds, {'B1': E14_BASE, 'C': E14_BASE + QB_QUALITY}, 't_yds', 'player_id', 0.95, spec['rule_numbers'], 'B1', 'C')
    return {'sample_sizes': {str(y): int(len(f)) for y, f in pairs.items()}, 'outcomes': out, 'primary': 'passing yards/g'}, _worst(verdicts)


RUNNERS = {'E13': run_e13, 'E14': run_e14}
