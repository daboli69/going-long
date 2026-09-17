import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from backtest_nfl_context import opponent_adjusted_projection, walk_forward


class OpponentAdjustmentTest(unittest.TestCase):
    def test_early_weeks_use_stronger_shrinkage(self):
        train=[]
        for week in range(1,4):
            train.append({'season':2026,'week':week,'home_team':'A','away_team':'B','home_score':35,'away_score':14,'kickoff_ts':week*1000,'game_id':f'a{week}'})
            train.append({'season':2026,'week':week,'home_team':'C','away_team':'D','home_score':21,'away_score':20,'kickoff_ts':week*1000+1,'game_id':f'c{week}'})
        game={'home_team':'A','away_team':'D'}
        early=opponent_adjusted_projection(train,game,2026,4)
        later=opponent_adjusted_projection(train,game,2026,5)
        self.assertEqual(early['prior_games'],6)
        self.assertEqual(later['prior_games'],3)
        self.assertGreater(abs(later['margin']),abs(early['margin']))

    def test_same_week_results_do_not_change_that_weeks_forecast(self):
        games=[]
        teams=['A','B','C','D','E','F','G','H']
        clock=1_700_000_000
        for week in range(1,19):
            for index in range(0,len(teams),2):
                games.append({'season':2025,'week':week,'home_team':teams[index],'away_team':teams[index+1],
                              'home_score':24+index,'away_score':20+index//2,'kickoff_ts':clock+week*604800,
                              'game_id':f'{week}-{index}'})
        original=walk_forward(games)
        changed=[dict(game) for game in games]
        changed[-1]['home_score']=70;changed[-1]['away_score']=0
        revised=walk_forward(changed)
        target=next(row for row in original['predictions'] if row['game_id']=='18-0')
        comparison=next(row for row in revised['predictions'] if row['game_id']=='18-0')
        self.assertEqual(target['opponent_projected_margin'],comparison['opponent_projected_margin'])
        self.assertEqual(target['training_cutoff'],comparison['training_cutoff'])


if __name__=='__main__':
    unittest.main()
