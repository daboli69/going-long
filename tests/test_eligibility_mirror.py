import sys
import json
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import eligibility as E

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
FRESH, OLD = '2026-10-11T08:00:00Z', '2026-10-08T08:00:00Z'


def inj(entries, reports=None, at=FRESH):
    return {'generated_at': at, 'source_content_at': at, 'source_roster_at': at, 'source_injury_at': at, 'current_players': {f'T|{k}': {'gsis_id': k, 'roster_status': v} for k, v in entries.items()},
            'current_reports': {f'T|{k}': {'gsis_id': k, **v} for k, v in (reports or {}).items()}}


class EligibilityMirrorTests(unittest.TestCase):
    def test_confirmed_unavailable_covers_every_status_and_reports(self):
        i = inj({'r': 'RES', 's': 'SUS', 't': 'RET', 'x': 'EXE', 'c': 'CUT', 'd': 'DEV', 'a': 'ACT', 'o': 'ACT', 'q': 'ACT', 'b': ''},
                {'o': {'report_status': 'Inactive'}, 'q': {'report_status': 'Questionable'}})
        got = E.confirmed_unavailable(i, {'players': []})
        self.assertEqual(got, {'r', 's', 't', 'x', 'c', 'd', 'o', 'b'})

    def test_roster_snapshot_injury_object_is_used(self):
        got = E.confirmed_unavailable(inj({}), {'players': [{'id': 'z', 'roster_status': 'ACT', 'injury': {'report_status': 'Out'}}, {'id': 'y', 'roster_status': 'ACT', 'injury': {'report_status': 'Questionable'}}]})
        self.assertEqual(got, {'z'})

    def test_freshness_fails_on_stale_or_missing_files(self):
        roster = {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH, 'players': []}
        self.assertTrue(E.freshness(NOW, inj({}), roster)['ok'])
        self.assertFalse(E.freshness(NOW, inj({}, at=OLD), roster)['ok'])
        self.assertIn('injury file', E.freshness(NOW, inj({}, at=OLD), roster)['reason'])
        self.assertFalse(E.freshness(NOW, inj({}), {'generated_at': OLD})['ok'])
        self.assertFalse(E.freshness(NOW, {'current_players': {}}, roster)['ok'])

    def test_bye_teams(self):
        self.assertEqual(E.bye_teams({'bye_carry_forward_teams': ['KC', 'CAR']}), {'KC', 'CAR'})
        self.assertEqual(E.bye_teams({}), set())

    def test_roster_only_unknown_and_contradictory_statuses_block(self):
        for status in ('RES', 'PS', 'BOGUS', '', None):
            roster = {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH, 'players': [{'id': 'a', 'roster_status': status}]}
            self.assertIn('a', E.blocked_ids({'a': {}}, inj({'a': 'ACT'}), roster, NOW, week=5))
            self.assertIn('a', E.confirmed_unavailable(inj({'a': 'ACT'}), roster, week=5))

    def test_explicit_missing_inputs_never_fall_back_to_repository(self):
        self.assertFalse(E.freshness(NOW, None, None)['ok'])
        self.assertEqual(E.blocked_ids({'a': {}}, None, None, NOW), {'a'})

    def test_javascript_python_blocking_parity_on_adversarial_json(self):
        roster = {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH, 'players': [], 'bye_carry_forward_teams': []}
        cases = []

        def add(i, r=roster, profiles=None):
            cases.append({'injury': i, 'roster': r, 'profiles': profiles or {'a': {}, 'unknown': {}}, 'week': 5})

        add(inj({'a': 'ACT'}))
        add({**inj({'a': 'ACT'}), 'source_content_at': OLD})
        add({**inj({'a': 'ACT'}), 'source_content_at': None})
        add(inj({'a': 'ACT'}), {**roster, 'source_injury_at': OLD})
        add(inj({'a': 'ACT'}), {**roster, 'week': 5, 'injury_week': 4})
        add({**inj({'a': 'ACT'}), 'validation': {'injury_report_week': 4}}, {**roster, 'week': 5})
        add(inj({'a': 'ACTIVE'}))
        add(inj({'a': ' act '}))
        for status in ('RES', 'PS', 'BOGUS', '', None, 123, ['ACT']):
            add(inj({'a': status}))
            add(inj({'a': 'ACT'}), {**roster, 'players': [{'id': 'a', 'roster_status': status}]})
        for week in (2, '2', 5, '5', None, 'bad'):
            add(inj({'a': 'ACT'}, {'a': {'report_status': ' Out ', 'week': week}}))
        for stamp in (OLD, 12, '12', '2026-10-11', '2026-10-11T08:00:00', '2026-10-12T08:00:00Z', '2026-02-30T08:00:00Z', '2026-10-10T24:00:00Z', '2026-10-11T08:00:00+00:99', '2026-10-11T08:00:00+01:60', '2026-10-11T08:00:00-00:60'):
            add(inj({'a': 'ACT'}, at=stamp))
        for bad in (None, [], {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH}, {**inj({'a': 'ACT'}), 'current_reports': []},
                    {**inj({'a': 'ACT'}), 'current_reports': {'bad': {'gsis_id': 'a', 'report_status': ['Out']}}},
                    {**inj({'a': 'ACT'}), 'current_players': {'bad': None}}):
            add(bad)
        for bad in (None, [], {'generated_at': FRESH, 'source_content_at': FRESH, 'source_roster_at': FRESH, 'source_injury_at': FRESH}, {**roster, 'players': 'bad'},
                    {**roster, 'players': [None]}, {**roster, 'bye_carry_forward_teams': 'AAA'}):
            add(inj({'a': 'ACT'}), bad)
        tagged = inj({'a': 'ACT'})
        tagged['current_players']['T|a']['team'] = 'AAA'
        add(tagged, {**roster, 'players': [{'id': 'a', 'team': 'BBB', 'roster_status': 'ACT'}]})
        add(tagged, profiles={'a': {'team': 'BBB'}})
        add(tagged, {**roster, 'bye_carry_forward_teams': ['AAA']})
        duplicate = inj({'a': 'ACT'})
        duplicate['current_players']['dup'] = {'gsis_id': 'a', 'roster_status': 'RES'}
        add(duplicate)
        add(inj({'a': 'ACT'}, {'report_only': {'report_status': 'Questionable', 'week': 5}}))
        for roster_week in (99, '99', 6, '6'):
            corrupt = inj({'a': 'ACT'}, {'a': {'report_status': 'Out', 'week': 5}})
            corrupt['current_players']['T|a']['roster_week'] = roster_week
            add(corrupt, {**roster, 'week': 5})
        add(inj({'a': 'ACT'}), {**roster, 'week': 99})
        for report_status in ('UNKNOWN', 'BOGUS', 'uncertain'):
            add(inj({'a': 'ACT'}, {'a': {'report_status': report_status, 'week': 5}}))
            add(inj({'a': 'ACT'}), {**roster, 'players': [{'id': 'a', 'roster_status': 'ACT', 'injury': {'report_status': report_status, 'week': 5}}]})
        js = """const E=require('./shared/going-eligibility.js');let s='';process.stdin.on('data',x=>s+=x);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(c=>{const e=E.create({...c,now:Date.parse('2026-10-11T12:00:00Z')});return {fresh:e.fresh.ok,blocked:[...e.blockedIds(c.profiles)].sort()};}))));"""
        result = subprocess.run(['node', '-e', js], input=json.dumps(cases), text=True,
                                capture_output=True, check=True, cwd=Path(__file__).resolve().parents[1], timeout=20)
        expected = json.loads(result.stdout)
        for case, want in zip(cases, expected):
            with self.subTest(case=case):
                actual = {'fresh': E.freshness(NOW, case['injury'], case['roster'])['ok'],
                          'blocked': sorted(E.blocked_ids(case['profiles'], case['injury'], case['roster'], NOW, week=case['week']))}
                self.assertEqual(actual, want)


if __name__ == '__main__':
    unittest.main()
