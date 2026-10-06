import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from opportunity_evidence import build_opportunity_evidence, situational_usage

G1, G2, OPEN = '2026_01_NO_ATL', '2026_02_NO_ATL', '2026_03_NO_ATL'


def play(gid, kind, pid, yardline, down=1, **extra):
    row = dict(season=2026, season_type='REG', game_id=gid, posteam='NO', play_id=len(extra) + yardline * 7 + (down or 0),
               yardline_100=yardline, down=down)
    row.update(play_type='pass', receiver_player_id=pid) if kind == 'target' else row.update(play_type='run', rush_attempt=1, rusher_player_id=pid)
    row.update(extra)
    return row


def ends(*gids):
    return [dict(season=2026, season_type='REG', game_id=g, play_type='game_end', game_seconds_remaining=0) for g in gids]


class SituationalUsageTests(unittest.TestCase):
    positions = {'rb': 'RB', 'wr': 'WR', 'k': 'K'}

    def test_thresholds_and_team_shares(self):
        rows = [play(G1, 'carry', 'rb', 20), play(G1, 'carry', 'rb', 21), play(G1, 'carry', 'rb', 10, down=3),
                play(G1, 'carry', 'rb', 5), play(G1, 'target', 'wr', 4), play(G1, 'target', 'wr', 50, down=3), *ends(G1)]
        usage, complete = situational_usage(2026, rows, self.positions)
        rb, wr = usage['NO|rb'], usage['NO|wr']
        self.assertEqual(complete, 1)
        self.assertEqual((rb['red_zone']['carries'], rb['inside_10']['carries'], rb['inside_5']['carries'], rb['third_down']['carries']), (3, 2, 1, 1))
        self.assertEqual((wr['red_zone']['targets'], wr['inside_5']['targets'], wr['third_down']['targets']), (1, 1, 1))
        self.assertEqual(rb['red_zone']['team_carries'], 3)
        self.assertEqual(rb['red_zone']['carry_share'], 1.0)
        self.assertEqual(wr['red_zone']['target_share'], 1.0)
        self.assertEqual(rb['red_zone']['target_share'], 0.0)  # team threw there; this player was not targeted

    def test_excluded_plays_incomplete_games_and_non_skill_positions(self):
        rows = [play(G1, 'carry', 'rb', 4, two_point_attempt=1), play(G1, 'carry', 'rb', 4, qb_kneel=1),
                play(G1, 'target', 'wr', 4, play_deleted=1), play(G1, 'carry', 'rb', 3, play_id=999),
                play(OPEN, 'carry', 'rb', 3), play(G1, 'carry', 'k', 3), *ends(G1)]
        usage, _ = situational_usage(2026, rows, self.positions)
        self.assertEqual(usage['NO|rb']['inside_5']['carries'], 1)
        self.assertNotIn('NO|wr', usage)
        self.assertNotIn('NO|k', usage)

    def test_other_seasons_and_postseason_are_ignored(self):
        rows = [dict(play(G1, 'carry', 'rb', 3), season=2025), dict(play(G1, 'carry', 'rb', 3), season_type='POST'), *ends(G1)]
        self.assertEqual(situational_usage(2026, rows, self.positions)[0], {})


class RobustnessTests(unittest.TestCase):
    positions = {'rb': 'RB'}

    def test_regulation_end_marker_without_a_schedule_final_is_not_complete(self):
        rows = [play(G1, 'carry', 'rb', 3), play(G2, 'carry', 'rb', 3), *ends(G1, G2)]
        usage, complete = situational_usage(2026, rows, self.positions, final_game_ids={G1})
        self.assertEqual(complete, 1)
        self.assertEqual(usage['NO|rb']['inside_5']['carries'], 1)
        self.assertEqual(situational_usage(2026, rows, self.positions, final_game_ids=set())[0], {})

    def test_float_nan_season_and_week_do_not_crash(self):
        rows = [dict(play(G1, 'carry', 'rb', 3), season=float('nan')), play(G1, 'carry', 'rb', 3), *ends(G1)]
        self.assertEqual(situational_usage(2026, rows, self.positions)[0]['NO|rb']['inside_5']['carries'], 1)
        expected = dict(season=2026.0, week=float('nan'), game_id=G1, player_id='rb', posteam='NO', total_fantasy_points_exp=5.0, total_fantasy_points=6.0)
        roster = [dict(season=2026, gsis_id='rb', position='RB', full_name='Back')]
        e = build_opportunity_evidence(season=2026, pbp_rows=ends(G1), expected_rows=[expected], roster_rows=roster, generated_at='2026-10-06T00:00:00+00:00')
        self.assertEqual(e['expected_vs_actual']['NO|rb']['games'], 1)

    def test_real_ffopportunity_parquet_types_season_text_week_float(self):
        expected = dict(season='2026', week=1.0, game_id=G1, player_id='rb', posteam='NO', total_fantasy_points_exp=5.0, total_fantasy_points=6.0,
                        rec_attempt=2.0, rush_attempt=10.0)
        roster = [dict(season=2026, gsis_id='rb', position='RB', full_name='Back')]
        e = build_opportunity_evidence(season=2026, pbp_rows=ends(G1), expected_rows=[expected], roster_rows=roster, generated_at='2026-10-06T00:00:00+00:00')
        row = e['expected_vs_actual']['NO|rb']
        self.assertEqual((row['games'], row['weeks']), (1, [1]))
        self.assertEqual(e['provenance']['expected_points']['latest_week'], 1)

    def test_traded_player_keeps_separate_team_keys(self):
        rows = [play(G1, 'carry', 'rb', 3), dict(play(G2, 'carry', 'rb', 3), posteam='KC'), *ends(G1, G2)]
        usage, _ = situational_usage(2026, rows, self.positions)
        self.assertEqual(sorted(usage), ['KC|rb', 'NO|rb'])
        self.assertEqual(usage['NO|rb']['games'], 1)


class ExpectedVsActualTests(unittest.TestCase):
    roster = [dict(season=2026, gsis_id='rb', position='RB', full_name='Back'), dict(season=2026, gsis_id='wr', position='WR', full_name='Wide')]

    def expected(self, game=G1, pid='rb', exp=10.0, act=4.0, **extra):
        row = dict(season=2026, week=1, game_id=game, player_id=pid, posteam='NO', position='RB',
                   total_fantasy_points_exp=exp, total_fantasy_points=act, rec_attempt=2, rush_attempt=12,
                   rec_yards_gained_exp=12.0, rec_yards_gained=8.0, rec_touchdown_exp=.2, rec_touchdown=0,
                   rush_yards_gained_exp=50.0, rush_yards_gained=40.0, rush_touchdown_exp=.5, rush_touchdown=0,
                   receptions_exp=1.5, receptions=1)
        row.update(extra)
        return row

    def build(self, expected, pbp=None, **kw):
        return build_opportunity_evidence(season=2026, pbp_rows=pbp if pbp is not None else ends(G1, G2), expected_rows=expected,
                                          roster_rows=self.roster, generated_at='2026-10-06T00:00:00+00:00', **kw)

    def test_sums_deltas_and_only_completed_games(self):
        e = self.build([self.expected(), self.expected(game=G2, exp=6.0, act=9.0, week=2), self.expected(game=OPEN, exp=50, act=0, week=3)])
        row = e['expected_vs_actual']['NO|rb']
        self.assertEqual(row['games'], 2)
        self.assertEqual(row['totals']['fantasy_points'], {'expected': 16.0, 'actual': 13.0, 'delta': -3.0})
        self.assertEqual(row['name'], 'Back')
        self.assertEqual(row['weeks'], [1, 2])
        self.assertEqual(e['provenance']['expected_points']['latest_week'], 3)

    def test_missing_component_is_unknown_not_zero_and_bad_rows_are_dropped(self):
        e = self.build([self.expected(rush_touchdown_exp=None), self.expected(pid='wr', exp=float('nan'))])
        totals = e['expected_vs_actual']['NO|rb']['totals']
        self.assertNotIn('rush_tds', totals)
        self.assertIn('rec_yards', totals)
        self.assertNotIn('NO|wr', e['expected_vs_actual'])

    def test_unavailable_sources_publish_no_evidence(self):
        e = self.build([], source_meta={'expected_points': {'status': 'unavailable'}})
        self.assertEqual(e['expected_vs_actual'], {})
        self.assertEqual(e['provenance']['expected_points']['status'], 'unavailable')
        e = self.build([self.expected()], pbp=[], source_meta={'pbp': {'status': 'unavailable'}})
        self.assertEqual((e['situational_usage'], e['expected_vs_actual']), ({}, {}))
        self.assertIn('descriptive process evidence', ' '.join(e['limitations']))


if __name__ == '__main__':
    unittest.main()
