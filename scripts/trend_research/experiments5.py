"""Phase 3, experiment P3-1: the production 80/20 weighting against a learned prior-strength blend, under a development / validation / holdout protocol.

Protocol (registered before this module is run):
  development  2021-2023 target seasons  - the prior strength c is chosen here, per market, and then frozen
  validation   2024                      - must support the blend
  holdout      2025                      - evaluated once, c unchanged. Honest caveat: E7/E7b (wave 2) already looked at 2023-2025 for this same idea with c re-fit
                                           on earlier seasons, so 2025 is a *confirmation*, not an untouched sample. 2026 (live) is the only unseen data.
Gate for PROMISING: in BOTH 2024 and 2025 the blend improves the metric in weeks 1-6 by the registered minimum, the player-clustered interval of the
2025 holdout excludes 0, all-weeks accuracy is not worse by more than the registered tolerance, and on rows where the Champion mean is >= 0.1 (so a
zero-mean artefact cannot drive the result) counts still improve.
"""
import numpy as np
from scipy.stats import poisson

from .experiments2 import C_GRID, COMMON, MARKET_RULES, _blend, _eligible, champion_rows

FLOOR = 0.01
COUNT = ('receptions', 'rec_tds', 'rush_tds', 'atd', 'pass_tds')
YARDS = ('rec_yds', 'rush_yds', 'pass_yds')
LOG_GRID = [0.25, 0.5, 1, 2, 3, 4, 6, 8, 12, 20, 40]
RULE = {'yards_min_relative_mae': 0.01, 'counts_min_nats': 0.005, 'holdout_ci_excludes_zero': True, 'all_weeks_max_regress': 0.0025, 'subset_mean_floor': 0.1,
        'early_weeks': 6, 'years_required': [2024, 2025]}

SPECS = {
    'P3-1': {**COMMON, 'id': 'P3-1', 'title': 'Champion Challenger: learned prior-strength blend (dynamic shrinkage) under development/validation/holdout',
             'hypothesis': 'Replacing the fixed 80% current / 20% earlier weighting by (k*current + c*prior)/(k + c), with c learned per market on 2021-2023 only, reduces error in the first six weeks '
                           'without hurting later weeks, and holds in 2024 (validation) and 2025 (holdout).',
             'football_rationale': 'One or two games are a noisy measure of a role or a rate; the prior season holds most of the information early and the current season takes over as games accumulate.',
             'population': 'reconstructed Champion rows 2021-2025 (ready window, QBs verified starts), by market', 'markets': list(MARKET_RULES),
             'grid': {'yards': C_GRID, 'counts': LOG_GRID},
             'splits': {'development': [2021, 2022, 2023], 'validation': [2024], 'holdout': [2025], 'prospective': '2026 (shadow)',
                        'disclosure': '2025 is a confirmation holdout: wave-2 experiments E7/E7b already examined 2023-2025 for the same idea with rolling re-fit'},
             'metric': 'yardage markets: MAE of the mean; count markets: mean Poisson log score with the mean floored at 0.01 (plus the same on rows with Champion mean >= 0.1)',
             'selection_metric': 'same as the metric, on development seasons only (all weeks, so that c balances early and late weeks)',
             'decision_rule': {'PROMISING': 'weeks 1-6: validation AND holdout each improve by >= 1% MAE (yards) or >= 0.005 nats (counts); holdout player-clustered 95% CI (Bonferroni over 8 markets) excludes 0; '
                                            'all-weeks metric not worse than the tolerance; counts also improve on rows with Champion mean >= 0.1',
                               'REJECTED': 'holdout early-week 99.4% interval lies entirely below the minimum improvement', 'INCONCLUSIVE': 'otherwise'},
             'rule_numbers': RULE, 'multiple_testing': 'Bonferroni over 8 markets (99.375% intervals)',
             'sources': ['nflverse weekly player stats, snap counts, schedules 2019-2025'], 'leakage': 'window strictly before the target week; c fixed on 2021-2023',
             'limitations': 'projected mean and Poisson/lognormal score only: no historical prop prices exist, so no ROI or closing-line value. Injury adjustments are not reconstructed.'},
}


def _log(y, lam):
    return poisson.logpmf(y, np.maximum(lam, FLOOR))


def _cluster_ci(values, groups, confidence, draws=2000, seed=20261008):
    """Mean and player-clustered bootstrap interval of per-row values."""
    values, groups = np.asarray(values, float), np.asarray(groups)
    _, inverse = np.unique(groups, return_inverse=True)
    sums = np.bincount(inverse, weights=values)
    counts = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(sums), size=(draws, len(sums)))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.quantile(boot, [(1 - confidence) / 2, 1 - (1 - confidence) / 2])
    return float(values.mean()), float(lo), float(hi)


def _loss(market, y, lam):
    return _log(y, lam) if market in COUNT else -np.abs(y - lam)  # higher is better for both


def _metric(market, y, lam):
    return float(_loss(market, y, lam).mean())


def run_p3_1(root, manifest):
    spec = SPECS['P3-1']
    frame = champion_rows(root)
    out, verdicts, best = {}, [], {}
    conf = 1 - 0.05 / len(MARKET_RULES)
    for market in MARKET_RULES:
        rows = _eligible(frame, market)
        dev = rows[rows.season <= 2023]
        grid = LOG_GRID if market in COUNT else C_GRID
        y_dev = dev['y_' + market].to_numpy(float)
        scores = {c: _metric(market, y_dev, _blend(dev, market, c)) for c in grid}
        c = max(scores, key=scores.get)
        best[market] = c
        cells, gate = {}, {}
        for label, season in (('validation', 2024), ('holdout', 2025)):
            test = rows[rows.season == season]
            y = test['y_' + market].to_numpy(float)
            base, new = test['champ_' + market].to_numpy(float), _blend(test, market, c)
            early = (test.week <= RULE['early_weeks']).to_numpy()
            gain = _loss(market, y, new) - _loss(market, y, base)  # positive = blend better
            g_early, groups = gain[early], test.player_id.to_numpy()[early]
            mean_gain, lo, hi = _cluster_ci(g_early, groups, conf)
            base_level = float(np.abs(y[early] - base[early]).mean()) if market in YARDS else None
            rel = mean_gain / base_level if base_level else None
            all_gain = float(gain.mean())
            subset = early & (base >= RULE['subset_mean_floor'])
            cells[label] = {'season': season, 'n_early': int(early.sum()), 'early_gain': mean_gain, 'early_ci': [lo, hi],
                            'early_relative_mae': rel, 'all_weeks_gain': all_gain,
                            'early_champion_metric': float(_loss(market, y[early], base[early]).mean()), 'early_blend_metric': float(_loss(market, y[early], new[early]).mean()),
                            'early_gain_where_champion_mean_ge_0.1': float(gain[subset].mean()) if subset.any() else None, 'n_subset': int(subset.sum()),
                            'mean_pred_champion_early': float(base[early].mean()), 'mean_pred_blend_early': float(new[early].mean()), 'mean_actual_early': float(y[early].mean())}
            gate[label] = (rel is not None and rel >= RULE['yards_min_relative_mae']) if market in YARDS else mean_gain >= RULE['counts_min_nats']
        hold = cells['holdout']
        passes = gate['validation'] and gate['holdout'] and hold['early_ci'][0] > 0
        tolerance_ok = (hold['all_weeks_gain'] / (np.abs(rows[rows.season == 2025]['y_' + market] - rows[rows.season == 2025]['champ_' + market]).mean()) >= -RULE['all_weeks_max_regress']) if market in YARDS \
            else hold['all_weeks_gain'] >= -RULE['all_weeks_max_regress']
        subset_ok = True if market in YARDS else (cells['holdout']['early_gain_where_champion_mean_ge_0.1'] or 0) > 0 and (cells['validation']['early_gain_where_champion_mean_ge_0.1'] or 0) > 0
        floor = RULE['yards_min_relative_mae'] if market in YARDS else RULE['counts_min_nats']
        ceiling_gain = (hold['early_ci'][1] / (hold['early_champion_metric'] and 1)) if market in COUNT else (hold['early_ci'][1] / (np.abs(hold['early_champion_metric'])))
        if passes and tolerance_ok and subset_ok:
            label = 'PROMISING'
        elif (market in COUNT and hold['early_ci'][1] < floor) or (market in YARDS and ceiling_gain < floor):
            label = 'REJECTED'
        else:
            label = 'INCONCLUSIVE'
        out[market] = {'verdict': label, 'chosen_c': c, 'development_scores': {str(k): v for k, v in scores.items()}, 'validation': cells['validation'], 'holdout': cells['holdout'],
                       'gates': {'validation_min_effect': bool(gate['validation']), 'holdout_min_effect': bool(gate['holdout']), 'holdout_ci_excludes_zero': bool(hold['early_ci'][0] > 0),
                                 'all_weeks_tolerance': bool(tolerance_ok), 'subset_ok': bool(subset_ok)}}
        verdicts.append(label)
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return {'markets': out, 'chosen_c': best}, status


RUNNERS = {'P3-1': run_p3_1}
