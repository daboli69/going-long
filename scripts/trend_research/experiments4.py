"""Post-QA follow-ups. Both are EXPLORATORY (designed after seeing E7/E8 results), so a PROMISING result is capped at NEEDS PROSPECTIVE DATA.

E7b  count markets judged by Poisson log score (MAE on 0/1 and small-count outcomes is not a sensible loss: QA found it picks the grid edge)
E8b  expected-opportunity sources against RAW VOLUME baselines (QA: most of E8's gain was raw volume, not expected-points quality)
"""
import numpy as np
from scipy.stats import poisson

from . import champion
from .experiments2 import COMMON, MARKET_RULES, _blend, _eligible, _folds, champion_rows, data_ffopp, with_ffopp, with_fp
from .stats import Ridge, paired_bootstrap

LOG_GRID = [0.25, 0.5, 1, 2, 3, 4, 6, 8, 12, 20, 40]
COUNT_MARKETS = ('receptions', 'rec_tds', 'rush_tds', 'atd', 'pass_tds')
FLOOR = 0.01
RULE = {'min_gain_nats': 0.005, 'min_years_better': 2}

SPECS = {
    'E7b': {**COMMON, 'id': 'E7b', 'exploratory': True,
            'title': 'EXPLORATORY follow-up to E7: count markets judged by Poisson log score',
            'hypothesis': 'For count markets (receptions, receiving/rushing TDs, anytime TD, QB passing TDs) a learned prior strength chosen and judged by Poisson log score improves on the production 80/20 weighting in weeks 1-6.',
            'football_rationale': 'Same as E7. For 0/1-like outcomes the mean absolute error is a poor loss; the log score is the proper score for the Poisson model that prices them.',
            'population': 'as E7, markets receptions, rec_tds, rush_tds, atd, pass_tds', 'grid': LOG_GRID,
            'comparators': {'W0': 'Champion (production 80/20)', 'W3': 'learned shrinkage with c chosen on TRAIN seasons by mean Poisson log score'},
            'primary_comparison': 'W3 vs W0, mean per-row Poisson log score, weeks 1-6, per market', 'multiple_testing': 'Bonferroni over 5 markets (99% CI)',
            'decision_rule': {'PROMISING': 'mean gain >= 0.005 nats per row AND adjusted CI above 0 AND better in >= 2 of 3 test seasons (capped at NEEDS PROSPECTIVE DATA: post-hoc)',
                              'REJECTED': 'the adjusted CI lies below 0.005 nats', 'INCONCLUSIVE': 'otherwise'}, 'rule_numbers': RULE,
            'sources': ['as E7'], 'leakage': 'as E7', 'markets': ['receptions', 'anytime TD', 'QB passing TDs'],
            'limitations': 'post-hoc after QA found that E7 chose c by MAE; secondary MSE is reported but is not a decision metric'},
    'E8b': {**COMMON, 'id': 'E8b', 'exploratory': True,
            'title': 'EXPLORATORY follow-up to E8: expected-opportunity sources against raw-volume baselines',
            'hypothesis': 'ffopportunity expected values (prior-season and in-season) and Fantasy Points XFP add information beyond raw volume, including raw IN-SEASON volume.',
            'football_rationale': 'Expected points should describe quality of touches, which raw counts cannot.',
            'population': 'as E8',
            'models': {'M0': 'Champion mean + position flags', 'MV': 'M0 + Champion-window volume per game', 'MVR': 'MV + current-season mean volume + games in the window this season',
                       'MFP': 'MV + Fantasy Points prior-season XFP/G, XTD/G', 'MEOP': 'MV + ffopportunity prior-season expected value',
                       'MEO': 'MVR + ffopportunity prior-season and in-season rolling expected value + count of games',
                       'MEOFP': 'MEO + Fantasy Points XFP/G, XTD/G'},
            'primary_comparisons': ['MFP vs MV', 'MEOP vs MV', 'MEO vs MVR', 'MEOFP vs MEO'],
            'metric': 'MAE for receptions, rec_yds, rush_yds; mean Poisson deviance proxy (negative log score) for rec_tds, rush_tds',
            'multiple_testing': 'Bonferroni over 5 markets x 4 comparisons = 20 (99.75% CI)', 'rule_numbers': {'min_relative_improvement': 0.01, 'min_years_better': 2,
                                                                                                             'reject_below_relative_improvement': 0.0025, 'reject_requires_ci': True},
            'sources': ['as E8'], 'leakage': 'as E8', 'markets': ['receptions', 'receiving yards', 'receiving TD', 'rushing yards', 'rushing TD'],
            'limitations': 'post-hoc after QA; ffopportunity expected-value model fitting period not verified (suspected out of sample for 2023-2025)'},
}


def _logscore(y, lam):
    return poisson.logpmf(y, np.maximum(lam, FLOOR))


def run_e7b(root, manifest):
    spec = SPECS['E7b']
    frame = champion_rows(root)
    out, verdicts = {}, []
    confidence = 1 - 0.05 / 5
    for market in COUNT_MARKETS:
        rows = _eligible(frame, market)
        folds = _folds(rows)
        per_year, early_gain, early_groups, chosen = {}, [], [], {}
        w0_scores, w3_scores = [], []
        better = 0
        for year, (train, test) in folds.items():
            ytr = train['y_' + market].to_numpy(float)
            best_c = max(LOG_GRID, key=lambda c: float(_logscore(ytr, _blend(train, market, c)).mean()))
            chosen[str(year)] = best_c
            y = test['y_' + market].to_numpy(float)
            lam0 = test['champ_' + market].to_numpy(float)
            lam3 = _blend(test, market, best_c)
            early = (test.week <= 6).to_numpy()
            g0, g3 = _logscore(y[early], lam0[early]), _logscore(y[early], lam3[early])
            per_year[str(year)] = {'log_score_champion': float(g0.mean()), 'log_score_w3': float(g3.mean()), 'gain': float((g3 - g0).mean()), 'n': int(early.sum()),
                                   'mse_champion': float(((y[early] - lam0[early]) ** 2).mean()), 'mse_w3': float(((y[early] - lam3[early]) ** 2).mean())}
            better += (g3 - g0).mean() > 0
            early_gain.append(g3 - g0)
            early_groups.append(test.player_id.to_numpy()[early])
            w0_scores.append(g0)
            w3_scores.append(g3)
        gains, groups = np.concatenate(early_gain), np.concatenate(early_groups)
        rng = np.random.default_rng(20261008)
        index = {g: np.flatnonzero(groups == g) for g in np.unique(groups)}
        keys = list(index)
        boots = [gains[np.concatenate([index[keys[i]] for i in rng.choice(len(keys), size=len(keys), replace=True)])].mean() for _ in range(2000)]
        lo, hi = np.quantile(boots, [(1 - confidence) / 2, 1 - (1 - confidence) / 2])
        mean_gain = float(gains.mean())
        if lo > 0 and mean_gain >= spec['rule_numbers']['min_gain_nats'] and better >= spec['rule_numbers']['min_years_better']:
            label = 'PROMISING'
        elif hi < spec['rule_numbers']['min_gain_nats']:
            label = 'REJECTED'
        else:
            label = 'INCONCLUSIVE'
        out[market] = {'verdict': label, 'mean_log_score_gain_per_row': mean_gain, 'adjusted_ci': [float(lo), float(hi)], 'years_better': int(better), 'chosen_c': chosen,
                       'per_test_year': per_year, 'n': int(len(gains))}
        verdicts.append(label)
    status = 'NEEDS PROSPECTIVE DATA' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out}, status


def run_e8b(root, manifest):
    spec = SPECS['E8b']
    frame = with_ffopp(champion_rows(root), root)
    frame = with_fp(frame, root, manifest, 'efficiency', ['FPTS.XFP/G', 'FPTS.XTD/G'], {'FPTS.XFP/G': 'fp_xfpg', 'FPTS.XTD/G': 'fp_xtdg'})
    frame = frame[frame.season >= 2022].copy()
    frame['is_te'], frame['is_rb'] = (frame.position == 'TE').astype(float), (frame.position == 'RB').astype(float)
    spec_markets = {'receptions': ('receptions_exp', 'champ_targets', 'cur_targets', False), 'rec_yds': ('rec_yards_gained_exp', 'champ_targets', 'cur_targets', False),
                    'rec_tds': ('rec_touchdown_exp', 'champ_targets', 'cur_targets', True), 'rush_yds': ('rush_yards_gained_exp', 'champ_carries', 'cur_carries', False),
                    'rush_tds': ('rush_touchdown_exp', 'champ_carries', 'cur_carries', True)}
    rule = spec['rule_numbers']
    out, verdicts = {}, []
    confidence = 1 - 0.05 / 20
    for market, (eo, vol, cur_vol, use_log) in spec_markets.items():
        rows = _eligible(frame, market).copy()
        rows[cur_vol] = rows[cur_vol].fillna(rows[vol])
        base = ['champ_' + market, 'is_te', 'is_rb']
        mv = base + [vol]
        mvr = mv + [cur_vol, 'k']
        models = {'M0': base, 'MV': mv, 'MVR': mvr, 'MFP': mv + ['fp_xfpg', 'fp_xtdg'], 'MEOP': mv + ['eop_' + eo], 'MEO': mvr + ['eop_' + eo, 'eor_' + eo, 'k_eo'],
                  'MEOFP': mvr + ['eop_' + eo, 'eor_' + eo, 'k_eo', 'fp_xfpg', 'fp_xtdg']}
        work = rows.dropna(subset=['fp_xfpg', 'fp_xtdg', 'eop_' + eo, vol]).copy()
        folds = {y: (tr, te) for y, (tr, te) in _folds(work, first_train=2022).items() if len(tr) > 50 and len(te) > 50}
        per_year, losses, groups = {}, {m: [] for m in models}, []
        for year, (train, test) in folds.items():
            y = test['y_' + market].to_numpy(float)
            row = {}
            for name, cols in models.items():
                p = Ridge().fit(train[cols], train['y_' + market]).predict(test[cols])
                loss = -_logscore(y, p) if use_log else np.abs(y - p)
                row[name] = float(loss.mean())
                losses[name].append(loss)
            row['n'] = int(len(y))
            per_year[str(year)] = row
            groups.append(test.player_id.to_numpy())
        g = np.concatenate(groups)
        comparisons = {}
        for new, base_name in (('MFP', 'MV'), ('MEOP', 'MV'), ('MEO', 'MVR'), ('MEOFP', 'MEO')):
            la, lb = np.concatenate(losses[base_name]), np.concatenate(losses[new])
            delta = paired_bootstrap(la, lb, g, confidence=confidence)
            base_loss = float(la.mean())
            better = sum(1 for y in per_year.values() if y[new] < y[base_name])
            rel = -delta['delta_mae'] / base_loss
            if delta['ci_high'] < 0 and rel >= rule['min_relative_improvement'] and better >= rule['min_years_better']:
                label = 'PROMISING'
            elif delta['ci_low'] > 0 or -delta['ci_low'] / base_loss < rule['min_relative_improvement']:
                label = 'REJECTED'
            else:
                label = 'INCONCLUSIVE'
            comparisons[f'{new} vs {base_name}'] = {'verdict': label, 'relative_improvement': rel, 'ci': [delta['ci_low'], delta['ci_high']], 'years_better': int(better),
                                                    'base_loss': base_loss, 'new_loss': float(lb.mean())}
            verdicts.append(label)
        out[market] = {'metric': 'neg_poisson_log_score' if use_log else 'mae', 'per_test_year': per_year, 'comparisons': comparisons, 'n_rows': int(len(work))}
    status = 'NEEDS PROSPECTIVE DATA' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out}, status


RUNNERS = {'E7b': run_e7b, 'E8b': run_e8b}
