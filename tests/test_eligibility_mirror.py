import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import eligibility as E

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
FRESH, OLD = '2026-10-11T08:00:00Z', '2026-10-08T08:00:00Z'


def inj(entries, reports=None, at=FRESH):
    return {'generated_at': at, 'current_players': {f'T|{k}': {'gsis_id': k, 'roster_status': v} for k, v in entries.items()},
            'current_reports': {f'T|{k}': {'gsis_id': k, **v} for k, v in (reports or {}).items()}}


class EligibilityMirrorTests(unittest.TestCase):
    def test_confirmed_unavailable_covers_every_status_and_reports(self):
        i = inj({'r': 'RES', 's': 'SUS', 't': 'RET', 'x': 'EXE', 'c': 'CUT', 'd': 'DEV', 'a': 'ACT', 'o': 'ACT', 'q': 'ACT', 'b': ''},
                {'o': {'report_status': 'Inactive'}, 'q': {'report_status': 'Questionable'}})
        got = E.confirmed_unavailable(i, {'players': []})
        self.assertEqual(got, {'r', 's', 't', 'x', 'c', 'd', 'o', 'b'})

    def test_roster_snapshot_injury_object_is_used(self):
        got = E.confirmed_unavailable(inj({}), {'players': [{'id': 'z', 'injury': {'report_status': 'Out'}}, {'id': 'y', 'injury': {'report_status': 'Questionable'}}]})
        self.assertEqual(got, {'z'})

    def test_freshness_fails_on_stale_or_missing_files(self):
        roster = {'generated_at': FRESH}
        self.assertTrue(E.freshness(NOW, inj({}), roster)['ok'])
        self.assertFalse(E.freshness(NOW, inj({}, at=OLD), roster)['ok'])
        self.assertIn('injury file', E.freshness(NOW, inj({}, at=OLD), roster)['reason'])
        self.assertFalse(E.freshness(NOW, inj({}), {'generated_at': OLD})['ok'])
        self.assertFalse(E.freshness(NOW, {'current_players': {}}, roster)['ok'])

    def test_bye_teams(self):
        self.assertEqual(E.bye_teams({'bye_carry_forward_teams': ['KC', 'CAR']}), {'KC', 'CAR'})
        self.assertEqual(E.bye_teams({}), set())


if __name__ == '__main__':
    unittest.main()
