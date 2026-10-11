"""Offline challenger contracts. Synthetic examples are not accuracy evidence."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1] / 'research/model-confidence'


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G, P, T = load('game_challenger'), load('props_challenger'), load('td_volume')


class GameChallengerTests(unittest.TestCase):
    def games(self):
        return [dict(id=str(i),season=2025,week=i+1,kickoff=100000+i*86400,home='A',away='B',home_score=30,away_score=20,neutral=False) for i in range(3)]

    def test_centered_ridge_unequal_counts_satisfies_constrained_gradient(self):
        sums, counts = {'A':40,'B':-12,'C':7}, {'A':2,'B':9,'C':4}
        fitted = G.centered_ridge(sums,counts)
        self.assertAlmostEqual(sum(fitted.values()),0)
        gradients = [(counts[t]+G.ALPHA)*fitted[t]-sums[t] for t in sums]
        self.assertAlmostEqual(gradients[0],gradients[1])
        self.assertAlmostEqual(gradients[1],gradients[2])

    def test_current_season_only_and_late_score_exclusion(self):
        games=self.games();cutoff=games[-1]['kickoff']+43201
        reference=G.fit(games,2025,cutoff)
        contaminated=games+[dict(games[0],season=2024,home_score=1000),dict(games[-1],kickoff=cutoff-10,home_score=2000)]
        self.assertEqual(reference,G.fit(contaminated,2025,cutoff))
        self.assertLess(reference['latest'],cutoff)

    def test_minimum_three_games_and_margin_direction(self):
        games=self.games();cutoff=games[-1]['kickoff']+43201
        self.assertIsNone(G.forecast(G.fit(games[:2],2025,cutoff),games[-1]))
        result=G.forecast(G.fit(games,2025,cutoff),games[-1])
        self.assertGreater(result['margin'],0)
        self.assertAlmostEqual(result['baseline_total'],50)
        self.assertAlmostEqual(result['baseline_margin'],10)

    def test_neutral_venue_and_sparse_team(self):
        games=[dict(g,neutral=True) for g in self.games()]
        model=G.fit(games,2025,400000)
        self.assertEqual(model['home_adv'],0)
        self.assertIsNone(G.forecast(model,dict(games[0],away='UNKNOWN')))

    def test_invalid_score_rejected(self):
        with self.assertRaises(ValueError):
            G.fit([dict(self.games()[0],home_score=float('nan'))],2025,400000)

    def test_weekly_cutoff_no_later_game_features(self):
        games=self.games()+[dict(self.games()[-1],id='future',week=4,kickoff=400000)]
        replay=G.replay(games)
        self.assertTrue(replay)
        self.assertTrue(all(r['latest_training_score']<r['cutoff'] for r in replay))


class OpportunityPropsTests(unittest.TestCase):
    def rows(self):
        return [dict(player_id='p',team='A',game_id='g'+str(i),position='WR',season=2025,game_type='REG',completed=True,participated=True,
                     kickoff=f'2025-09-{i*7+1:02}T13:00:00Z',available_at=f'2025-09-{i*7+2:02}T13:00:00Z',targets=8,receptions=5,rec_yds=70,carries=1,rush_yds=5) for i in range(3)]

    def prior(self,market='rec_yds'):
        return P.fit_prior(self.rows(),market=market,position='WR',trained_through='2025-10-01T00:00:00Z',demand_prior_games=2,efficiency_prior_opportunities=20)

    def predict(self,rows=None,prior=None,**kwargs):
        args=dict(player_id='p',team='A',position='WR',season=2025,market='rec_yds',decision_at='2025-10-05T00:00:00Z',roster_at='2025-10-04T12:00:00Z',roster_verified=True,prior=prior or self.prior())
        args.update(kwargs)
        return P.predict(self.rows() if rows is None else rows,**args)

    def test_demand_catch_rate_yards_decomposition(self):
        result=self.predict()
        self.assertEqual(result['status'],'experimental')
        self.assertAlmostEqual(result['mean'],70)
        self.assertAlmostEqual(result['demand'],8)
        self.assertEqual(result['current_games'],3)
        self.assertNotIn('probability',result)

    def test_missing_identity_never_inferred(self):
        rows=self.rows();del rows[0]['player_id']
        self.assertEqual(self.predict(rows)['status'],'withheld')

    def test_duplicates_and_impossible_counts_withheld(self):
        rows=self.rows()
        for bad in [rows+[rows[0]], [dict(rows[0],receptions=10)]+rows[1:], [dict(rows[0],targets=-1)]+rows[1:], [dict(rows[0],participated=False)]+rows[1:]]:
            self.assertEqual(self.predict(bad)['status'],'withheld')

    def test_prior_season_and_future_receipts_do_not_add_support(self):
        rows=self.rows();old=[dict(r,season=2024) for r in rows]
        future=[dict(r,available_at='2025-12-01T00:00:00Z') for r in rows]
        self.assertEqual(self.predict(old+future)['status'],'withheld')

    def test_team_change_no_reuse_previous_stint(self):
        rows=self.rows();rows[1]['team']='B'
        self.assertEqual(self.predict(rows)['status'],'withheld')

    def test_roster_staleness_and_unknown_block(self):
        for kwargs in [dict(roster_verified=False),dict(roster_at='2025-10-01T00:00:00Z'),dict(roster_at='2025-10-06T00:00:00Z')]:
            self.assertEqual(self.predict(**kwargs)['status'],'withheld')

    def test_prior_market_and_cutoff_must_match(self):
        for prior in [dict(self.prior(),market='pass_yds'),dict(self.prior(),trained_through='2025-12-01T00:00:00Z')]:
            self.assertEqual(self.predict(prior=prior)['status'],'withheld')

    def test_training_artifact_required(self):
        self.assertEqual(self.predict(prior={'schema':'wrong'})['status'],'withheld')

    def test_negative_yardage_is_real_but_no_touch_yardage_not_supported(self):
        rows=[dict(r,rec_yds=-3) for r in self.rows()]
        prior=P.fit_prior(rows,market='rec_yds',position='WR',trained_through='2025-10-01T00:00:00Z',demand_prior_games=2,efficiency_prior_opportunities=20)
        self.assertEqual(self.predict(rows,prior)['status'],'experimental')
        self.assertEqual(self.predict([dict(self.rows()[0],targets=0,receptions=0)]+self.rows()[1:])['status'],'withheld')

    def test_qb_requires_verified_starts(self):
        rows=[dict(r,position='QB',attempts=30,pass_yds=250,verified_start=False) for r in self.rows()]
        with self.assertRaises(ValueError):
            P.fit_prior(rows,market='pass_yds',position='QB',trained_through='2025-10-01T00:00:00Z',demand_prior_games=2,efficiency_prior_opportunities=20)


class TdVolumeTests(unittest.TestCase):
    def test_probability_matches_poisson_and_no_sixty_percent_cutoff(self):
        import math
        p=T.opportunity_probability(20,10,{'carry':.05,'target':.1})
        self.assertAlmostEqual(p,1-math.exp(-2))
        self.assertGreater(p,.6)

    def test_invalid_opportunities_and_conversion_rates(self):
        for carries, rates in [(-1,{'carry':.1,'target':.1}),(10,{'carry':2,'target':.1}),(float('nan'),{'carry':.1,'target':.1})]:
            with self.assertRaises(ValueError):
                T.opportunity_probability(carries,2,rates)

    def test_current_season_strict_prior_week_and_team_stint(self):
        rows=[dict(season=2025,week=i,team='A',carries=10,targets=5) for i in range(1,4)]
        self.assertEqual(T.prior_role(rows,2025,4,'A')['n'],3)
        self.assertIsNone(T.prior_role(rows,2025,3,'A'))
        self.assertIsNone(T.prior_role(rows,2026,4,'A'))
        rows[1]['team']='B'
        self.assertIsNone(T.prior_role(rows,2025,4,'A'))

    def test_duplicate_roles_rejected(self):
        rows=[dict(season=2025,week=1,team='A',carries=1,targets=1)]*3
        with self.assertRaises(ValueError):
            T.prior_role(rows,2025,4,'A')


if __name__=='__main__':
    unittest.main()
