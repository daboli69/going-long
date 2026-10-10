"""Offline downstream regressions: builders must not create forecasts on failed feeds."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import king_endzone as king
import slate_breaker as slate

STAMP = '2026-10-10T12:00:00Z'
ROSTER = {'generated_at': STAMP, 'players': [{'id': 'p', 'team': 'A', 'roster_status': 'ACT'}]}
INJURY = {'generated_at': STAMP, 'current_players': {}, 'current_reports': {}}


class JackpotAvailabilityTests(unittest.TestCase):
    def test_both_builders_refuse_missing_malformed_stale_or_future_feed(self):
        for injury in [None, {'generated_at': STAMP}, dict(INJURY, generated_at='2026-10-06T12:00:00Z'),
                       dict(INJURY, generated_at='2026-10-12T12:00:00Z')]:
            with self.subTest(injury=injury), patch('eligibility._load', side_effect=lambda name: injury if name == 'injury_context.json' else ROSTER):
                with self.assertRaisesRegex(RuntimeError, 'availability unverified'):
                    king.build_slate([], {}, [], [], STAMP)
                with self.assertRaisesRegex(RuntimeError, 'availability unverified'):
                    slate.build_selections([], {}, [], [], {}, {}, as_of=STAMP)

    def test_fresh_feed_does_not_clear_unknown_or_conflicting_raw_roster(self):
        games = [{'id': 'g', 'away': 'A', 'home': 'B'}]
        first = {'g': {'outcomes': {'p': {'probability': .2}, 'unknown': {'probability': .2}}}}
        raw = [{'gsis_id': 'unknown', 'team': 'A', 'status': 'ACT', 'position': 'WR', 'full_name': 'Unknown'},
               {'gsis_id': 'p', 'team': 'B', 'status': 'ACT', 'position': 'RB', 'full_name': 'Conflicting'}]
        with patch('eligibility._load', side_effect=lambda name: INJURY if name == 'injury_context.json' else ROSTER):
            selections, _, _, _ = slate.build_selections(games, first, raw, [], defaultdict(Counter), {}, as_of=STAMP)
        self.assertFalse(any(row['kind'] == 'player' for row in selections))


if __name__ == '__main__':
    unittest.main()
