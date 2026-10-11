import sys
import unittest
import json
import tempfile
from unittest.mock import Mock, patch
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from parlay_feed import normalize_props, normalize_periods, request_rows, fetch_parlay, _fetch_parlay, ProviderRows, retry_after_seconds


class ParlayTests(unittest.TestCase):
    def response(self, status, body, headers=None):
        return Mock(ok=status < 400, status_code=status, headers=headers or {}, json=Mock(return_value=body))

    def test_busy_retry_preserves_multi_book_rows(self):
        rows = [{'bookmaker':'draftkings','line':50.5}, {'bookmaker':'fanduel','line':60.5}]
        busy = self.response(503, {'error':'props_temporarily_busy'}, {'Retry-After':'3','x-request-id':'fixture'})
        with patch('parlay_feed.requests.get', side_effect=[busy,self.response(200,rows)]) as get, patch('parlay_feed.time.sleep') as sleep:
            self.assertEqual(request_rows('nfl','props',{'limit':10000},'secret'),rows)
            self.assertEqual(get.call_count,2)
            sleep.assert_called_once_with(5)

    def test_props_follow_documented_next_offset_and_completeness_headers(self):
        first = self.response(200, [{'page': 1}], {'x-result-has-more':'true','x-next-offset':'10000'})
        second = self.response(200, [{'page': 2}], {'x-result-has-more':'false'})
        with patch('parlay_feed.requests.get', side_effect=[first, second]) as get:
            rows = request_rows('nfl','props',{'markets':'player_pass_yds','limit':10000},'secret')
        self.assertEqual(rows, [{'page':1},{'page':2}])
        self.assertFalse(rows.truncated)
        self.assertEqual(get.call_args_list[1].kwargs['params']['offset'], 10000)

        degraded = self.response(200, [], {'x-result-truncated':'true','x-result-degraded':'fanatics'})
        with patch('parlay_feed.requests.get', return_value=degraded):
            rows = request_rows('nfl','props',{},'secret')
        self.assertTrue(rows.truncated)

    def test_503_retry_policy_uses_provider_code(self):
        cases = [
            ('DB_NOT_READY', 30, True),
            ('PRIMARY_TIER_UNAVAILABLE', 60, True),
            ('props_board_degraded', 5, True),
            ('ENDPOINT_DISABLED', None, False),
            ('ASYNCAPI_NOT_LOADED', None, False),
            ('OPENAPI_UNAVAILABLE', None, False),
            ('INCIDENTS_PARSE_FAILED', None, False),
        ]
        for code, delay, retries in cases:
            with self.subTest(code=code):
                response = self.response(503, {'error': code, 'message': 'provider diagnostic'}, {'x-request-id':'fixture'})
                sequence = [response, self.response(200, [])] if retries else [response]
                with patch('parlay_feed.requests.get', side_effect=sequence) as get, patch('parlay_feed.time.sleep') as sleep:
                    if retries:
                        self.assertEqual(request_rows('nfl','props',{},'secret'), [])
                        sleep.assert_called_once_with(delay)
                        self.assertEqual(get.call_count, 2)
                    else:
                        with self.assertRaisesRegex(RuntimeError, code):
                            request_rows('nfl','props',{},'secret')
                        sleep.assert_not_called()
                        self.assertEqual(get.call_count, 1)

    def test_auth_and_schema_errors_do_not_retry(self):
        for response in [self.response(401,{'error':'INVALID_KEY'}),self.response(200,{'unexpected':[]})]:
            with patch('parlay_feed.requests.get',return_value=response) as get, patch('parlay_feed.time.sleep') as sleep:
                with self.assertRaises(RuntimeError): request_rows('nfl','props',{},'secret')
                self.assertEqual(get.call_count,1)
                sleep.assert_not_called()

    def test_transport_retries_are_bounded_and_redacted(self):
        with patch('parlay_feed.requests.get',side_effect=requests.ReadTimeout('secret')) as get, patch('parlay_feed.time.sleep'):
            with self.assertRaises(RuntimeError) as error: request_rows('nfl','props',{},'secret')
            self.assertEqual(get.call_count,2)
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
            if 'player_pass_yds' in params['markets'].split(','): return [row]*10000
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

    def test_retry_after_http_dates_and_invalid_values_are_bounded(self):
        now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
        self.assertEqual(retry_after_seconds('Sat, 10 Oct 2026 12:00:30 GMT', now), 30)
        self.assertEqual(retry_after_seconds('Sat, 10 Oct 2026 12:10:00 GMT', now), 60)
        for value in ('NaN', 'Infinity', '-5', 'bad', None):
            self.assertEqual(retry_after_seconds(value, now), 0)

    def test_offset_clocks_and_invalid_timestamps_do_not_replace_newer_quote(self):
        quote = dict(player='QB', bookmaker='book', market_key='player_pass_yds', line=200.5,
                     commence_time='2030-01-01T00:00:00Z')
        rows = normalize_props([
            dict(quote, last_update='2026-10-10T12:00:00+02:00', over_price=110),
            dict(quote, last_update='2026-10-10T10:30:00Z', over_price=120),
            dict(quote, last_update=1e40, over_price=130),
            dict(quote, last_update='2026-10-10T11:00:00', over_price=140),
            dict(quote, commence_time='2030-01-01T00:00:00', over_price=150),
            dict(quote, commence_time='2030-01-01T00:00:00+00:60', over_price=160),
            dict(quote, last_update='2026-10-10T11:00:00+00:60', over_price=170),
            dict(quote, commence_time='2030-02-30T17:00:00Z', over_price=180),
            dict(quote, commence_time='2030-10-11T24:00:00Z', over_price=190),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['overOdds'], 120)
        period = dict(match_id='g', source='book', market='total', period_key='1H', side='over',
                      line=20.5, price=-110, kickoff='2030-01-01T00:00:00', updatedAt='bad', last_observed_ms=1e40)
        normalized = normalize_periods([period])[0]
        self.assertTrue(normalized['inPlay'])
        self.assertIsNone(normalized['updatedAt'])

    def test_malformed_nested_odds_preserve_other_boards_without_retry(self):
        malformed = [
            {'id': 'broken', 'bookmakers': {}},
            {'id': 'broken', 'bookmakers': [None]},
            {'id': 'broken', 'bookmakers': [{'markets': {}}]},
            {'id': 'broken', 'bookmakers': [{'markets': [{'outcomes': [None]}]}]},
            {'id': 'broken', 'bookmakers': [{'key': 'b', 'markets': [{'key': 42, 'outcomes': []}]}]},
            {'id': 'broken', 'home_team': {}},
            {'id': 'broken', 'bookmakers': [{'key': {}}]},
            {'id': 'broken', 'bookmakers': [{'markets': [{'key': '1h_total', 'outcomes': [{'name': []}]}]}]},
        ]
        quote = dict(player='QB', bookmaker='book', market_key='player_pass_yds', line=200.5,
                     commence_time='2030-01-01T00:00:00Z', last_update='2026-10-10T10:30:00Z')
        for event in malformed:
            def get(url, **kwargs):
                core = url.endswith('/props') and 'player_pass_yds' in kwargs['params']['markets'].split(',')
                return self.response(200, [event] if url.endswith('/odds') else [quote] if core else [])
            with self.subTest(event=event), patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.requests.get', side_effect=get) as requests, patch('parlay_feed.time.sleep') as sleep:
                result = _fetch_parlay('nfl')
                self.assertEqual(requests.call_count, 4)
                sleep.assert_not_called()
                self.assertEqual(len(result['props']), 1)
                self.assertEqual(result['source_states']['odds'], 'FAILED')
                self.assertEqual(result['source_states']['props'], 'FRESH')
                self.assertEqual(result['feed_status'], 'FALLBACK')
                self.assertIn('odds', result['source_errors'])

    def test_malformed_scalar_identities_fail_only_their_source(self):
        quote = dict(player='QB', bookmaker='book', market_key='player_pass_yds', line=200.5)
        cases = [('props', dict(quote, market_key={})), ('props', dict(quote, bookmaker={'bad': 'book'})),
                 ('periods', {'match_id': {}, 'source': 'book'}), ('periods', {'match_id': 'game', 'source': {}})]
        for source, malformed in cases:
            def get(url, **kwargs):
                core = url.endswith('/props') and 'player_pass_yds' in kwargs['params']['markets'].split(',')
                if source == 'props' and core or source == 'periods' and url.endswith('/period_markets'):
                    rows = [malformed]
                elif url.endswith('/props'):
                    rows = [quote] if core else [dict(quote, market_key='player_first_td', line=.5)]
                else:
                    rows = []
                return self.response(200, rows)
            with self.subTest(source=source, malformed=malformed), patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.requests.get', side_effect=get) as requests:
                result = _fetch_parlay('nfl')
                self.assertEqual(requests.call_count, 4)
                self.assertEqual(result['source_states'][source], 'FAILED')
                self.assertEqual(result['source_states']['derivatives'], 'FRESH')
                self.assertTrue(result['props'])
                self.assertEqual(result['feed_status'], 'FALLBACK')

    def test_partial_refresh_preserves_original_quote_clocks_and_malformed_provenance(self):
        retained = {'quoteKey': 'retained', 'market': 'pass_yds', 'updatedAt': '2026-10-09T12:00:00Z'}
        previous = {'props': [retained], 'source_observed_at': {'props': '2026-10-09T12:00:00Z'},
                    'last_fresh_at': '2026-10-09T12:00:00Z'}
        def get(sport, endpoint, params, key):
            if endpoint == 'props' and 'player_pass_yds' in params['markets'].split(','):
                raise RuntimeError('core unavailable')
            return [{'id': 'current'}] if endpoint == 'odds' else []
        with patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.request_rows', side_effect=get) as requests:
            result = _fetch_parlay('nfl', previous)
            malformed = _fetch_parlay('nfl', dict(previous, source_observed_at=None))
        self.assertEqual(requests.call_count, 8)  # Four existing boards per refresh; no added retries.
        self.assertEqual(result['props'], [retained])
        self.assertEqual(result['source_states']['props'], 'STALE')
        self.assertEqual(result['source_observed_at']['props'], retained['updatedAt'])
        self.assertIsNone(malformed['source_observed_at']['props'])
        self.assertEqual(result['last_fresh_at'], previous['last_fresh_at'])
        self.assertEqual(result['feed_status'], 'FALLBACK')

    def test_degraded_provider_coverage_is_never_fresh_and_ncaa_props_not_applicable(self):
        def get(sport, endpoint, params, key):
            return ProviderRows([], truncated=endpoint == 'props')
        with patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.request_rows', side_effect=get):
            result = _fetch_parlay('nfl')
            ncaa = _fetch_parlay('ncaa')
        self.assertEqual(result['feed_status'], 'FALLBACK')
        self.assertEqual(result['source_states']['props'], 'DEGRADED')
        self.assertTrue(result['coverage']['possibly_truncated'])
        self.assertIn('props', result['source_errors'])
        self.assertEqual(ncaa['source_states']['props'], 'NOT_APPLICABLE')
        self.assertEqual(ncaa['source_states']['derivatives'], 'NOT_APPLICABLE')
        self.assertIsNone(ncaa['source_observed_at']['props'])

    def test_malformed_period_rows_are_rejected_without_retry_and_false_degraded_flag_is_healthy(self):
        with patch('parlay_feed.requests.get', return_value=self.response(200, {'results': [None]})) as get:
            with self.assertRaisesRegex(RuntimeError, 'unexpected response schema'):
                request_rows('nfl', 'live/period_markets', {}, 'fixture')
            self.assertEqual(get.call_count, 1)
        with patch('parlay_feed.requests.get', return_value=self.response(200, [], {'x-result-degraded': ' false '})):
            self.assertFalse(request_rows('nfl', 'props', {}, 'fixture').truncated)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'data').mkdir()
            path = root / 'data/ncaa_lines.json'
            path.write_text(json.dumps({'generated_at': '2026-10-09T12:00:00Z', 'games_raw': [{'id': 'old'}]}))
            with patch('parlay_feed.ROOT', root), patch('parlay_feed._fetch_parlay', side_effect=RuntimeError('odds unavailable')):
                with self.assertRaises(RuntimeError):
                    fetch_parlay('ncaa')
            states = json.loads(path.read_text())['source_states']
            self.assertEqual(states['props'], 'NOT_APPLICABLE')
            self.assertEqual(states['derivatives'], 'NOT_APPLICABLE')


if __name__ == '__main__':
    unittest.main()
