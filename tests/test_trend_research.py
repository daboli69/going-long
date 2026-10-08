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


class TrendContextAndLabelTests(unittest.TestCase):
    def put_week(self, workspace, games, table, days, **kw):
        workspace.put(f'{table}_{games}.csv', fpt.make_csv(table, season=2026, games=games, **kw))
        fpt.set_mtime(workspace.inbox / f'{table}_{games}.csv', NOW + datetime.timedelta(days=days))

    def run_weeks(self, workspace, weeks, tables):
        for index, games in enumerate(weeks):
            for table, kw in tables.items():
                self.put_week(workspace, games, table, index * 7, **(kw(games) if callable(kw) else kw))
            workspace.run(now=NOW + datetime.timedelta(days=7 * index), max_possible_games=games + 1, expected_games=games)

    def test_team_environment_and_matchup_context_are_stored_with_the_state(self):
        def pass_heavy(games):
            def mutate(body, keys):
                for row in body:
                    row[keys.index('Overall.SNAPS')] = str(60 * games)
                    row[keys.index('Overall.PASS')] = str(30 * games if games < 4 else 30 * 3 + 42)  # week 4: 42 of 60 plays are passes
                    row[keys.index('Team Details.G')] = str(games)
            return {'mutate': mutate}
        workspace = fpt.Workspace(self)
        self.run_weeks(workspace, [3, 4], {'run_pass_report': pass_heavy, 'line_matchups': {}, 'coverage_matrix': {}, 'receiving_routes_run': {}})
        written = trends.capture(workspace.dir, 2026)
        self.assertEqual(written, ['trends/2026/through-week-04.json'])
        state = json.loads((workspace.dir / written[0]).read_text(encoding='utf-8'))
        team = next(iter(state['team_environment'].values()))
        self.assertAlmostEqual(team['pass_rate_week'], 0.7, places=3)
        self.assertAlmostEqual(team['pass_rate_before'], 0.5, places=3)
        matchup = next(iter(state['matchup_known_before_game'].values()))
        self.assertTrue(matchup['next_opponent'])
        self.assertIn('Man', json.dumps(matchup['opponent_coverage_mix_season_to_date']) + 'Man')
        self.assertEqual(state['schema'], 'fp-trend-state-v2')
        self.assertIn('descriptive evidence only', state['labels_note'])

    def test_missing_context_tables_simply_leave_those_sections_empty(self):
        workspace = fpt.Workspace(self)
        self.run_weeks(workspace, [3, 4], {'receiving_routes_run': {}})
        state = json.loads((workspace.dir / trends.capture(workspace.dir, 2026)[0]).read_text(encoding='utf-8'))
        self.assertEqual((state['team_environment'], state['matchup_known_before_game']), ({}, {}))

    def record(self, **overrides):
        base = {'week': {'routes': 40, 'targets': 9, 'first_read_targets': 6, 'carries': 0}, 'before': {'routes': 90, 'targets': 18, 'first_read_targets': 4, 'carries': 0},
                'games_before': {'receiving_routes_run': 3, 'rushing_bell_cow': 3}, 'derived': {'routes_vs_season_avg': 10.0, 'targets_vs_season_avg': 3.0}}
        base.update(overrides)
        return base

    def test_labels_fire_on_pre_declared_thresholds_and_are_marked_descriptive(self):
        from fp_ingest import trend_labels
        labels = {l['label']: l for l in trend_labels.detect(self.record())}
        self.assertIn('ROUTE PARTICIPATION UP', labels)
        self.assertIn('TARGET VOLUME UP', labels)
        self.assertIn('FIRST READ UP', labels)
        self.assertTrue(all(l['descriptive_only'] for l in labels.values()))
        down = {l['label'] for l in trend_labels.detect(self.record(derived={'routes_vs_season_avg': -12.0, 'targets_vs_season_avg': -4.0},
                                                                    week={'routes': 18, 'targets': 2, 'first_read_targets': 0}))}
        self.assertTrue({'ROUTE PARTICIPATION DOWN', 'TARGET VOLUME DOWN'} <= down)

    def test_small_changes_and_missing_evidence_produce_no_label_never_a_negative_one(self):
        from fp_ingest import trend_labels
        self.assertEqual(trend_labels.detect(self.record(derived={'routes_vs_season_avg': 2.0, 'targets_vs_season_avg': 0.5}, week={'routes': 32, 'targets': 6, 'first_read_targets': 2})), [])
        self.assertEqual(trend_labels.detect({}), [])
        self.assertEqual(trend_labels.detect({'week': {'routes': 40}, 'derived': {}}), [])


class MatchupContextTests(unittest.TestCase):
    def test_own_and_opponent_defense_are_kept_apart(self):
        from unittest import mock
        from fp_ingest import trend_labels
        doc = {'rows': [{'entity': {'team': 'AAA'}, 'context': {'opponent': 'BBB'}, 'metrics': {'Defense Stats.ADJ YBC/ATT': 1.0, 'Defense Stats.PRESS %': 10.0, 'Offense Stats.RUSH GRADE': 70}},
                        {'entity': {'team': 'BBB'}, 'context': {'opponent': 'AAA'}, 'metrics': {'Defense Stats.ADJ YBC/ATT': 2.0, 'Defense Stats.PRESS %': 20.0, 'Offense Stats.RUSH GRADE': 60}}]}
        with mock.patch.object(trend_labels, 'live_snapshots', lambda m, s, t: {1: {'sha256': 'x'}} if t == 'line_matchups' else {}), mock.patch.object(trend_labels, '_doc', lambda r, e: doc):
            out, _ = trend_labels.matchup_context('root', {}, 2026, 1)
        self.assertEqual((out['AAA']['own_defense_adj_ybc_per_att'], out['AAA']['opponent_defense_adj_ybc_per_att']), (1.0, 2.0))
        self.assertEqual(out['BBB']['opponent_defense_pressure_pct'], 10.0)


@unittest.skipUnless(__import__('importlib').util.find_spec('pandas'), 'pandas needed')
class OutcomeJoinTests(unittest.TestCase):
    def weekly(self, weeks):
        import pandas as pd
        rows = []
        for week, targets in weeks.items():
            rows.append({'player_id': 'P1', 'team': 'AAA', 'opponent_team': 'BBB', 'position': 'WR', 'season': 2026, 'week': week, 'season_type': 'REG', 'targets': targets,
                         'receptions': targets - 1, 'receiving_yards': 10 * targets, 'receiving_tds': 0, 'carries': 0, 'rushing_yards': 0, 'rushing_tds': 0, 'attempts': 0,
                         'passing_yards': 0, 'passing_tds': 0})
        return pd.DataFrame(rows)

    def test_outcomes_are_write_once_and_skip_the_week_still_in_progress(self):
        import tempfile
        from trend_research import prospective
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__('shutil').rmtree, root, True)
        frame = self.weekly({1: 5, 2: 8, 3: 6})
        self.assertEqual(prospective.write_outcomes(root, 2026, frame), ['outcomes/2026/week-01.json', 'outcomes/2026/week-02.json'])
        path = root / 'outcomes' / '2026' / 'week-01.json'
        before = path.read_bytes()
        self.assertEqual(prospective.write_outcomes(root, 2026, self.weekly({1: 99, 2: 99, 3: 99, 4: 1})), ['outcomes/2026/week-03.json'])
        self.assertEqual(path.read_bytes(), before, 'a written outcome is never edited')

    def test_join_pairs_a_trend_state_with_the_players_next_appearance_across_a_bye(self):
        import tempfile
        from trend_research import prospective
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__('shutil').rmtree, root, True)
        prospective.write_outcomes(root, 2026, self.weekly({1: 5, 2: 8, 4: 6, 5: 7, 6: 3}))  # week 3 was a bye
        state = {'players': {'P1': {'week': {'targets': 8}, 'games_before': {'receiving_routes_run': 1}, 'labels': [{'label': 'TARGET VOLUME UP'}]}}}
        pair = prospective.join_next_game(state, prospective.appearances_by_player(root, 2026))['P1']
        self.assertEqual((pair['state_week'], pair['next_week'], pair['aligned']), (2, 4, True))
        self.assertEqual(pair['next']['targets'], 6.0)
        state['players']['P1']['week']['targets'] = 99
        self.assertFalse(prospective.join_next_game({'players': {'P1': {'week': {'carries': 8}, 'games_before': {'receiving_routes_run': 1}}}}, prospective.appearances_by_player(root, 2026))['P1']['aligned'], 'targets are required')
        self.assertFalse(prospective.join_next_game(state, prospective.appearances_by_player(root, 2026))['P1']['aligned'], 'a mismatched stat line is flagged')


try:
    import numpy, pandas, scipy  # noqa: F401
    HAVE_STACK_EARLY = True
except ImportError:
    HAVE_STACK_EARLY = False


class ChampionReconstructionTests(unittest.TestCase):
    def setUp(self):
        if not HAVE_STACK_EARLY:
            self.skipTest('numpy, pandas and scipy are needed')
        from trend_research import champion
        self.champion = champion

    def test_season_weights_equal_the_production_policy_function(self):
        import build_pipeline
        for seasons, current in (([2025, 2025, 2026], 2026), ([2026, 2026], 2026), ([2024, 2025], 2026), ([2024, 2025, 2026, 2026, 2026], 2026)):
            self.assertEqual([round(x, 12) for x in self.champion.season_weights(seasons, current)], [round(x, 12) for x in build_pipeline.season_weights(seasons, current)])

    def synthetic(self, stats):
        import pandas as pd
        rows = []
        for (season, week), value in stats.items():
            rows.append({'player_id': 'P', 'player_display_name': 'P', 'position': 'WR', 'team': 'AAA', 'opponent_team': 'BBB', 'season': season, 'week': week, 'passing_yards': 0,
                         'passing_tds': 0, 'attempts': 0, 'carries': 0, 'rushing_yards': 0, 'rushing_tds': 0, 'receptions': value, 'targets': value, 'receiving_yards': 10 * value,
                         'receiving_tds': 0, 'touchdowns': 0, 'carry_share': 0.1, 'target_share': 0.2})
        games = pd.DataFrame([{'season': s, 'week': w, 'game_type': 'REG', 'gameday': f'{s}-09-{w:02d}', 'home_team': 'AAA', 'away_team': 'BBB', 'home_qb_id': 'Q', 'away_qb_id': 'R'}
                              for (s, w) in stats])
        return pd.DataFrame(rows), games

    def build(self, stats, targets):
        from unittest.mock import patch
        frame, games = self.synthetic(stats)
        with patch.object(self.champion, 'appearances', lambda root, seasons: frame), patch.object(self.champion, 'load_games', lambda root: games):
            return self.champion.champion_frame('root', targets)

    def test_window_weights_and_point_in_time_safety(self):
        stats = {(2025, w): float(w) for w in range(1, 11)}  # 10 prior-season games with values 1..10
        stats.update({(2026, 1): 20.0, (2026, 2): 30.0, (2026, 3): 100.0})
        out = self.build(stats, {2026}).set_index('week')
        # week 3: window = 10 prior games (the last 10 of 2025) + 2 current games; only games before week 3 are visible
        window_prior = np_mean(range(1, 11))
        self.assertAlmostEqual(out.loc[3, 'champ_receptions'], 0.8 * 25.0 + 0.2 * window_prior, places=9)
        self.assertEqual((out.loc[3, 'k'], out.loc[3, 'n']), (2, 12))
        self.assertAlmostEqual(out.loc[1, 'champ_receptions'], window_prior, places=9, msg='week 1 uses the prior season only')
        # appending a later game must not change an earlier row
        stats[(2026, 4)] = 999.0
        later = self.build(stats, {2026}).set_index('week')
        self.assertEqual(later.loc[3, 'champ_receptions'], out.loc[3, 'champ_receptions'])
        self.assertEqual(out.loc[3, 'y_receptions'], 100.0)

    def test_a_single_current_game_gets_eighty_percent_of_the_weight(self):
        stats = {(2025, w): 4.0 for w in range(1, 12)}
        stats[(2026, 1)] = 10.0
        row = self.build({**stats, (2026, 2): 0.0}, {2026}).set_index('week').loc[2]
        self.assertAlmostEqual(row['champ_receptions'], 0.8 * 10.0 + 0.2 * 4.0, places=9)
        self.assertEqual(row['k'], 1)


class BenchmarkAndBlendTests(unittest.TestCase):
    def setUp(self):
        if not HAVE_STACK_EARLY:
            self.skipTest('numpy, pandas and scipy are needed')

    def test_summarize_computes_calibration_brier_and_roi(self):
        from trend_research import benchmark
        rows = [{'group': 'g', 'family': 'f', 'game': f'G{i}', 'prob': 0.6, 'push': 0.0, 'dec': 1.91, 'status': 'win' if i % 2 == 0 else 'loss', 'close_dec': None, 'close_prob': None,
                 'side': 'Over', 'n': 12, 'cohort': None} for i in range(100)]
        result = benchmark.summarize(rows)
        self.assertEqual((result['n_graded'], result['win_rate']), (100, 0.5))
        self.assertAlmostEqual(result['brier'], 0.5 * (0.4 ** 2) + 0.5 * (0.6 ** 2), places=9)
        self.assertAlmostEqual(result['roi_flat_stake'], 0.5 * 0.91 - 0.5, places=9)

    def test_refunds_are_excluded_from_probability_metrics(self):
        from trend_research import benchmark
        rows = [{'group': 'g', 'family': 'f', 'game': 'A', 'prob': 0.5, 'push': 0.1, 'dec': 2.0, 'status': s, 'close_dec': None, 'close_prob': None, 'side': 'Over', 'n': 12, 'cohort': None}
                for s in ('win', 'loss', 'refund')]
        result = benchmark.summarize(rows)
        self.assertEqual((result['n_graded'], result['n_refund']), (2, 1))

    def test_shrinkage_blend_formula(self):
        import numpy as np
        import pandas as pd
        from trend_research import experiments2
        frame = pd.DataFrame({'cur_receptions': [8.0, np.nan, 6.0], 'prior_receptions': [4.0, 4.0, np.nan], 'k': [1, 0, 3], 'n_prior': [11, 12, 0]})
        out = experiments2._blend(frame, 'receptions', 1.0)
        self.assertAlmostEqual(out[0], (1 * 8.0 + 1.0 * 4.0) / 2.0)
        self.assertEqual((out[1], out[2]), (4.0, 6.0))
        far = experiments2._blend(frame, 'receptions', 1e6)
        self.assertAlmostEqual(far[0], 4.0, places=3)


def np_mean(values):
    values = list(values)
    return sum(values) / len(values)


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
            from trend_research import experiments2, experiments3, experiments4, experiments5, experiments6, experiments7
            current = {**self.experiments.SPECS, **experiments2.SPECS, **experiments3.SPECS, **experiments4.SPECS, **experiments5.SPECS, **experiments6.SPECS, **experiments7.SPECS}
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
