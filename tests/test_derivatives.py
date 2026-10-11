import math
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_pipeline import competing_first_td, period_distribution, pace_factor, first_td_game, unavailable_players


class DerivativeTests(unittest.TestCase):
    def test_derivative_availability_uses_complete_shared_candidate_gate(self):
        profiles = {'unknown': {'team': 'A'}}
        with patch('eligibility.blocked_ids', return_value={'unknown'}) as gate:
            self.assertEqual(unavailable_players(profiles), {'unknown'})
        gate.assert_called_once_with(profiles)
    def first_td_fixture(self, margin=0, home_weight=.8, away_weight=.8):
        recent = datetime.now(timezone.utc).date().isoformat()
        profiles = {pid: dict(name=pid, team=team, position='RB', last_game=recent,
                             stats={'atd': {'mean': weight}})
                    for pid, team, weight in [('h', 'A', home_weight), ('a', 'B', away_weight)]}
        game = dict(id='exact-game', home='A', away='B', kickoff='2026-10-11T17:00:00Z',
                    total=48, spread=-margin, model={'total_mean': 40, 'margin_mean': 0})
        return game, profiles, {'nfl': {'teams': {}, 'players': {}}}

    @staticmethod
    def team_mass(model, team):
        return sum(p['probability'] for p in model['outcomes'].values() if p.get('team') == team)

    def test_first_td_equal_environments_have_equal_team_mass(self):
        game, profiles, features = self.first_td_fixture()
        model = first_td_game(game, profiles, features)
        self.assertAlmostEqual(self.team_mass(model, 'A'), self.team_mass(model, 'B'), places=14)
        self.assertGreater(model['outcomes']['a']['probability'], 0)
        self.assertEqual(model['game_id'], 'exact-game')
        self.assertEqual(model['calculation_version'], 2)

    def test_first_td_away_environment_uses_game_total_not_home_player_weights(self):
        game, profiles, features = self.first_td_fixture(margin=6)
        with patch('build_pipeline.competing_first_td', wraps=competing_first_td) as integrate:
            model = first_td_game(game, profiles, features)
        stages = integrate.call_args.args[0]
        for team, expected_points in [('A', 27), ('B', 21)]:
            offense = sum(v for s in stages for key, v in s.items() if key in ({'h', 'other_A'} if team == 'A' else {'a', 'other_B'}))
            self.assertAlmostEqual(offense, expected_points*.75/7)
        self.assertGreater(self.team_mass(model, 'A'), self.team_mass(model, 'B'))
        self.assertGreater(self.team_mass(model, 'B'), .3)
        profiles['h']['stats']['atd']['mean'] = 100
        changed = first_td_game(game, profiles, features)
        self.assertAlmostEqual(self.team_mass(model, 'B'), self.team_mass(changed, 'B'))

    def test_first_td_swapping_home_and_away_preserves_matchup_probabilities(self):
        game, profiles, features = self.first_td_fixture(margin=8)
        original = first_td_game(game, profiles, features)
        game.update(home='B', away='A', spread=8)
        swapped = first_td_game(game, profiles, features)
        for key, p in original['outcomes'].items():
            self.assertAlmostEqual(p['probability'], swapped['outcomes'][key]['probability'], places=14)

    def test_first_td_empty_or_unavailable_home_scorers_do_not_zero_away(self):
        game, profiles, features = self.first_td_fixture(margin=7)
        model = first_td_game(game, profiles, features, unavailable={'h'})
        self.assertNotIn('h', model['outcomes'])
        self.assertGreater(model['outcomes']['a']['probability'], 0)
        self.assertGreater(model['outcomes']['other_A']['probability'], 0)
        self.assertAlmostEqual(sum(p['probability'] for p in model['outcomes'].values()), 1, places=14)
        self.assertLess(sum(p['probability'] for p in model['outcomes'].values() if p.get('player_id')), 1)
    def test_first_td_future_participation_is_not_pregame_evidence(self):
        game, profiles, features = self.first_td_fixture()
        profiles['h']['last_game'] = (datetime.now(timezone.utc).date()+timedelta(days=1)).isoformat()
        model = first_td_game(game, profiles, features)
        self.assertNotIn('h', model['outcomes'])
        self.assertGreater(model['outcomes']['a']['probability'], 0)
        self.assertAlmostEqual(model['probability_sum'], 1, places=14)

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
