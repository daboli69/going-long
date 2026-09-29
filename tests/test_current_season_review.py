import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_pipeline import fit_stat, season_fit, build_profiles, build_game_models
from current_season_review import evaluate, results_review
from injury_context import build_current


class CurrentSeasonTests(unittest.TestCase):
    def test_requested_eighty_twenty_policy(self):
        games=[{'season':2025,'yards':10}]*9+[{'season':2026,'yards':50}]*3
        baseline=season_fit(games,'yards','lognormal',2026)
        candidate=season_fit(games,'yards','lognormal',2026,candidate=True)
        self.assertAlmostEqual(baseline['mean'],42)
        self.assertAlmostEqual(candidate['season_evidence']['current_weight'],.6)
        self.assertAlmostEqual(baseline['season_evidence']['current_weight'],.8)
        self.assertEqual(baseline['season_evidence']['sample_confidence'],'low')

    def test_missing_season_is_explicit_fallback_not_fabricated(self):
        for years,status,weight in [([2025]*6,'historical_fallback',0),([2026]*6,'current_only',1)]:
            fit=season_fit([{'season':y,'yards':10} for y in years],'yards','lognormal',2026)
            self.assertEqual(fit['season_evidence']['evidence_status'],status)
            self.assertAlmostEqual(fit['season_evidence']['current_weight'],weight)
        self.assertEqual(season_fit([{'season':2027,'yards':999}],'yards','lognormal',2026)['n'],0)

    def test_weighted_zero_mass_is_normalized(self):
        model=fit_stat([-1,0,10,20],'lognormal',weights=[1,1,3,3])
        self.assertEqual(model['positive_weight'],.75)
        self.assertAlmostEqual(sum(model['nonpositive_weights'])+model['positive_weight'],1)

    def test_game_line_blends_seasons_before_target_kickoff(self):
        games=[dict(id=f'{year}-{day}',season=year,home='A',away='B',kickoff=f'{year}-09-{day:02}T17:00:00Z',
            completed=True,homeScore=30 if year==2026 else 10,awayScore=5 if year==2026 else 0)
            for year,count in [(2025,5),(2026,3)] for day in range(1,count+1)]
        games.append(dict(id='next',season=2026,home='A',away='B',kickoff='2026-09-08T17:00:00Z',completed=False))
        model=build_game_models(games)[0][0]['model']
        self.assertAlmostEqual(model['total_mean'],30)
        self.assertAlmostEqual(model['margin_mean'],22)
        self.assertAlmostEqual(model['season_evidence']['home_current_weight'],.8)

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
