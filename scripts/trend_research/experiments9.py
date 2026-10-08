"""Phase 3 DFS research on the shared football projections.

P3-7  Does the Champion v2 mean (prior-strength blend where it passed its gates) improve the modelled-component DraftKings projection of the NEXT game?
P3-8  Are the predictive distributions of DraftKings points (floor / median / ceiling) calibrated, and does the v2 chain with within-player dependence improve them?
The DFS engine is not a separate football model: it consumes the same player projections as betting, so a betting-side mean improvement must be measured in DraftKings points too.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import dfs_data
from .experiments2 import COMMON, MARKET_RULES, _blend, champion_rows
from .experiments5 import _cluster_ci

POSITIONS = ('QB', 'RB', 'WR', 'TE')
PARTIAL_COEF = {'pass_yds': 0.04, 'pass_tds': 4.0, 'rush_yds': 0.1, 'rush_tds': 6.0, 'receptions': 1.0, 'rec_yds': 0.1, 'rec_tds': 6.0}
PROMOTED = ('pass_yds', 'pass_tds', 'rush_tds', 'receptions', 'rec_yds', 'rec_tds')  # P3-1 markets promoted to the v2 mean (rush_yds stays v1)

SPECS = {
    'P3-7': {**COMMON, 'id': 'P3-7', 'title': 'DraftKings projection: Champion v2 means vs the 80/20 means, modelled-component DK points of the next game',
             'hypothesis': 'Replacing the 80/20 market means by the validated blend (same c as P3-1, no re-tuning) lowers the error of the projected modelled-component DraftKings points, mainly in weeks 1-6.',
             'football_rationale': 'DFS uses the same player projections as betting; the shrinkage lowers noise from one-game reads of a role.',
             'population': 'reconstructed Champion rows 2021-2025 for QB/RB/WR/TE with every component mean available; outcome = partial DK points (pass yds .04, pass TD 4, rush yds .1, rush TD 6, rec 1, rec yds .1, rec TD 6)',
             'splits': {'validation': [2024], 'holdout': [2025], 'note': 'c values come from P3-1 (development 2021-2023); nothing is re-fit'},
             'metric': 'MAE of partial DK points by position; player-clustered paired bootstrap; Bonferroni over 4 positions (98.75% intervals)',
             'decision_rule': {'PROMISING': 'relative MAE improvement >= 1% in BOTH 2024 and 2025 AND the 2025 interval excludes 0', 'REJECTED': 'the 2025 interval lies below a 1% gain', 'INCONCLUSIVE': 'otherwise'},
             'rule_numbers': {'min_relative_improvement': 0.01}, 'sources': ['nflverse weekly stats'], 'leakage': 'as P3-1', 'markets': ['DFS projection'],
             'limitations': 'partial DK points only (no interceptions, fumbles, conversions, bonuses, defence); no salaries or field data exist for these seasons, so nothing about lineup value is tested'},
}


def _chosen_c():
    from .experiments7 import _c_from_ledger
    return _c_from_ledger()


def partial_projection(frame, c, version):
    """Partial DK projection of every row for 'v1' (80/20 means) or 'v2' (blend where promoted)."""
    total = np.zeros(len(frame))
    ok = np.ones(len(frame), bool)
    for market, coef in PARTIAL_COEF.items():
        if version == 'v2' and market in PROMOTED:
            mean = _blend(frame, market, c[market])
        else:
            mean = frame['champ_' + market].to_numpy(float)
        # a position that does not play the market contributes zero (e.g. WR passing)
        positions_for = MARKET_RULES[market][0]
        applies = frame.position.isin(positions_for).to_numpy()
        part = np.where(applies, mean, 0.0)
        ok &= ~(applies & np.isnan(mean))
        total += coef * np.nan_to_num(part)
    return total, ok


def actual_partial(root):
    games = dfs_data.player_games(root, range(2021, 2026))
    return games[['player_id', 'season', 'week', 'dk', 'dk_partial']]


def run_p3_7(root, manifest):
    c = _chosen_c()
    rows = champion_rows(root)
    rows = rows[rows.position.isin(POSITIONS)].reset_index(drop=True)
    actual = actual_partial(root)
    rows = rows.merge(actual, on=['player_id', 'season', 'week'], how='left').dropna(subset=['dk_partial'])
    rows['proj_v1'], ok1 = partial_projection(rows, c, 'v1')
    rows['proj_v2'], ok2 = partial_projection(rows, c, 'v2')
    rows = rows[ok1 & ok2]
    conf = 1 - 0.05 / 4
    out, verdicts = {'positions': {}}, []
    for pos in POSITIONS:
        sub = rows[rows.position == pos]
        if pos == 'QB':
            sub = sub[sub.start]
        res = {}
        gates = []
        for label, season in (('validation', 2024), ('holdout', 2025)):
            t = sub[sub.season == season]
            e1, e2 = np.abs(t.dk_partial - t.proj_v1), np.abs(t.dk_partial - t.proj_v2)
            gain = (e1 - e2) / e1.mean()
            m, lo, hi = _cluster_ci(gain.to_numpy(), t.player_id.to_numpy(), conf)
            early = (t.week <= 6).to_numpy()
            res[label] = {'n': int(len(t)), 'mae_v1': float(e1.mean()), 'mae_v2': float(e2.mean()), 'relative_gain': m, 'ci': [lo, hi],
                          'weeks_1_6_relative': float(1 - e2[early].mean() / e1[early].mean()) if early.sum() > 100 else None,
                          'weeks_7_plus_relative': float(1 - e2[~early].mean() / e1[~early].mean()),
                          'rmse_v1': float(np.sqrt(((t.dk_partial - t.proj_v1) ** 2).mean())), 'rmse_v2': float(np.sqrt(((t.dk_partial - t.proj_v2) ** 2).mean())),
                          'bias_v1': float((t.proj_v1 - t.dk_partial).mean()), 'bias_v2': float((t.proj_v2 - t.dk_partial).mean())}
            gates.append(m >= 0.01)
        label = 'PROMISING' if all(gates) and res['holdout']['ci'][0] > 0 else ('REJECTED' if res['holdout']['ci'][1] < 0.01 else 'INCONCLUSIVE')
        res['verdict'] = label
        out['positions'][pos] = res
        verdicts.append(label)
    status = 'PROMISING' if 'PROMISING' in verdicts else ('REJECTED' if set(verdicts) == {'REJECTED'} else 'INCONCLUSIVE')
    return out, status


RUNNERS = {'P3-7': run_p3_7}
