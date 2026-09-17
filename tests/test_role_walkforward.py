import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from backtest_nfl_context import walk_forward_roles


def fixture(include_future=False):
    rows=[];charts=[];roster=[{'gsis_id':str(i),'position':'WR','full_name':'Player '+str(i)} for i in range(10)]
    for week in range(1,6 if include_future else 5):
        for play in range(60):
            gid=f'g{week}';history=week<4;target='0' if history or play<10 else None
            rows.append({'season':2025,'season_type':'REG','week':week,'game_date':f'2025-09-{week:02d}','game_id':gid,
                         'posteam':'A','defteam':'B','qtr':1,'play_type':'pass','play_id':play,'wp':.5,'qb_dropback':1,
                         'xpass':.6,'drive':1,'quarter_seconds_remaining':900-play*10,'receiver_player_id':target,
                         'complete_pass':0 if history else int(play<5),'cp':.8 if target else None,
                         'receiving_yards':0 if history else (20 if play<5 else 0),'air_yards':10 if target else None})
            ids=['0']+[str(i) for i in range(1,10) if play<30]
            charts.append({'nflverse_game_id':gid,'play_id':play,'offense_players':';'.join(ids),'offense_personnel':'1 RB, 1 TE, 3 WR'})
    return rows,[],roster,charts


class RoleWalkForwardTests(unittest.TestCase):
    def test_weekly_signal_uses_only_earlier_games(self):
        result=walk_forward_roles(*fixture(),2025)
        week4=next(r for r in result['records'] if r['week']==4 and r['player_id']=='0')
        self.assertEqual(week4['cutoff'],'2025-09-04')
        self.assertEqual(week4['status'],'role_ahead_of_results')
        self.assertEqual(week4['actual_yards'],100)
        self.assertFalse(result['promotion_eligible'])
        role=next(g for g in result['groups'] if g['name']=='role_ahead_of_results')
        self.assertEqual(role['yards_difference_from_all_range_95'],[role['mean_yards_difference_from_all']]*2)
        poisoned=walk_forward_roles(*fixture(include_future=True),2025)
        same=next(r for r in poisoned['records'] if r['week']==4 and r['player_id']=='0')
        self.assertEqual(week4,same)
        week5=next(r for r in poisoned['records'] if r['week']==5 and r['player_id']=='0')
        self.assertGreater(week5['role_adjustment'],0)
        self.assertAlmostEqual(week5['adjusted_yards'],week5['baseline_yards']+week5['role_adjustment'])
        self.assertEqual(result['decision'],'experimental_only')
        self.assertEqual(result['projection_adjustment_decision'],'do_not_promote')


if __name__=='__main__':unittest.main()
