import importlib.util
import json
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_pipeline as bp  # noqa: E402
import champion_policy as cp  # noqa: E402

POLICY = {'version': 'champion-v2', 'active': True, 'markets': {
    'receptions': {'mean': {'method': 'prior_strength_blend', 'c': 2}, 'shape': {'family': 'nbinom', 'phi': 0.2}},
    'rec_yds': {'mean': {'method': 'prior_strength_blend', 'c': 1}, 'shape': {'family': 'pooled_lognormal', 'zero_shrink_games': 10, 'cv': {'WR': 0.7, 'TE': 0.7, 'RB': 0.9}, 'zero_rate': {'WR': 0.28, 'TE': 0.37, 'RB': 0.4}}},
    'rec_tds': {'mean': {'method': 'prior_strength_blend', 'c': 4}}}}


def games(prior, current, column):
    return [{'season': 2025, 'week': i + 1, column: v} for i, v in enumerate(prior)] + [{'season': 2026, 'week': i + 1, column: v} for i, v in enumerate(current)]


class PolicyFileTests(unittest.TestCase):
    def write(self, policy):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(policy, handle)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_inactive_missing_or_v1_environment_means_v1(self):
        self.assertIsNone(cp.load(self.write({**POLICY, 'active': False})))
        self.assertIsNone(cp.load('/no/such/file.json'))
        self.assertIsNotNone(cp.load(self.write(POLICY)))
        with mock.patch.dict(os.environ, {'GOING_CHAMPION_POLICY': 'v1'}):
            self.assertIsNone(cp.load(self.write(POLICY)))

    def test_committed_policy_lists_only_markets_that_passed_the_gates(self):
        committed = json.loads(cp.POLICY_PATH.read_text(encoding='utf-8'))
        self.assertNotIn('rush_yds', committed['markets'])
        for market, spec in committed['markets'].items():
            self.assertEqual(spec['mean']['method'], 'prior_strength_blend')
            self.assertGreater(spec['mean']['c'], 0)
        self.assertTrue(committed['rollback'])


class StrictLoadingAndGatingTests(PolicyFileTests):
    def test_a_broken_file_raises_instead_of_silently_disabling_and_only_true_activates(self):
        with self.assertRaises(ValueError):
            cp.load(self.write({**POLICY, 'markets': {'receptions': {'mean': {'c': -1}}}}))
        bad = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        bad.write('{not json')
        bad.close()
        self.addCleanup(os.unlink, bad.name)
        with self.assertRaises(ValueError):
            cp.load(bad.name)
        self.assertIsNone(cp.load(self.write({**POLICY, 'active': 'false'})))
        self.assertIsNone(cp.load(self.write({**POLICY, 'active': 1})))

    def test_positions_outside_the_validated_cells_keep_v1(self):
        gated = {**POLICY, 'markets': {**POLICY['markets'], 'receptions': {**POLICY['markets']['receptions'], 'positions': ['WR', 'TE', 'RB']}}}
        self.assertIsNotNone(cp.market_policy(gated, 'receptions', 'WR'))
        self.assertIsNone(cp.market_policy(gated, 'receptions', 'QB'))
        self.assertIsNone(cp.market_policy(gated, 'receptions', 'FB'))
        self.assertIsNotNone(cp.market_policy(gated, 'rec_tds', 'QB'), 'a market without a positions list applies to every position')

    def test_v1_output_carries_no_policy_key_and_v2_output_does(self):
        rows = games([4, 5, 3, 6, 2, 5, 4, 3, 7, 4, 5], [9], 'receptions')
        gated = {**POLICY, 'markets': {**POLICY['markets'], 'receptions': {**POLICY['markets']['receptions'], 'positions': ['WR']}}}
        with mock.patch.object(cp, 'load', lambda path=None: gated):
            self.assertNotIn('policy', bp.season_fit(rows, 'receptions', 'poisson', 2026, 5, market='receptions', position='QB'))
            self.assertEqual(bp.season_fit(rows, 'receptions', 'poisson', 2026, 5, market='receptions', position='WR')['policy'], 'champion-v2')
        self.assertNotIn('policy', bp.season_fit(rows, 'receptions', 'poisson', 2026, 5))


class BlendTests(unittest.TestCase):
    def test_blend_weights_reproduce_the_prior_strength_formula(self):
        rng = random.Random(7)
        for _ in range(200):
            n_prior, k = rng.randint(1, 11), rng.randint(1, 11)
            c = rng.choice([0.5, 1, 2, 3, 4])
            values = [rng.uniform(0, 100) for _ in range(n_prior + k)]
            years = [2025] * n_prior + [2026] * k
            w = cp.blend_weights(years, 2026, c)
            self.assertAlmostEqual(sum(w), 1.0, places=12)
            cur, prior = sum(values[n_prior:]) / k, sum(values[:n_prior]) / n_prior
            self.assertAlmostEqual(sum(a * b for a, b in zip(w, values)), (k * cur + c * prior) / (k + c), places=9)

    def test_single_source_windows_use_equal_weights(self):
        self.assertEqual(cp.blend_weights([2026, 2026], 2026, 2), [0.5, 0.5])
        self.assertEqual(cp.blend_weights([2025, 2025, 2025, 2025], 2026, 2), [0.25] * 4)
        self.assertEqual(cp.blend_weights([], 2026, 2), [])

    def test_week_one_uses_only_the_prior_season_and_one_game_is_not_given_eighty_percent(self):
        w = cp.blend_weights([2025] * 11 + [2026], 2026, 2)
        self.assertAlmostEqual(w[-1], 1 / 3)
        legacy = cp.legacy_weights([2025] * 11 + [2026], 2026)
        self.assertAlmostEqual(legacy[-1], 0.8)


class PooledShapeTests(unittest.TestCase):
    shape = POLICY['markets']['rec_yds']['shape']

    def test_pooled_lognormal_has_the_requested_mean_and_zero_mass(self):
        f = cp.pooled_lognormal(48.0, 12, 0.25, 'WR', self.shape)
        p0 = f['nonpositive_weights'][0]
        self.assertAlmostEqual(p0, (12 * 0.25 + 10 * 0.28) / 22, places=12)
        positive_mean = math.exp(f['mu_log'] + f['sigma_log'] ** 2 / 2)
        self.assertAlmostEqual((1 - p0) * positive_mean, 48.0, places=9)
        self.assertAlmostEqual(f['sigma_log'], math.sqrt(math.log1p(0.7 ** 2)), places=12)
        self.assertEqual(f['nonpositive'], [0])
        second_moment = (1 - p0) * (positive_mean ** 2 * (1 + 0.7 ** 2))
        self.assertAlmostEqual(f['sd'] ** 2, second_moment - 48.0 ** 2, places=6)

    def test_uncovered_position_or_nonpositive_mean_is_not_modelled(self):
        self.assertIsNone(cp.pooled_lognormal(48.0, 12, 0.25, 'FB', self.shape))
        self.assertIsNone(cp.pooled_lognormal(0.0, 12, 0.25, 'WR', self.shape))

    def test_zero_mass_is_clipped(self):
        self.assertAlmostEqual(cp.pooled_lognormal(10.0, 12, 1.0, 'RB', {**self.shape, 'zero_rate': {'RB': 1.0}})['nonpositive_weights'][0], 0.99)


class SeasonFitIntegrationTests(unittest.TestCase):
    def fit(self, rows, column, family, market, position, policy):
        with mock.patch.object(cp, 'load', lambda path=None: policy):
            return bp.season_fit(rows, column, family, 2026, 5, market=market, position=position)

    def test_inactive_policy_is_byte_for_byte_the_previous_model(self):
        rows = games([4, 5, 3, 6, 2, 5, 4, 3, 7, 4, 5], [9], 'receptions')
        old = bp.season_fit(rows, 'receptions', 'poisson', 2026, 5)
        new = self.fit(rows, 'receptions', 'poisson', 'receptions', 'WR', None)
        new.pop('calibration', None)  # the probability-calibration layer is separate data (config/calibration_policy.json), not part of the Champion policy
        self.assertEqual(old, new)

    def test_unlisted_market_is_unchanged_even_when_the_policy_is_active(self):
        rows = games([40, 55, 0, 80, 20, 65, 44, 31, 97, 54, 15], [120], 'rushing_yards')
        old = bp.season_fit(rows, 'rushing_yards', 'lognormal', 2026, 5)
        new = self.fit(rows, 'rushing_yards', 'lognormal', 'rush_yds', 'RB', POLICY)
        self.assertEqual(old, new)

    def test_receptions_v2_blends_the_mean_and_adds_dispersion(self):
        rows = games([4, 5, 3, 6, 2, 5, 4, 3, 7, 4, 5], [9], 'receptions')
        model = self.fit(rows, 'receptions', 'poisson', 'receptions', 'WR', POLICY)
        prior_mean, cur = sum(r['receptions'] for r in rows[:-1]) / 11, 9.0
        self.assertAlmostEqual(model['mean'], (1 * cur + 2 * prior_mean) / 3, places=9)
        self.assertAlmostEqual(model['lambda'], model['mean'])
        self.assertEqual(model['dispersion_phi'], 0.2)
        self.assertAlmostEqual(model['sd'], math.sqrt(model['mean'] + 0.2 * model['mean'] ** 2))
        self.assertEqual(model['policy'], 'champion-v2')
        self.assertIn('champion-v2', model['season_evidence']['method'])
        self.assertAlmostEqual(model['season_evidence']['current_weight'], 1 / 3)

    def test_td_market_gets_the_blend_without_a_new_shape(self):
        rows = games([0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0], [2, 1], 'receiving_tds')
        model = self.fit(rows, 'receiving_tds', 'poisson', 'rec_tds', 'WR', POLICY)
        self.assertNotIn('dispersion_phi', model)
        self.assertAlmostEqual(model.get('mean_raw', model['mean']), (2 * 1.5 + 4 * (3 / 11)) / 6, places=9)  # blend; calibration policy may then scale the mean

    def test_yardage_v2_uses_the_pooled_spread_and_the_legacy_window_for_zero_mass(self):
        prior = [40, 55, 0, 80, 20, 65, 44, 31, 97, 54, 15]
        rows = games(prior, [120], 'receiving_yards')
        model = self.fit(rows, 'receiving_yards', 'lognormal', 'rec_yds', 'WR', POLICY)
        legacy = cp.legacy_weights([2025] * 11 + [2026], 2026)
        nonpositive = sum(w for r, w in zip(rows, legacy) if r['receiving_yards'] <= 0)
        expected_p0 = (12 * nonpositive + 10 * 0.28) / 22
        self.assertAlmostEqual(model['nonpositive_weights'][0], expected_p0, places=12)
        self.assertAlmostEqual(model['positive_weight'], 1 - expected_p0, places=12)
        self.assertAlmostEqual(model['mean'], (120 + 1 * (sum(prior) / 11)) / 2, places=9)
        self.assertEqual(model['policy'], 'champion-v2')

    def test_a_player_the_pooled_parameters_do_not_cover_falls_back_to_v1_entirely(self):
        rows = games([40, 55, 0, 80, 20, 65, 44, 31, 97, 54, 15], [120], 'receiving_yards')
        old = bp.season_fit(rows, 'receiving_yards', 'lognormal', 2026, 5)
        new = self.fit(rows, 'receiving_yards', 'lognormal', 'rec_yds', 'FB', POLICY)
        self.assertNotIn('policy', new)
        self.assertEqual(old['mean'], new['mean'])

    def test_too_few_games_stays_insufficient_under_v2(self):
        rows = games([3, 4], [5], 'receptions')
        self.assertEqual(self.fit(rows, 'receptions', 'poisson', 'receptions', 'WR', POLICY)['status'], 'insufficient')


@unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('scipy'), 'numpy/scipy needed')
class ResearchEquivalenceTests(unittest.TestCase):
    """The research code evaluates vectorised versions of these formulas; production must give the same numbers."""

    def test_pooled_parameters_match_the_vectorised_research_formula(self):
        import numpy as np
        from trend_research import experiments7 as e7
        rng = random.Random(3)
        shape = POLICY['markets']['rec_yds']['shape']
        for _ in range(100):
            mean, n, window_zero = rng.uniform(5, 90), rng.randint(5, 12), rng.uniform(0, 0.6)
            f = cp.pooled_lognormal(mean, n, window_zero, 'WR', shape)
            p0 = float(np.clip((n * window_zero + 10 * 0.28) / (n + 10), 0.001, 0.99))
            pm = mean / (1 - p0)
            mu, sg = e7._ln_params(pm, pm * 0.7)
            self.assertAlmostEqual(f['mu_log'], float(mu), places=10)
            self.assertAlmostEqual(f['sigma_log'], float(sg), places=10)
            self.assertAlmostEqual(f['nonpositive_weights'][0], p0, places=12)

    def test_blend_matches_the_research_blend(self):
        import numpy as np
        import pandas as pd
        from trend_research.experiments2 import _blend
        rng = random.Random(5)
        for _ in range(50):
            n_prior, k, c = rng.randint(1, 11), rng.randint(1, 11), rng.choice([1, 2, 3, 4])
            values = [rng.uniform(0, 60) for _ in range(n_prior + k)]
            frame = pd.DataFrame({'cur_x': [np.mean(values[n_prior:])], 'prior_x': [np.mean(values[:n_prior])], 'k': [k]})
            w = cp.blend_weights([2025] * n_prior + [2026] * k, 2026, c)
            self.assertAlmostEqual(float(_blend(frame, 'x', c)[0]), sum(a * b for a, b in zip(w, values)), places=9)


if __name__ == '__main__':
    unittest.main()


class RoleTrendTests(unittest.TestCase):
    def test_role_trend_is_descriptive_and_flags_expansion_and_contraction(self):
        games_list = [{'season': 2026, 'week': w, 'team': 'AAA', 'targets': t, 'carries': 0} for w, t in enumerate([2, 2, 3, 6, 7, 8], 1)]
        team_week = {(2026, w, 'AAA'): {'targets': 30.0, 'carries': 25.0} for w in range(1, 7)}
        snaps = {('p', 2026, w): s for w, s in enumerate([.5, .5, .55, .8, .85, .9], 1)}
        up = bp.role_trend('p', games_list, snaps, team_week)
        self.assertEqual(up['flags'], ['ROLE UP'])
        self.assertAlmostEqual(up['target_share']['l1'], 8 / 30)
        self.assertAlmostEqual(up['snap_share']['l6'], sum([.5, .5, .55, .8, .85, .9]) / 6 * 100)
        down = bp.role_trend('p', list(reversed(games_list)) and [dict(g, targets=t) for g, t in zip(games_list, [8, 7, 6, 3, 2, 2])], {k: v for k, v in zip(snaps, [.9, .85, .8, .55, .5, .5])}, team_week)
        self.assertEqual(down['flags'], ['ROLE DOWN'])
        self.assertIsNone(bp.role_trend('p', games_list[:2], snaps, team_week), 'fewer than three games gives no trend')
        flat = bp.role_trend('p', [dict(g, targets=5) for g in games_list], {k: .7 for k in snaps}, team_week)
        self.assertEqual(flat['flags'], [])


class CalibrationAttachmentTests(unittest.TestCase):
    def test_only_validated_markets_and_positions_carry_calibration(self):
        for market, pos, expected in [('receptions', 'WR', True), ('receptions', 'TE', True), ('receptions', 'RB', True), ('receptions', 'QB', False),
                                      ('pass_yds', 'QB', True), ('pass_yds', 'WR', False), ('rec_yds', 'WR', False), ('rush_yds', 'RB', False), ('atd', 'WR', True), ('atd', 'QB', False), ('rush_tds', 'RB', True), ('rec_tds', 'TE', True), ('pass_tds', 'QB', False)]:
            cal = bp._calibration_for(market, pos)
            self.assertEqual(cal is not None, expected, (market, pos))
            if cal:
                self.assertEqual(cal['version'], 'cal-b-2026.10.09-v3')


    def test_td_mean_scale_changes_lambda_and_keeps_raw(self):
        games = [{'season': 2025, 'touchdowns': t} for t in (1, 0, 1, 0, 1, 0, 0, 1)] + [{'season': 2026, 'touchdowns': t} for t in (1, 0, 1)]
        scaled = bp.season_fit(games, 'touchdowns', 'poisson', 2026, market='atd', position='WR')
        factor = bp._calibration_for('atd', 'WR')['params']['factor']
        self.assertAlmostEqual(scaled['lambda'], scaled['lambda_raw'] * factor, places=9)
        self.assertAlmostEqual(scaled['mean'], scaled['mean_raw'] * factor, places=9)
        self.assertNotIn('lambda_raw', bp.season_fit(games, 'touchdowns', 'poisson', 2026, market='atd', position='QB'))


    def test_pass_yds_lognormal_refit_uses_equal_weight_mean_and_keeps_raw(self):
        games = [{'season': 2025, 'passing_yards': y} for y in (250, 280, 310, 190, 260, 300)] + [{'season': 2026, 'passing_yards': y} for y in (220, 240, 330)]
        m = bp.season_fit(games, 'passing_yards', 'lognormal', 2026, market='pass_yds', position='QB')
        self.assertEqual(m['calibration']['method'], 'lognormal_refit')
        self.assertAlmostEqual(m['mean_raw'] > 0 and m['mean'] > 0, True)
        self.assertLess(abs(m['mean'] - sum(g['passing_yards'] for g in games) / len(games)) / 270, 0.1)  # compressed toward the league mean, near the equal-weight mean
        self.assertIn('sigma_log_raw', m)
        self.assertIsNone(bp.lognormal_refit({'positive_weight': 1, 'sigma_log': .3}, 10, m['calibration']['params']))
