import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_pipeline import competing_first_td, period_distribution, pace_factor, first_td_game


class DerivativeTests(unittest.TestCase):
    def test_competing_risks_partition_and_opening_order(self):
        p = competing_first_td([{'a': 1, 'b': 0, 'dst': .1}, {'a': 0, 'b': 1, 'dst': .1}])
        self.assertAlmostEqual(sum(p.values()), 1, places=14)
        self.assertAlmostEqual(p['no_td'], math.exp(-2.2), places=14)
        self.assertGreater(p['a'], p['b'])
        self.assertEqual(competing_first_td([{}]), {'no_td': 1})
        with self.assertRaises(ValueError):
            competing_first_td([{'a': -1}])

    def test_half_moment_matching_and_count_thinning(self):
        full = dict(family='lognormal', mean=200, sd=60, n=12, status='ready')
        half = period_distribution(full, .49, .5)
        self.assertEqual(half['mean'], 98)
        self.assertAlmostEqual(half['sd'], 60*math.sqrt(.5))
        self.assertAlmostEqual(math.exp(half['mu_log']+half['sigma_log']**2/2),98)
        count = period_distribution(dict(full, family='poisson', mean=2), .49, .5)
        self.assertEqual(count['lambda'], .98)
        self.assertEqual(period_distribution({'status':'missing'},.49,.5)['status'],'insufficient')

    def test_pace_shrinkage_bounds(self):
        self.assertEqual(pace_factor({},'1H'),1)
        self.assertEqual(pace_factor({'pace_seconds':30,'periods':{'1H':{'pace_seconds':10,'pace_n':500}}},'1H'),1.1)

    def test_full_pool_includes_other_and_dst_and_is_not_book_dependent(self):
        profiles={'p':dict(name='Player',team='A',position='RB',last_game='2026-09-01',stats={'atd':{'mean':.7}})}
        f={'nfl':{'teams':{},'players':{}}}
        game={'home':'A','away':'B','kickoff':'2026-09-20','model':{'total_mean':45,'margin_mean':3}}
        model=first_td_game(game,profiles,f)
        self.assertAlmostEqual(model['probability_sum'],1)
        self.assertTrue({'p','other_A','other_B','dst_A','dst_B','no_td'} <= model['outcomes'].keys())
        self.assertTrue(all(0 <= x['probability'] <= 1 for x in model['outcomes'].values()))
