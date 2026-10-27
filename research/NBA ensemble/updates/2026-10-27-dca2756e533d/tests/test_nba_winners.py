import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scripts.nba_winners.data import digest, load_snapshot, normalize_sdv, snapshot, validate_games, write_new
from scripts.nba_winners.features import FEATURES, feature_rows, state_at
from scripts.nba_winners.models import NAMES, debate, weights, fit, probabilities
from scripts.nba_winners.__main__ import development_games
from scripts.nba_winners.evaluation import replay, report

CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'config/nba_winners_v1.json').read_text())


def games(count=22):
    start = datetime(2024, 10, 22, 23, tzinfo=timezone.utc)
    return [dict(game_id=f'espn:{i}', season=2025, tipoff=(start + timedelta(days=i)).isoformat(),
                 home='BOS' if i % 2 else 'NYK', away='NYK' if i % 2 else 'BOS',
                 neutral=False, completed=True, home_score=110 + i % 4, away_score=105 + i % 7)
            for i in range(count) if 110 + i % 4 != 105 + i % 7]


class NBAWinnersTest(unittest.TestCase):
    def test_future_and_own_scores_cannot_change_pregame_features(self):
        original = games()
        changed = copy.deepcopy(original)
        changed[-1]['home_score'] = 200
        a, b = feature_rows(original, CONFIG), feature_rows(changed, CONFIG)
        self.assertEqual([r['game']['game_id'] for r in a], [r['game']['game_id'] for r in b])
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x['x'], y['x'])

    def test_lagged_score_and_unlagged_schedule_are_separate(self):
        source = games()
        target = source[-1]
        origin = datetime.fromisoformat(target['tipoff'])
        state = state_at(source, CONFIG, origin)
        x, counts = state.features(target)
        self.assertIsNotNone(x)
        # Previous day's tipoff contributes to rest while its result is embargoed.
        self.assertLess(sum(counts), 2 * (len(source) - 1))
        self.assertEqual(x[FEATURES.index('rest_difference')], 0)
        recent = [tip for tip in state.appearances[(2025, 'BOS')] if origin - tip < timedelta(days=2)]
        self.assertTrue(recent)
        previous = copy.deepcopy(source)
        previous[-2]['home_score'] = 250
        np.testing.assert_array_equal(x, state_at(previous, CONFIG, origin).features(target)[0])

    def test_future_season_is_not_a_prior_for_new_teams(self):
        target = dict(games()[-1], season=2027, completed=False, home_score=None, away_score=None)
        state = state_at(games(), CONFIG, datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertIsNone(state.features(target)[0])

    def test_regular_season_provider_flag_does_not_admit_allstar_or_cup_final(self):
        base = dict(game_id=1, season=2025, season_type=2, date='2025-01-01T00:00Z',
                    home_abbreviation='BOS', away_abbreviation='NY', home_score=120, away_score=110,
                    neutral_site=False, time_valid=True, status_type_name='STATUS_FINAL', status_type_completed=True)
        rows = [base, dict(base, game_id=2, home_abbreviation='SHQ'),
                dict(base, game_id=3, notes_headline='NBA Cup Championship'),
                dict(base, game_id=4, status_type_name='STATUS_POSTPONED', status_type_completed=False)]
        result, excluded = normalize_sdv(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['away'], 'NYK')
        self.assertEqual(sum(excluded.values()), 3)

    def test_conflicts_unknown_venue_naive_times_and_tied_finals_fail(self):
        g = games()[0]
        self.assertEqual(len(validate_games([g, g])), 1)
        for modified in (dict(g, home_score=999),):
            with self.assertRaises(ValueError):
                validate_games([g, modified])
        for modified in (dict(g, neutral=None), dict(g, tipoff='2025-01-01'), dict(g, away_score=g['home_score'])):
            with self.assertRaises(ValueError):
                validate_games([modified])

    def test_only_allowlisted_fields_enter_snapshot_and_source_tampering_fails(self):
        g = dict(games()[0], odds=1.2, power_rating=999, home_winner=False)
        body = snapshot([g], [{'url': 'fixture'}])
        self.assertNotIn('odds', body['games'][0])
        self.assertFalse(body['freshness_verified'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'snapshot.json'
            write_new(path, body)
            self.assertEqual(load_snapshot(path)['sha256'], body['sha256'])
            with self.assertRaises(FileExistsError):
                write_new(path, body)
            body['games'][0]['home_score'] += 1
            path.write_text(json.dumps(body))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                load_snapshot(path)

    def test_weight_prior_equal_then_rewards_lower_oos_brier(self):
        w = weights([], CONFIG)
        self.assertEqual(set(w), set(NAMES))
        self.assertAlmostEqual(sum(w.values()), 1)
        prior = [{'actual': 1, 'probabilities': {n: .9 if n == 'elo' else .2 for n in NAMES}}] * 100
        self.assertGreater(weights(prior, CONFIG)['elo'], weights(prior, CONFIG)['logistic'])

    def test_disagreement_is_disclosed_and_probabilities_complement(self):
        p = dict(zip(NAMES, [.9, .8, .7, .2, .1, .3]))
        result = debate(games()[0], p, weights([], CONFIG), [10, 10], CONFIG)
        self.assertIn('large_model_disagreement', result['flags'])
        self.assertAlmostEqual(result['home_probability'] + result['away_probability'], 1)
        self.assertAlmostEqual(sum(v['contribution_to_home_probability'] for v in result['models'].values()), result['home_probability'])

    def test_holdout_is_locked_and_reports_are_json_safe(self):
        with self.assertRaisesRegex(ValueError, 'Holdout'):
            development_games({'games': [dict(games()[0], season=2026)]}, CONFIG)
        forecasts = [dict(actual=i % 2, probabilities={n: .6 for n in NAMES}, home_probability=.6,
                          equal_weight_home_probability=.6, home_frequency=.5, tipoff=f'2025-01-{i+1:02d}T00:00:00Z', flags=[])
                     for i in range(5)]
        value = report(forecasts, CONFIG)
        json.dumps(value, allow_nan=False)
        self.assertEqual(value['paired_comparisons']['elo']['ensemble_minus_baseline_brier'], 0)

    def test_all_six_algorithms_fit_and_produce_finite_complementary_forecasts(self):
        from threadpoolctl import threadpool_limits
        rng = np.random.default_rng(4)
        rows = []
        for _ in range(CONFIG['minimum_training_games']):
            x = rng.normal(size=len(FEATURES))
            margin = 4*x[0] + rng.normal(scale=12)
            rows.append(dict(x=x, y=int(margin > 0), margin=margin))
        with threadpool_limits(limits=1):
            trained = fit(rows, CONFIG)
            p = probabilities(trained, np.zeros(len(FEATURES)))
        self.assertEqual(set(p), set(NAMES))
        self.assertTrue(all(np.isfinite(v) and .01 <= v <= .99 for v in p.values()))

    def test_own_outcome_cannot_change_fitted_models_or_debate_weights(self):
        from threadpoolctl import threadpool_limits
        original = games(70)
        changed = copy.deepcopy(original)
        changed[-1]['home_score'], changed[-1]['away_score'] = 0, 210
        config = dict(CONFIG, minimum_training_games=30)
        with threadpool_limits(limits=1):
            first, _ = replay(original, config)
            second, _ = replay(changed, config)
        self.assertTrue(first)
        self.assertEqual(first[-1]['probabilities'], second[-1]['probabilities'])
        self.assertEqual(first[-1]['models'], second[-1]['models'])
        for row in first:
            self.assertLess(row['model_fitted_at'], row['tipoff'])
            self.assertLess(row['weight_training_games'], len(first))


if __name__ == '__main__':
    unittest.main()
