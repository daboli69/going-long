import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from season_learning import completeness, dynamic_blend, classify_status, build_matchups, carryover_validation


class SeasonLearningTests(unittest.TestCase):
    def test_completeness_compares_schedule_to_persisted_results(self):
        games = [
            dict(id='1', sport='nfl', home='A', away='B', kickoff='2026-09-01T00:00:00+00:00', completed=True),
            dict(id='2', sport='nfl', home='C', away='D', kickoff='2026-09-02T00:00:00+00:00', completed=True),
            dict(id='3', sport='nfl', home='E', away='F', kickoff='2026-10-02T00:00:00+00:00', completed=False),
        ]
        results = {'generated_at': '2026-09-03T00:00:00+00:00', 'games': {'nfl|1': dict(id='1', sport='nfl', homeScore=20, awayScore=17)}}
        audit = completeness(games, results, [dict(id='1', sport='nfl', model={'x': 1})], 'nfl', datetime(2026, 9, 10, tzinfo=timezone.utc), {'1'})
        self.assertEqual(audit['expected_completed'], 2)
        self.assertEqual(audit['actually_ingested'], 1)
        self.assertEqual(audit['missing_game_ids'], ['2'])
        self.assertEqual(audit['status'], 'PARTIAL')
        self.assertTrue(audit['trace'][-1]['features_built'])

    def test_dynamic_current_weight_rises_with_evidence_and_never_erases_history(self):
        early = dynamic_blend(1.0, -1.0, 80, 10, .5)
        late = dynamic_blend(1.0, -1.0, 80, 100, .5)
        changed = dynamic_blend(1.0, -1.0, 80, 10, .5, structural_decay=.55)
        self.assertLess(early['current_weight'], late['current_weight'])
        self.assertGreater(changed['current_weight'], early['current_weight'])
        self.assertGreaterEqual(late['historical_weight'], .10)

    def test_single_game_cannot_change_status(self):
        hist = {'targets': 100, 'games': 17, 'adjusted_extra_yards_per_target': 1.0}
        cur = {'targets': 40, 'games': 1, 'adjusted_extra_yards_per_target': -4.0, 'residual': -160, 'residual_sq': 800}
        status, confidence = classify_status(hist, cur, {'estimate': -.5}, 'targets', 'adjusted_extra_yards_per_target')
        self.assertEqual((status, confidence), ('uncertain', 'low'))

    def test_carryover_validation_is_role_specific_and_excludes_current_season(self):
        scopes = {}
        for year in (2023, 2024, 2025, 2026):
            rows = {}
            for i in range(8):
                rows[f'T{i}|WR'] = {'adjusted': i + year/1000}
                rows[f'T{i}|TE'] = {'adjusted': 50-i}
            scopes[str(year)] = {'defense_receiving': rows}
        result = carryover_validation(scopes, 'defense_receiving', 'adjusted', 'WR', 2025)
        self.assertEqual([(p['train_season'], p['test_season']) for p in result['pairs']], [(2023, 2024), (2024, 2025)])
        self.assertTrue(all(p['roles'] == 8 for p in result['pairs']))

    def test_matchup_requires_real_usage_and_supported_role(self):
        context = {'season': 2026, 'as_of': '2026-09-19T00:00:00Z', 'games': [{'id': 'g', 'away': 'A', 'home': 'B', 'kickoff': '2026-09-20T00:00:00Z'}], 'scopes': {'2026': {'players': {
            'used': {'player_id': 'used', 'name': 'Used TE', 'team': 'A', 'position': 'TE', 'games': 2, 'targets': 5, 'target_share': .2, 'share': .7, 'share_type': 'offensive_snap_share'},
            'unused': {'player_id': 'unused', 'name': 'Unused TE', 'team': 'A', 'position': 'TE', 'games': 2, 'targets': 1, 'target_share': .02, 'share': .3, 'share_type': 'offensive_snap_share'},
        }}}}
        weakness = [{'id': 'B|TE_RECEIVING', 'defense': 'B', 'historical_weakness': 'TE_RECEIVING', 'current_status': 'persisting', 'confidence': 'medium'}]
        rows = build_matchups(context, weakness)
        self.assertEqual([r['player_id'] for r in rows], ['used'])
        self.assertTrue(rows[0]['active_signal'])


if __name__ == '__main__':
    unittest.main()
