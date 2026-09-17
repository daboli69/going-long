import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from king_endzone import probabilities, td_event, distance_mix


class KingTests(unittest.TestCase):
    def test_return_is_one_event_with_two_eligible_winners(self):
        p,no_td=probabilities([dict(rate=.2,dist={99:1},owners=['returner','dst'])])
        self.assertAlmostEqual(no_td,math.exp(-.2))
        self.assertAlmostEqual(p['returner'],1-no_td)
        self.assertEqual(p['returner'],p['dst'])

    def test_explosive_scorer_can_outrank_more_likely_goal_line_scorer(self):
        p,_=probabilities([dict(rate=1,dist={1:1},owners=['rb']),dict(rate=.5,dist={80:1},owners=['wr'])])
        self.assertGreater(p['wr'],p['rb'])
        self.assertAlmostEqual(p['wr'],1-math.exp(-.5))
        self.assertAlmostEqual(p['rb'],(1-math.exp(-1))*math.exp(-.5))

    def test_equal_distance_ties_both_win_and_no_td_is_preserved(self):
        p,none=probabilities([dict(rate=1,dist={10:1},owners=['a']),dict(rate=1,dist={10:1},owners=['b'])])
        self.assertAlmostEqual(p['a'],1-math.exp(-1))
        self.assertEqual(p['a'],p['b']);self.assertAlmostEqual(none,math.exp(-2))

    def test_passer_does_not_get_receiving_touchdown_and_no_plays_excluded(self):
        play=dict(touchdown=1,td_team='BUF',posteam='BUF',td_player_id='receiver',pass_touchdown=1,yards_gained=40,game_id='g',game_date='2026-09-17')
        event=td_event(play);self.assertEqual(event['player'],'receiver');self.assertEqual(event['distance'],40)
        self.assertIsNone(td_event(dict(play,play_type='no_play')))
        self.assertIsNone(td_event(dict(play,two_point_attempt=1)))
        returned=td_event(dict(play,kickoff_attempt=1,return_yards=101))
        self.assertEqual(returned['kind'],'return');self.assertEqual(returned['distance'],101)

    def test_distance_shrinkage_retains_long_tail_and_missing_is_not_fabricated(self):
        dist=distance_mix([90],[1,10,20]);self.assertAlmostEqual(sum(dist.values()),1)
        self.assertGreater(dist[90],0)
        with self.assertRaises(ValueError):distance_mix([],[])


if __name__=='__main__':unittest.main()
