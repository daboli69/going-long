import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from odds_history import Archive, normalize


BODY = {'timestamp': '2025-10-12T15:55:00Z', 'data': [{'id': 'event',
    'commence_time': '2025-10-12T17:00:00Z', 'home_team': 'Home', 'away_team': 'Away',
    'bookmakers': [{'key': 'book', 'last_update': '2025-10-12T15:54:00Z', 'markets': [
        {'key': 'player_pass_yds', 'outcomes': [{'name': 'Over', 'description': 'QB', 'price': -110, 'point': 200.5},
                                             {'name': 'Under', 'description': 'QB', 'price': -110, 'point': 200.5}]}]}]}]}


class HistoryTests(unittest.TestCase):
    def response(self, cost=30, used=30, remaining=19970):
        return Mock(status_code=200, json=Mock(return_value=BODY), headers={
            'x-requests-last': str(cost), 'x-requests-used': str(used), 'x-requests-remaining': str(remaining)})

    def test_only_history_paths_and_old_timestamps_can_spend(self):
        with tempfile.TemporaryDirectory() as root:
            fetch = Mock(); a = Archive(root, fetch=fetch)
            for path, date in [('/v4/sports/americanfootball_nfl/odds', '2025-10-12T16:00:00Z'),
                               ('/v4/historical/sports/basketball_nba/odds', '2025-10-12T16:00:00Z'),
                               ('/v4/historical/sports/americanfootball_nfl/odds', '2099-01-01T00:00:00Z')]:
                with self.assertRaises(ValueError): a.request(path, {'date': date}, 30, 'secret')
            fetch.assert_not_called()

    def test_resume_is_immutable_offline_and_secret_free(self):
        with tempfile.TemporaryDirectory() as root:
            fetch = Mock(return_value=self.response()); a = Archive(root, fetch=fetch)
            p = {'date': '2025-10-12T16:00:00Z'}; path = '/v4/historical/sports/americanfootball_nfl/odds'
            a.request(path, p, 30, 'secret'); a.request(path, p, 30, 'different-key')
            a.request(path, {'date': '2025-10-12T12:00:00-04:00'}, 30, 'different-key')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(a.status()['quotes'], 2)
            self.assertEqual(a.status()['credits_charged_or_reserved'], 30)
            self.assertNotIn(b'secret', a.db.read_bytes())
            self.assertEqual(fetch.call_args.kwargs['params']['date'], '2025-10-12T16:00:00Z')
            b = Archive(root, fetch=Mock(side_effect=AssertionError('must remain offline')))
            self.assertEqual(len(b.quotes()), 2)

    def test_ceiling_reserves_before_request(self):
        with tempfile.TemporaryDirectory() as root:
            fetch = Mock(return_value=self.response()); a = Archive(root, limit=30, fetch=fetch)
            a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z'}, 30, 'secret')
            self.assertIsNone(a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-11T16:00:00Z'}, 30, 'secret'))
            self.assertEqual(fetch.call_count, 1)

    def test_full_market_scope_must_be_reserved_before_network(self):
        with tempfile.TemporaryDirectory() as root:
            fetch = Mock(); a = Archive(root, fetch=fetch)
            with self.assertRaises(ValueError):
                a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z', 'markets': 'h2h,spreads,totals'}, 1, 'secret')
            with self.assertRaises(ValueError):
                a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z', 'markets': 'unsupported'}, 30, 'secret')
            fetch.assert_not_called()

    def test_transport_failure_is_reserved_and_stops_without_leaking_key(self):
        with tempfile.TemporaryDirectory() as root:
            a = Archive(root, fetch=Mock(side_effect=requests.Timeout('https://example/?apiKey=secret')))
            with self.assertRaises(RuntimeError) as exc:
                a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z'}, 30, 'secret')
            self.assertNotIn('apiKey=secret', str(exc.exception))
            self.assertEqual(a.status()['credits_charged_or_reserved'], 30)
            self.assertIn('stopped', a.status()['control'])

    def test_account_balance_and_missing_headers_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            fetch = Mock(return_value=self.response(30, 19999, 1)); a = Archive(root, fetch=fetch)
            a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z'}, 30, 'secret')
            self.assertIsNone(a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-11T16:00:00Z'}, 30, 'secret'))
            self.assertEqual(fetch.call_count, 1)
        with tempfile.TemporaryDirectory() as root:
            r = self.response(); r.headers = {}; a = Archive(root, fetch=Mock(return_value=r))
            with self.assertRaises(RuntimeError):
                a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z'}, 30, 'secret')

    def test_dedup_and_point_in_time_validation(self):
        d = json.loads(json.dumps(BODY)); d['data'].append(d['data'][0])
        self.assertEqual(len(normalize(d, 'fixture')), 2)
        d['data'][0]['commence_time'] = '2025-10-12T15:00:00Z'
        self.assertEqual(normalize(d, 'fixture'), [])
        d = json.loads(json.dumps(BODY)); d['data'][0]['bookmakers'][0]['last_update'] = '2025-10-12T16:00:00Z'
        self.assertEqual(normalize(d, 'fixture'), [])
        for malformed in (None, {}, [None, {'key': 'bad', 'markets': [None, {'key': 'bad', 'outcomes': [None]}]}]):
            d = json.loads(json.dumps(BODY)); d['data'][0]['bookmakers'] = malformed
            self.assertEqual(normalize(d, 'fixture'), [])

    def test_missing_historical_event_only_skips_with_verified_zero_charge(self):
        for verified in (True, False):
            with tempfile.TemporaryDirectory() as root:
                missing = Mock(status_code=404, json=Mock(return_value={'error_code': 'EVENT_NOT_FOUND'}),
                    headers={'x-requests-last': '0', 'x-requests-used': '30' if verified else '31', 'x-requests-remaining': '19970'})
                fetch = Mock(side_effect=[self.response(), missing]); a = Archive(root, fetch=fetch)
                a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z'}, 30, 'secret')
                if verified:
                    self.assertIsNone(a.request('/v4/historical/sports/americanfootball_nfl/events/missing/odds', {'date': '2025-10-11T16:00:00Z'}, 60, 'secret'))
                    self.assertEqual(a.status()['credits_charged_or_reserved'], 30)
                    self.assertNotIn('stopped', a.status()['control'])
                else:
                    with self.assertRaises(RuntimeError):
                        a.request('/v4/historical/sports/americanfootball_nfl/events/missing/odds', {'date': '2025-10-11T16:00:00Z'}, 60, 'secret')
                    self.assertEqual(a.status()['credits_charged_or_reserved'], 90)


if __name__ == '__main__': unittest.main()
