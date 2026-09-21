import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from injury_context import body_group, build_current, build_effects, status_group


class InjuryContextTests(unittest.TestCase):
    def test_played_through_effect_uses_only_prior_healthy_active_weeks(self):
        roster = [{'pfr_id': 'TestPl00', 'gsis_id': 'p'}]
        snaps = [dict(season=2025, week=week, game_type='REG', pfr_player_id='TestPl00', offense_pct=.8)
                 for week in range(1, 5)]
        weekly = [dict(season=2025, week=week, season_type='REG', player_id='p', position='WR',
                       receiving_yards=100 if week < 4 else 50, receptions=6, targets=8,
                       rushing_yards=0, carries=0) for week in range(1, 5)]
        injuries = [dict(season=2025, week=4, season_type='REG', gsis_id='p', position='WR',
                         report_primary_injury='Hip', report_status='Questionable', practice_status='Limited Participation in Practice')]
        effects, validation = build_effects(injuries, weekly, snaps, roster)
        effect = effects['WR|hip|questionable|rec_yds']
        self.assertEqual(effect['sample'], 1)
        self.assertEqual(effect['raw_median_ratio'], .5)
        self.assertEqual(effect['scale'], .65)
        self.assertGreater(validation['played_through_market_observations'], 0)

    def test_current_qb_and_defense_blitz_splits_are_observed_not_inferred(self):
        roster = [
            dict(season=2026, week=1, game_type='REG', gsis_id='qb', full_name='QB One', team='A', position='QB', status='ACT'),
            dict(season=2026, week=1, game_type='REG', gsis_id='wr', full_name='Wide One', team='A', position='WR', status='ACT'),
        ]
        depth = [
            dict(dt='2026-09-20T12:00:00Z', gsis_id='qb', team='A', player_name='QB One', pos_abb='QB', pos_rank=1),
            dict(dt='2026-09-20T12:00:00Z', gsis_id='wr', team='A', player_name='Wide One', pos_name='Wide Receiver', pos_rank=1),
        ]
        pbp = [dict(game_id='g', play_id=1, play_type='pass', qb_spike=0, posteam='A', defteam='B', passer_player_id='qb', receiver_player_id='wr')]
        ftn = [dict(nflverse_game_id='g', nflverse_play_id=1, n_blitzers=1)]
        players, reports, qb, defense, meta = build_current(2026, [], depth, roster, {'scopes': {'2026': {'players': {}}}}, pbp, ftn)
        self.assertEqual(qb['A']['blitz_splits']['blitz']['dropbacks'], 1)
        self.assertEqual(qb['A']['target_rate_by_position']['WR'], 1)
        self.assertFalse(qb['A']['supported_for_model'])
        self.assertEqual(defense['B']['blitz_rate'], 1)
        self.assertFalse(defense['B']['supported_for_model'])
        self.assertEqual(reports, {})
        self.assertEqual(meta['current_players'], 2)

    def test_injury_taxonomy_rejects_rest_and_keeps_real_body_parts(self):
        self.assertEqual(body_group('Hip'), 'hip')
        self.assertIsNone(body_group('Not injury related - resting player'))
        self.assertEqual(status_group({'report_status': 'Questionable'}), 'questionable')
        self.assertIsNone(status_group({'report_status': 'Out'}))


if __name__ == '__main__':
    unittest.main()
