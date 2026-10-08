import datetime
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
import test_fantasy_points_ingest as fpt  # noqa: E402
from fp_ingest import store, trends  # noqa: E402
from fp_ingest.parse import sha256  # noqa: E402

TEAMS = fpt.TEAMS
NOW = fpt.NOW


def routes_csv(games, per_game_routes, per_game_targets, skip_first=False):
    """receiving_routes_run for one season-to-date snapshot: row 0 of each team gets the given weekly rates; the first row can be 'inactive'."""
    def mutate(body, keys):
        for i, row in enumerate(body):
            weeks = games - (1 if (skip_first and i == 0 and games == 4) else 0)
            row[keys.index('Overall.RTE')] = str(per_game_routes * weeks)
            row[keys.index('Overall.TGT')] = str(per_game_targets * weeks)
            row[keys.index('Player Details.G')] = str(weeks)
    return fpt.make_csv('receiving_routes_run', season=2026, games=games, mutate=mutate)


class TrendCaptureTests(unittest.TestCase):
    def snapshots(self, workspace, weeks, **kw):
        for index, games in enumerate(weeks):
            workspace.put(f'w{games}.csv', routes_csv(games, 30, 4, **kw))
            fpt.set_mtime(workspace.inbox / f'w{games}.csv', NOW + datetime.timedelta(days=7 * index))
            workspace.run(now=NOW + datetime.timedelta(days=7 * index), max_possible_games=games + 1, expected_games=games)

    def test_week_usage_is_the_difference_of_two_consecutive_snapshots(self):
        workspace = fpt.Workspace(self)
        self.snapshots(workspace, [3, 4])
        written = trends.capture(workspace.dir, 2026)
        self.assertEqual(written, ['trends/2026/through-week-04.json'])
        state = json.loads((workspace.dir / written[0]).read_text(encoding='utf-8'))
        self.assertEqual((state['through_games'], state['prev_through_games']), (4, 3))
        player = next(iter(state['players'].values()))
        self.assertEqual((player['week']['routes'], player['week']['targets']), (30, 4))
        self.assertAlmostEqual(player['derived']['tprr_week'], 4 / 30, places=3)
        self.assertEqual(player['derived']['routes_vs_season_avg'], 0.0)
        manifest = workspace.manifest()
        later = max(e['first_imported_at'] for e in manifest.files.values())
        self.assertEqual(state['known_at'], later, 'a trend state is known only once the later snapshot was imported')

    def test_one_snapshot_or_a_gap_produces_no_trend(self):
        single = fpt.Workspace(self)
        self.snapshots(single, [4])
        self.assertEqual(trends.capture(single.dir, 2026), [])
        gap = fpt.Workspace(self)
        self.snapshots(gap, [2, 4])
        self.assertEqual(trends.capture(gap.dir, 2026), [], 'weeks 2 and 4 are not consecutive: the week-3 usage cannot be reconstructed')

    def test_states_are_write_once_and_later_weeks_never_touch_earlier_ones(self):
        workspace = fpt.Workspace(self)
        self.snapshots(workspace, [2, 3])
        first = trends.capture(workspace.dir, 2026)
        path = workspace.dir / first[0]
        before = path.read_bytes()
        workspace.put('w4.csv', routes_csv(4, 12, 1))
        fpt.set_mtime(workspace.inbox / 'w4.csv', NOW + datetime.timedelta(days=30))
        workspace.run(now=NOW + datetime.timedelta(days=30), max_possible_games=5, expected_games=4)
        second = trends.capture(workspace.dir, 2026)
        self.assertEqual(second, ['trends/2026/through-week-04.json'])
        self.assertEqual(path.read_bytes(), before, 'week 3 state must not change when week 4 arrives')
        self.assertEqual(trends.capture(workspace.dir, 2026), [], 'rerun writes nothing')

    def test_a_corrected_snapshot_makes_a_revision_file_never_an_edit(self):
        workspace = fpt.Workspace(self)
        self.snapshots(workspace, [3, 4])
        original = trends.capture(workspace.dir, 2026)[0]
        before = (workspace.dir / original).read_bytes()
        workspace.put('fix.csv', routes_csv(4, 31, 4))
        fpt.set_mtime(workspace.inbox / 'fix.csv', NOW + datetime.timedelta(days=20))
        workspace.run(now=NOW + datetime.timedelta(days=20), max_possible_games=5, expected_games=4)
        revised = trends.capture(workspace.dir, 2026)
        self.assertEqual(len(revised), 1)
        self.assertIn('__revision-', revised[0])
        self.assertEqual((workspace.dir / original).read_bytes(), before)

    def test_known_at_includes_a_corrected_earlier_snapshot(self):
        workspace = fpt.Workspace(self)
        self.snapshots(workspace, [3, 4])
        trends.capture(workspace.dir, 2026)
        workspace.put('fix3.csv', routes_csv(3, 29, 4))
        late = NOW + datetime.timedelta(days=40)
        fpt.set_mtime(workspace.inbox / 'fix3.csv', late)
        workspace.run(now=late, max_possible_games=5, expected_games=4)
        revised = [n for n in trends.capture(workspace.dir, 2026) if '__revision-' in n]
        self.assertTrue(revised)
        state = json.loads((workspace.dir / revised[0]).read_text(encoding='utf-8'))
        self.assertEqual(state['known_at'], late.strftime('%Y-%m-%dT%H:%M:%SZ'), 'the revised state was not knowable before the corrected week-3 file arrived')

    def test_players_who_did_not_play_have_no_weekly_usage(self):
        workspace = fpt.Workspace(self)
        for games, skip in ((3, False), (4, True)):
            workspace.put(f'w{games}.csv', routes_csv(games, 30, 4, skip_first=skip))
            fpt.set_mtime(workspace.inbox / f'w{games}.csv', NOW + datetime.timedelta(days=games))
        workspace.run(max_possible_games=5, expected_games=4)
        state = json.loads((workspace.dir / trends.capture(workspace.dir, 2026)[0]).read_text(encoding='utf-8'))
        inactive = [p for p in state['players'].values() if p.get('did_not_play')]
        self.assertTrue(inactive and all('week' not in p for p in inactive))


try:  # the research stack is not part of the production requirements; those tests run wherever numpy/pandas/scipy exist
    import numpy, pandas, scipy  # noqa: F401
    HAVE_STACK = True
except ImportError:
    HAVE_STACK = False


@unittest.skipUnless(HAVE_STACK, 'numpy, pandas and scipy are needed for the research tooling tests')
class ResearchToolingTests(unittest.TestCase):
    def setUp(self):
        from trend_research import data, experiments, ledger, stats
        self.data, self.experiments, self.ledger, self.stats = data, experiments, ledger, stats

    def test_features_cannot_come_from_the_season_being_predicted(self):
        with self.assertRaises(self.data.LeakageError):
            self.data.assert_no_same_season(2024, 2024)
        with self.assertRaises(self.data.LeakageError):
            self.data.assert_no_same_season(2025, 2024)
        self.data.assert_no_same_season(2023, 2024)

    def test_prior_features_read_only_the_previous_season(self):
        asked = []

        def spy(root, manifest, season, table):
            asked.append(season)
            return None
        with patch.object(self.data, 'snapshot_frame', spy):
            self.data.prior_features('r', None, 2025, 'receiving_advanced')
        self.assertEqual(asked, [2024])

    def test_a_changed_spec_cannot_replace_its_preregistration(self):
        book = self.ledger.load(Path('does-not-exist.json'))
        spec = {'id': 'X1', 'hypothesis': 'a'}
        self.ledger.register(book, spec)
        self.ledger.register(book, dict(spec))  # identical: fine
        with self.assertRaises(ValueError):
            self.ledger.register(book, {'id': 'X1', 'hypothesis': 'changed after seeing the result'})
        with self.assertRaises(ValueError):
            self.ledger.record(book, 'X1', {'id': 'X1', 'hypothesis': 'changed'}, {}, 'PROMISING')
        self.ledger.record(book, 'X1', spec, {'ok': True}, 'REJECTED')
        self.assertEqual(book['experiments']['X1']['status'], 'REJECTED')

    def test_committed_ledger_matches_its_specs_and_contains_no_player_level_values(self):
        book = json.loads((ROOT / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
        for exp_id, entry in book['experiments'].items():
            self.assertEqual(entry['spec_sha256'], self.ledger.spec_hash(entry['spec']), exp_id)
            from trend_research import experiments2, experiments3
            current = {**self.experiments.SPECS, **experiments2.SPECS, **experiments3.SPECS}
            self.assertEqual(entry['spec_sha256'], self.ledger.spec_hash(current[exp_id]), f'{exp_id}: spec edited after registration')
            self.assertNotIn('player_id', json.dumps(entry['result']), 'aggregate results only')

    def test_ridge_recovers_a_known_relationship_and_bootstrap_detects_a_real_gain(self):
        import numpy as np
        rng = np.random.default_rng(1)
        X = rng.normal(size=(400, 2))
        y = 3 * X[:, 0] + 0.5 * X[:, 1] + rng.normal(scale=.3, size=400)
        model = self.stats.Ridge().fit(X[:300], y[:300])
        self.assertLess(self.stats.mae(y[300:], model.predict(X[300:])), 0.6)
        base = y[300:] - X[300:, 0] * 3.0 * 0.0  # a useless predictor
        new = y[300:] - model.predict(X[300:])
        result = self.stats.paired_bootstrap(base, new, np.arange(100))
        self.assertLess(result['ci_high'], 0)

    def test_the_decision_rule_is_applied_mechanically(self):
        rule = {'min_relative_improvement': 0.01, 'min_years_better': 2, 'reject_below_relative_improvement': 0.0025}
        good = {'delta_mae': -0.05, 'ci_low': -0.08, 'ci_high': -0.02}
        self.assertEqual(self.stats.verdict(good, 1.0, 3, 3, rule)[0], 'PROMISING')
        self.assertEqual(self.stats.verdict(good, 1.0, 1, 3, rule)[0], 'INCONCLUSIVE', 'needs 2 of 3 seasons')
        self.assertEqual(self.stats.verdict({'delta_mae': -0.05, 'ci_low': -0.08, 'ci_high': 0.01}, 1.0, 3, 3, rule)[0], 'INCONCLUSIVE')
        self.assertEqual(self.stats.verdict({'delta_mae': 0.02, 'ci_low': 0.01, 'ci_high': 0.03}, 1.0, 0, 3, rule)[0], 'REJECTED')

    def test_the_v2_rejection_rule_needs_the_interval_to_exclude_a_worthwhile_gain(self):
        rule = {'min_relative_improvement': 0.01, 'min_years_better': 2, 'reject_below_relative_improvement': 0.0025, 'reject_requires_ci': True}
        wide = {'delta_mae': 0.02, 'ci_low': -0.20, 'ci_high': 0.24}
        self.assertEqual(self.stats.verdict(wide, 3.0, 0, 3, rule)[0], 'INCONCLUSIVE', 'wide interval: a 6% gain is still plausible')
        tight = {'delta_mae': 0.02, 'ci_low': -0.01, 'ci_high': 0.05}
        self.assertEqual(self.stats.verdict(tight, 3.0, 0, 3, rule)[0], 'REJECTED')
        v1 = dict(rule, reject_requires_ci=False)
        self.assertEqual(self.stats.verdict(wide, 3.0, 0, 3, v1)[0], 'REJECTED', 'the first-wave v1 rule is unchanged')

    def test_sensitivity_is_recorded_beside_the_registered_results(self):
        book = json.loads((ROOT / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
        self.assertIn('E2_fp_per_game', book['sensitivity'])
        self.assertEqual(book['experiments']['E2']['status'], 'INCONCLUSIVE', 'sensitivity never edits a registered verdict')

    def test_exploratory_experiments_cannot_report_promising(self):
        with patch.object(self.experiments, 'run_e1', lambda root, manifest, exp_id='E1': ({}, 'PROMISING')):
            self.assertEqual(self.experiments.run_e6(None, None)[1], 'NEEDS PROSPECTIVE DATA')


if __name__ == '__main__':
    unittest.main()
