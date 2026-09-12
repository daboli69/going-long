import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from football_context import build_scope, coach_meetings


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
        # Untargeted players still have a known team from all-player participation.
        self.assertTrue(p['opportunity_flag'])
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
