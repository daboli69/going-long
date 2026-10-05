import math
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from slate_breaker import (elapsed_game_seconds, first_td_event, fastest_factors,
                           evaluate_time_models, build_selections, grade_slate,
                           build_payload, build_from_history_file, resolve_archive_or_build)


class SlateBreakerTests(unittest.TestCase):
    def test_existing_archive_is_reused_as_the_entire_original_payload(self):
        config = slate_config()
        archived = slate_payload(config)
        archived['generated_at'] = '2026-09-18T20:44:17.947735+00:00'
        archived['model']['frozen_marker'] = {'source': 'original'}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '2026-09-20.json'
            path.write_text(json.dumps(archived), encoding='utf-8')
            result = resolve_archive_or_build(config, path, lambda: self.fail('builder must not run'))
        self.assertEqual(result, archived)

    def test_existing_archive_identity_or_shape_mismatches_fail_closed(self):
        config = slate_config()
        mutations = [
            lambda p: p.update(date='2026-09-21'),
            lambda p: p.update(offer_id='different-offer'),
            lambda p: p['games'][0].update(away='WRONG'),
            lambda p: p.pop('validation'),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                payload = slate_payload(config)
                mutate(payload)
                path = Path(folder) / 'archive.json'
                path.write_text(json.dumps(payload), encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    resolve_archive_or_build(config, path, lambda: self.fail('invalid archive must not rebuild'))

    def test_new_snapshot_cannot_backfill_after_configured_kickoff(self):
        config = {'date': '2026-09-20', 'offer_id': 'offer', 'games': [['A', 'B']], 'note': '', 'source': ''}
        history = {'derivatives': {'first_td': {'g': {'away': 'A', 'home': 'B',
                    'kickoff': '2026-09-20T17:00:00+00:00', 'outcomes': {}}}},
                   'games': {'nfl': []}}
        with self.assertRaisesRegex(RuntimeError, 'after a configured game has started'):
            build_payload(config, history, [], [], [], '2026-09-20T17:00:01+00:00')

    def test_main_builder_wiring_passes_config_before_history(self):
        config, schedules, rows, roster = slate_config(), [{'schedule': True}], [{'play': True}], [{'roster': True}]
        as_of = '2026-09-18T12:00:00+00:00'
        with tempfile.TemporaryDirectory() as folder:
            history_path = Path(folder) / 'history.json'
            history_path.write_text(json.dumps({'betting': {'history_fixture': True}}), encoding='utf-8')
            with patch('slate_breaker.build_payload', return_value={'built': True}) as build:
                result = build_from_history_file(config, history_path, schedules, rows, roster, as_of)
        self.assertEqual(result, {'built': True})
        build.assert_called_once_with(config, {'history_fixture': True}, schedules, rows, roster, as_of)

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


def slate_config():
    return {'date': '2026-09-20', 'offer_id': 'offer',
            'games': [['A', 'B'], ['C', 'D']], 'note': 'eligibility', 'source': 'source'}


def slate_payload(config):
    return {'schema_version': 1, 'generated_at': '2026-09-18T00:00:00+00:00',
            'date': config['date'], 'offer_id': config['offer_id'],
            'games': [{'id': 'g1', 'away': 'A', 'home': 'B', 'kickoff': '2026-09-20T17:00:00+00:00'},
                      {'id': 'g2', 'away': 'C', 'home': 'D', 'kickoff': '2026-09-20T17:00:00+00:00'}],
            'selections': [{'id': 'player', 'slate_breaker_probability': 0.1}],
            'event_components': {}, 'model': {'version': 'slate-breaker-1'}, 'validation': {},
            'excluded_inactive': [], 'eligibility_note': config['note'], 'source': config['source']}


def td_row(game, player, clock, play):
    return {'game_id': game, 'play_id': play, 'qtr': 1, 'quarter_seconds_remaining': clock,
            'touchdown': 1, 'td_team': 'A', 'posteam': 'A', 'td_player_id': player}


if __name__ == '__main__':
    unittest.main()
