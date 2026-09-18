import sys
import unittest
import json
import tempfile
from unittest.mock import Mock, patch
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from parlay_feed import normalize_props, normalize_periods, request_rows, fetch_parlay, _fetch_parlay


class ParlayTests(unittest.TestCase):
    def response(self, status, body, headers=None):
        return Mock(ok=status < 400, status_code=status, headers=headers or {}, json=Mock(return_value=body))

    def test_busy_retry_preserves_multi_book_rows(self):
        rows = [{'bookmaker':'draftkings','line':50.5}, {'bookmaker':'fanduel','line':60.5}]
        busy = self.response(503, {'error':'props_temporarily_busy'}, {'Retry-After':'3','x-request-id':'fixture'})
        with patch('parlay_feed.requests.get', side_effect=[busy,self.response(200,rows)]) as get, patch('parlay_feed.time.sleep') as sleep:
            self.assertEqual(request_rows('nfl','props',{'limit':10000},'secret'),rows)
            self.assertEqual(get.call_count,2)
            sleep.assert_called_once_with(3)

    def test_auth_and_schema_errors_do_not_retry(self):
        for response in [self.response(401,{'error':'INVALID_KEY'}),self.response(200,{'unexpected':[]})]:
            with patch('parlay_feed.requests.get',return_value=response) as get, patch('parlay_feed.time.sleep') as sleep:
                with self.assertRaises(RuntimeError): request_rows('nfl','props',{},'secret')
                self.assertEqual(get.call_count,1)
                sleep.assert_not_called()

    def test_transport_retries_are_bounded_and_redacted(self):
        with patch('parlay_feed.requests.get',side_effect=requests.ReadTimeout('secret')) as get, patch('parlay_feed.time.sleep'):
            with self.assertRaises(RuntimeError) as error: request_rows('nfl','props',{},'secret')
            self.assertEqual(get.call_count,3)
            self.assertIn('ReadTimeout',str(error.exception))
            self.assertNotIn('secret',str(error.exception))

    def test_failure_preserves_quotes_and_generation_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'data').mkdir()
            path=root/'data/nfl_betting.json'
            old={'generated_at':'2026-09-17T00:00:00Z','props':[{'bookKey':'draftkings','updatedAt':'old'}]}
            path.write_text(json.dumps(old))
            with patch('parlay_feed.ROOT',root), patch('parlay_feed._fetch_parlay',side_effect=RuntimeError('Parlay props: HTTP 503')):
                with self.assertRaises(RuntimeError): fetch_parlay('nfl')
            stored=json.loads(path.read_text())
            self.assertEqual(stored['props'],old['props'])
            self.assertEqual(stored['generated_at'],old['generated_at'])
            self.assertEqual(stored['feed_status'],'STALE')
            self.assertEqual(stored['refresh_status'],'FAILED')
            self.assertEqual(stored['source_states']['props'],'STALE')

    def test_derivative_fallback_uses_actual_primary_rows(self):
        row=dict(player='P',bookmaker='draftkings',market_key='player_first_td',line=.5,over_price=500)
        def get(sport,endpoint,params,key):
            if endpoint=='odds': return [{'id':'event','bookmakers':[]}]
            if endpoint=='live/period_markets': return []
            if 'player_pass_yds' in params['markets']: return [row]*10000
            raise RuntimeError('Parlay props: HTTP 503')
        with patch.dict('os.environ',{'PARLAY_API_KEY':'fixture'}), patch('parlay_feed.request_rows',side_effect=get):
            result=_fetch_parlay('nfl')
        self.assertEqual(result['source_states']['derivatives'],'FALLBACK')
        self.assertEqual(result['props'][0]['bookKey'],'draftkings')
        self.assertEqual(result['props'][0]['market'],'first_td')
        self.assertTrue(result['coverage']['possibly_truncated'])

    def test_period_duplicates_and_first_td_alias(self):
        q=dict(match_id='a',source='book',market='total',period_key='1H',side='over',line=20.5,price=-110,age_seconds=4)
        rows=normalize_periods([q,dict(q,age_seconds=1,price=110),dict(q,period_key='Q1'),dict(q,line=21.5)])
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['price'],110)
        self.assertTrue(rows[0]['inPlay'])
        first=normalize_props([dict(player='P',bookmaker='book',market_key='player_first_td',line=None,over_price=500)])
        self.assertEqual(first[0]['market'],'first_td')
        self.assertEqual(first[0]['line'],.5)

    def test_thresholds_missing_prices_and_dfs(self):
        quote = dict(player='Josh Allen', bookmaker='draftkings', market_key='player_anytime_td',
                     line=1.5, over_price=600, under_price=None, commence_time='2030-09-01T00:00:00Z')
        rows = normalize_props([quote, {**quote, 'line': 0},
                                {**quote, 'bookmaker': 'prizepicks', 'dfs_normalized': True}],
                               datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual([r['line'] for r in rows], [1.5, .5, 1.5])
        self.assertIsNone(rows[0]['underOdds'])
        self.assertIsNone(rows[2]['overOdds'])

    def test_started_invalid_and_unsupported_rows(self):
        quote = dict(player='Puka Nacua', bookmaker='a', market_key='player_receiving_yards', line=80.5)
        rows = normalize_props([quote, {**quote, 'commence_time': 'invalid'},
                                {**quote, 'commence_time': '2020-01-01T00:00:00Z'},
                                {**quote, 'market_key': 'player_longest_reception'}])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['kickoff'])


if __name__ == '__main__':
    unittest.main()
