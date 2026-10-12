import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from king_endzone import probabilities, td_event, distance_mix, monday_games, current_games, matchup_evidence, build_slate
from unittest.mock import patch
from datetime import datetime, timezone


class KingTests(unittest.TestCase):
    def test_monday_rollover_preserves_started_early_game(self):
        rows=[dict(game_id='2026_05_A_B',gameday='2026-10-12',gametime='19:00',home_team='A',away_team='B'),
              dict(game_id='2026_05_C_D',gameday='2026-10-12',gametime='22:00',home_team='C',away_team='D'),
              dict(game_id='2026_06_E_F',gameday='2026-10-19',gametime='20:15',home_team='E',away_team='F')]
        self.assertEqual(len(monday_games(rows,datetime.fromisoformat('2026-10-13T00:00:00+00:00'))),2)
        self.assertEqual(monday_games(rows,datetime.fromisoformat('2026-10-13T09:00:00+00:00'))[0]['date'],'2026-10-19')
        self.assertEqual(monday_games([],datetime.now(timezone.utc)),[])

    def test_prior_season_and_same_day_rows_cannot_enter_player_rate(self):
        p={'games':[{'season':2025,'date':'2026-01-04','rec_tds':100},
                    {'season':2026,'date':'2026-10-04','rec_tds':1},
                    {'season':2026,'date':'2026-10-12','rec_tds':999}]}
        self.assertEqual(current_games(p,2026,'2026-10-12'),[p['games'][1]])

    def test_matchup_context_requires_fresh_clock_and_current_scope(self):
        c={'team':'A','position':'WR'};games=[{'home':'A','away':'B'}]
        old={'generated_at':'2026-10-01T00:00:00Z','scopes':{'2026':{}}}
        self.assertIn('stale',matchup_evidence(c,games,old,2026,'2026-10-12T00:00:00+00:00')[0])
        ctx={'generated_at':'2026-10-12T00:00:00Z','sources':{'pbp_2026':{'status':'loaded'}},'scopes':{'2026':{'defense_receiving':{'B|WR':{'games':4,'targets':50,'explosive_rate':.2}}}}}
        lines=matchup_evidence(c,games,ctx,2026,'2026-10-12T01:00:00+00:00')
        self.assertIn('20.0%',lines[0]);self.assertIn('unavailable',' '.join(lines));self.assertIn('does not alter',' '.join(lines))

    def test_current_season_probability_ignores_old_profile_means_and_scoring(self):
        games=[dict(id='2026_05_A_B',home='A',away='B',date='2026-10-12',kickoff='2026-10-13T00:15:00Z')]
        roster=[dict(gsis_id='p',team='A',status='ACT',position='WR',full_name='Player')]
        base=dict(game_id='2026_01_A_B',game_date='2026-09-10',home_team='A',away_team='B',posteam='A',td_team='A',touchdown=1,td_player_id='p',yards_gained=30,pass_touchdown=1)
        rows=[base,dict(base,td_player_id='r',pass_touchdown=0,yards_gained=2)]
        profile={'p':{'games':[dict(season=2026,date='2026-09-10',rec_tds=1,rush_tds=0)]}}
        with patch('eligibility.freshness',return_value={'ok':True}),patch('eligibility.blocked_ids',return_value=set()):
            a=build_slate(games,profile,roster,rows,'2026-10-11T20:00:00+00:00')
            profile['p']['stats']={'rec_tds':{'mean':999,'status':'ready'}}
            profile['p']['games'].append(dict(season=2025,date='2026-01-04',rec_tds=999,rush_tds=999))
            b=build_slate(games,profile,roster,rows+[dict(base,game_id='2025_01_A_B',game_date='2025-09-10',yards_gained=99)],'2026-10-11T20:00:00+00:00')
        self.assertEqual(a['candidates'],b['candidates'])
        candidate=next(c for c in a['candidates'] if c['id']=='p');self.assertEqual(candidate['position'],'WR')

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
