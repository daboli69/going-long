import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from football_context import build_scope, coach_meetings, coverage_game_state


class FootballContextTests(unittest.TestCase):
    def test_proxy_benchmark_and_catch_gap_are_observed_not_routes(self):
        rows, charts, roster = [], [], []
        for j in range(10):
            roster.append({'gsis_id': str(j), 'position': 'WR', 'full_name': 'Player '+str(j)})
        for game in range(3):
            for i in range(40):
                gid='g'+str(game);ids=[str(j) for j in range(10) if j==0 or i<20]
                rows.append(dict(season=2026,season_type='REG',game_date='2026-09-'+str(1+game).zfill(2),game_id=gid,posteam='A',defteam='B',qtr=1,play_type='pass',play_id=i,wp=.5,qb_dropback=1,xpass=.5,drive=1,quarter_seconds_remaining=900-i*20,receiver_player_id='0',complete_pass=0,cp=.8,receiving_yards=0,air_yards=10))
                charts.append({'nflverse_game_id':gid,'play_id':i,'offense_players':';'.join(ids),'offense_personnel':'1 RB, 1 TE, 3 WR'})
        result=build_scope(rows,[],roster,charts,2026,'2026-09-10')
        p=result['players']['0']
        self.assertEqual(p['routes'],None)
        self.assertEqual(p['share_type'],'passing_snap_proxy')
        self.assertEqual(p['share'],1)
        self.assertAlmostEqual(p['shrunk_share'],.82)
        self.assertAlmostEqual(p['share_above_average'],.27)
        self.assertEqual(p['share_percentile'],1)
        self.assertEqual(p['role_signal']['status'],'role_ahead_of_results')
        self.assertEqual(p['role_signal']['prior_strength_pass_snaps'],80)
        # Untargeted players still have a known team from all-player participation.
        self.assertTrue(p['opportunity_flag'])
        self.assertFalse(result['players']['1']['opportunity_flag'])
        self.assertAlmostEqual(p['catches_short'],96)
        self.assertEqual(result['teams']['A']['personnel_11_share'],1)
        empty=build_scope(rows,[],roster,charts,2026,'2026-09-01')
        self.assertEqual(empty['players'],{})

    def test_coach_record_accounts_for_the_market_not_just_wins(self):
        games=[dict(game_type='REG',gameday='2025-10-01',home_coach='A',away_coach='B',home_score=20,away_score=17,spread_line=7) for _ in range(6)]
        result=coach_meetings(games,'2026-01-01')
        self.assertEqual(result['A|B']['wins'],6)
        self.assertEqual(result['A|B']['covers'],0)
        self.assertEqual(result['A|B']['average_vs_spread'],-4)
        self.assertTrue(result['A|B']['historically_behind'])
        self.assertFalse(result['B|A']['historically_behind'])

    def test_exact_coverage_is_conditioned_on_defensive_score_state(self):
        self.assertEqual(coverage_game_state(-3),'leading_1_7')
        rows,charts=[],[]
        roster=[{'gsis_id':'qb','position':'QB','full_name':'Quarterback'},
                {'gsis_id':'te','position':'TE','full_name':'Tight End'}]
        for game in range(3):
            for play in range(20):
                gid=f'g{game}'
                rows.append(dict(season=2025,season_type='REG',game_date=f'2025-09-{game+1:02d}',game_id=gid,
                                 posteam='A',defteam='B',qtr=1,play_type='pass',play_id=play,wp=.5,
                                 score_differential=-3,qb_dropback=1,xpass=.6,drive=1,
                                 quarter_seconds_remaining=900-play*20,passer_player_id='qb',receiver_player_id='te',
                                 complete_pass=1,cp=.7,receiving_yards=8,air_yards=6))
                charts.append({'nflverse_game_id':gid,'play_id':play,'defense_coverage_type':'COVER_3'})
        result=build_scope(rows,[],roster,charts,2025,'2026-01-01',max_games=None)
        state=result['defense_coverage_game_states']['B']['leading_1_7']
        self.assertEqual(state['dropbacks'],60)
        self.assertEqual(state['dominant_shell'],'COVER_3')
        self.assertEqual(state['status'],'observed')
        split=result['qb_coverage']['qb']['COVER_3']
        self.assertEqual(split['status'],'observed')
        self.assertEqual(split['target_rate_by_position']['TE'],1)
        allowed=result['defense_coverage_receiving']['B|COVER_3|TE']
        self.assertEqual(allowed['status'],'observed')
