import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_pipeline import fit_stat, season_fit, build_profiles
from current_season_review import evaluate, results_review
from injury_context import build_current


class CurrentSeasonTests(unittest.TestCase):
    def test_candidate_is_not_silently_promoted(self):
        games=[{'season':2025,'yards':10}]*9+[{'season':2026,'yards':50}]*3
        baseline=season_fit(games,'yards','lognormal',2026)
        candidate=season_fit(games,'yards','lognormal',2026,candidate=True)
        self.assertEqual(baseline['mean'],20)
        self.assertAlmostEqual(candidate['season_evidence']['current_weight'],.6)
        self.assertEqual(baseline['season_evidence']['current_weight'],.25)

    def test_weighted_zero_mass_is_normalized(self):
        model=fit_stat([-1,0,10,20],'lognormal',weights=[1,1,3,3])
        self.assertEqual(model['positive_weight'],.75)
        self.assertAlmostEqual(sum(model['nonpositive_weights'])+model['positive_weight'],1)

    def test_qb_relief_is_not_a_start(self):
        roster=[{'gsis_id':'q','full_name':'Backup QB','position':'QB','team':'A'}]
        rows=[dict(player_id='q',season=2026,week=w,team='A',position='QB',season_type='REG',passing_yards=200 if w==3 else 5) for w in (1,2,3)]
        schedule=[dict(season=2026,week=w,home_team='A',away_team='B',home_qb_id='q' if w==3 else 'other',gameday=f'2026-09-{w:02}') for w in (1,2,3)]
        p=build_profiles(rows,roster,[],schedule)['q']
        self.assertEqual(p['stats']['pass_yds']['n'],1)
        self.assertEqual(p['stats']['pass_yds']['status'],'insufficient')
        self.assertEqual(p['stats']['pass_yds']['mean'],200)

    def test_depth_replacement_not_season_volume_and_unknown_chart_not_nonblitz(self):
        roster=[dict(gsis_id=p,full_name=p,team='A',position='QB',week=4,game_type='REG',status='ACT') for p in ('old','new')]
        depth=[dict(gsis_id=p,dt='2026-09-29',pos_rank=rank) for p,rank in [('old',2),('new',1)]]
        pbp=[dict(passer_player_id=p,posteam='A',defteam='B',play_type='pass',game_id='g',play_id=i) for i,p in enumerate(['old']*80+['new']*5)]
        _,_,qb,_,_=build_current(2026,[],depth,roster,{},pbp,[])
        self.assertEqual(qb['A']['qb_id'],'new')
        self.assertEqual(qb['A']['dropbacks'],5)
        self.assertFalse(qb['A']['supported_for_model'])
        self.assertEqual(qb['A']['blitz_splits']['non_blitz']['dropbacks'],0)
        self.assertEqual(qb['A']['profiles_by_id']['old']['dropbacks'],80)

    def test_results_deduplicate_exact_contracts(self):
        p=dict(sport='nfl',canonical_contract='x',market='pass_yds',event='g',probability=.8,model_evidence={'push':0})
        records=[{'kind':'prediction','payload':dict(p,id=i,observed_at=i)} for i in ('a','b')]
        records += [{'kind':'settlement','payload':{'prediction_id':i,'method':'published_full_game_result','status':'win'}} for i in ('a','b')]
        self.assertEqual(results_review({'records':records})['pass_yds']['contracts'],1)


if __name__=='__main__':unittest.main()
