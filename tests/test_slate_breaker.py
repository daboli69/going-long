import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from slate_breaker import (elapsed_game_seconds, first_td_event, fastest_factors,
                           evaluate_time_models, build_selections, grade_slate)


class SlateBreakerTests(unittest.TestCase):
    def test_elapsed_game_time_ignores_kickoff_and_supports_overtime(self):
        self.assertEqual(elapsed_game_seconds({'qtr': 1, 'quarter_seconds_remaining': 840}), 60)
        self.assertEqual(elapsed_game_seconds({'qtr': 2, 'quarter_seconds_remaining': 900}), 900)
        self.assertEqual(elapsed_game_seconds({'qtr': 5, 'quarter_seconds_remaining': 570}), 3630)

    def test_fastest_competition_and_exact_ties(self):
        early = [1.0, 0.0]
        late = [0.0, 1.0]
        tied = fastest_factors({'a': {'pmf': early, 'no_td_probability': 0},
                               'b': {'pmf': early, 'no_td_probability': 0}})
        self.assertEqual(tied, {'a': 1.0, 'b': 1.0})
        ordered = fastest_factors({'a': {'pmf': early, 'no_td_probability': 0},
                                  'b': {'pmf': late, 'no_td_probability': 0}})
        self.assertEqual(ordered, {'a': 1.0, 'b': 0.0})

    def test_complete_eight_game_slate_competes_on_elapsed_time(self):
        forecasts = {}
        for index in range(8):
            pmf = [0.0] * 8
            pmf[index] = 1.0
            forecasts[str(index)] = {'pmf': pmf, 'no_td_probability': 0}
        factors = fastest_factors(forecasts)
        self.assertEqual(factors['0'], 1.0)
        self.assertTrue(all(factors[str(index)] == 0 for index in range(1, 8)))

    def test_return_td_is_one_event_with_player_and_dst_owners(self):
        event = first_td_event({'game_id': 'g', 'play_id': 7, 'qtr': 1, 'quarter_seconds_remaining': 800,
                                'touchdown': 1, 'td_team': 'BUF', 'posteam': 'BUF', 'td_player_id': 'p',
                                'kickoff_attempt': 1})
        self.assertEqual(event['elapsed_seconds'], 100)
        self.assertEqual(event['eligible_selection_ids'], ['p', 'dst_BUF'])

    def test_complete_active_field_excludes_inactive_and_allocates_reserved_mass(self):
        games = [{'id': 'g', 'away': 'A', 'home': 'B'}]
        first = {'g': {'outcomes': {'p1': {'probability': .2}, 'other_A': {'probability': .04},
                                     'dst_A': {'probability': .03}, 'other_B': {'probability': .02},
                                     'dst_B': {'probability': .03}}}}
        roster = [{'gsis_id': 'p1', 'team': 'A', 'status': 'ACT', 'position': 'RB', 'full_name': 'Known'},
                  {'gsis_id': 'p2', 'team': 'A', 'status': 'ACT', 'position': 'WR', 'full_name': 'New'},
                  {'gsis_id': 'p3', 'team': 'A', 'status': 'INA', 'position': 'WR', 'full_name': 'Inactive'}]
        selections, components, inactive, _ = build_selections(games, first, roster, [], defaultdict_counter(),
                                                                 {'QB': .1, 'RB': .3, 'FB': .05, 'WR': .4, 'TE': .15})
        ids = {x['id'] for x in selections}
        self.assertIn('p1', ids); self.assertIn('p2', ids); self.assertNotIn('p3', ids)
        self.assertIn('Inactive', inactive)
        new = next(x for x in selections if x['id'] == 'p2')
        self.assertAlmostEqual(new['first_td_probability'], .04)
        self.assertTrue(components)

    def test_chronological_validation_never_scores_training_games(self):
        records = [{'date': f'2024-01-{1 + i // 20:02d}', 'game_id': str(i),
                    'elapsed_seconds': 300 + i % 60, 'total': 44.0} for i in range(405)]
        result = evaluate_time_models(records, minimum_training=400)
        self.assertEqual(result['models']['empirical']['n'], 5)
        self.assertEqual(result['selected'], 'empirical')

    def test_grading_preserves_slate_ties(self):
        snapshot = {'games': [{'id': 'a'}, {'id': 'b'}]}
        rows = [td_row('a', 'p1', 700, 1), td_row('b', 'p2', 700, 2)]
        result = grade_slate(snapshot, rows)
        self.assertEqual(result['winning_elapsed_seconds'], 200)
        self.assertEqual(result['winner_selection_ids'], ['p1', 'p2'])


def defaultdict_counter():
    from collections import defaultdict, Counter
    return defaultdict(Counter)


def td_row(game, player, clock, play):
    return {'game_id': game, 'play_id': play, 'qtr': 1, 'quarter_seconds_remaining': clock,
            'touchdown': 1, 'td_team': 'A', 'posteam': 'A', 'td_player_id': player}


if __name__ == '__main__':
    unittest.main()
