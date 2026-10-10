"""Synthetic replay contracts and models only; never reads historical/private rows."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'research' / 'prop-lines'))
import public_passyds_replay as replay


class PublicPropReplayTests(unittest.TestCase):
    def profile(self):
        games = [dict(date=f'2026-09-{day:02}', season=2026, week=i + 1, verified_start=True, pass_yds=150 + 30 * i)
                 for i, day in enumerate([1, 7, 14, 21, 28])]
        return dict(id='p1', name='Synthetic QB', team='BUF', position='QB', games=games,
                    stats={'pass_yds': {'n': 5}})

    def test_exact_game_requires_teams_and_kickoff_not_just_date(self):
        games = [dict(id='a', home='BUF', away='MIA', kickoff='2026-10-04T17:00:00Z'),
                 dict(id='b', home='NYG', away='DAL', kickoff='2026-10-04T17:00:00Z')]
        row = SimpleNamespace(home='Buffalo Bills', away='MIA', kick=pd.Timestamp('2026-10-04T17:00:00Z'))
        self.assertEqual(replay.match_game(row, games, {'Buffalo Bills': 'BUF'})['id'], 'a')
        row.kick = pd.Timestamp('2026-10-04T17:01:00Z')
        self.assertIsNone(replay.match_game(row, games, {'Buffalo Bills': 'BUF'}))

    def test_QB_identity_requires_unique_exact_name_position_and_game_team(self):
        p = self.profile()
        self.assertEqual(replay.match_profile({'p1': p}, 'Synthetic QB', {'BUF', 'MIA'}, {})['id'], 'p1')
        self.assertIsNone(replay.match_profile({'p1': p}, 'Synthetic QB', {'NYG', 'DAL'}, {}))
        self.assertIsNone(replay.match_profile({'p1': p, 'p2': dict(p, id='p2')}, 'Synthetic QB', {'BUF', 'MIA'}, {}))

    def test_relief_or_target_game_rows_cannot_fill_a_missing_start_window(self):
        p = self.profile()
        history, error = replay.model_history(p, '2026-10-04', 2026)
        self.assertEqual(len(history), 5)
        self.assertIsNone(error)
        p['games'][0]['verified_start'] = False
        self.assertEqual(replay.model_history(p, '2026-10-04', 2026)[1], 'incomplete_public_start_window')
        p['games'][0]['verified_start'] = True
        p['games'][0]['date'] = '2026-10-04'
        self.assertEqual(replay.model_history(p, '2026-10-04', 2026)[1], 'incomplete_public_start_window')

    def test_duplicate_history_is_rejected(self):
        p = self.profile()
        p['games'].append(p['games'][0])
        self.assertEqual(replay.model_history(p, '2026-10-04', 2026)[1], 'duplicate_history')

    def test_fixed_model_probabilities_match_recomputed_production_refit(self):
        params = json.loads((ROOT / 'config/calibration_policy.json').read_text())['markets']['pass_yds']
        history, _ = replay.model_history(self.profile(), '2026-10-04', 2026)
        models = replay.fixed_models(history, 2026, params['params'])
        actual = replay.pipeline.season_fit(history, 'passing_yards', 'lognormal', 2026, 5, market='pass_yds', position='QB')
        self.assertAlmostEqual(models['refit']['mu_log'], actual['mu_log'])
        self.assertAlmostEqual(models['refit']['sigma_log'], actual['sigma_log'])
        probabilities = replay.probabilities(models, 199.5, params['superseded_shrink_const']['params'])
        self.assertTrue(all(0 < p < 1 for p in probabilities.values()))

    def test_constant_market_probability_has_no_invented_calibration_slope(self):
        result = replay.calibrate([.5] * 20, [0, 1] * 10)
        self.assertIsNone(result['slope'])

    def test_paired_bootstrap_preserves_complete_game_clusters(self):
        frame = pd.DataFrame(dict(game_id=['g1', 'g1', 'g2', 'g2'], y=[1, 1, 0, 0],
                                  refit=[.7, .7, .3, .3], market=[.5] * 4))
        result = replay.paired_ci(frame, 'refit', 'market', 'game_id', 'brier', np.random.default_rng(1), 100)
        self.assertEqual(result['clusters'], 2)
        self.assertAlmostEqual(result['difference'], -.16)
        self.assertTrue(all(abs(value + .16) < 1e-10 for value in result['ci95']))

    def test_market_main_selection_cannot_move_after_a_push_or_missing_model(self):
        rows = pd.DataFrame(dict(pg=['g|p'] * 3, line=[190.5, 200., 210.5], books=[2, 2, 2],
                                 market=[.6, .5, .4], actual=[200.] * 3, eligible=[True, False, True]))
        self.assertEqual(replay.choose_main_lines(rows), {'g|p': 200.})

    def test_alternate_market_threshold_has_no_forecast_MAE(self):
        rows = pd.DataFrame(dict(pg=['g1|p1', 'g2|p2'], game_id=['g1', 'g2'], pid=['p1', 'p2'],
                                 actual=[100, 300], y=[0, 1], line=[150, 250], main=[False, False],
                                 raw=[.5, .5], shrink=[.5, .5], refit=[.5, .5], trailing=[.5, .5], market=[.5, .5],
                                 point_raw=[200, 200], point_refit=[200, 200], point_trailing=[200, 200], point_market=[150, 250]))
        result = replay.report(rows, {'bootstrap': {'seed': 1, 'replications': 20}})
        self.assertIsNone(result['models']['market']['mae'])
        self.assertEqual(result['models']['refit']['mae'], 100)


if __name__ == '__main__':
    unittest.main()
