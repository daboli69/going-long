import sys
import unittest
import json
import tempfile
from unittest.mock import Mock, patch
import requests
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from parlay_feed import normalize_props, normalize_periods, request_rows, fetch_parlay, _fetch_parlay, ProviderRows, retry_after_seconds, props_query_plan, GROUPS, MARKET_MAP


class ParlayTests(unittest.TestCase):
    def large_board(self):
        # Synthetic row-volume fixture: former core query exceeds the serving cap.
        counts = {'rec_yds': 3400, 'atd': 3100, 'receptions': 2100, 'rush_yds': 1400,
                  'pass_yds': 900, 'pass_tds': 310, 'first_td': 400,
                  'receptions_1q': 300, 'pass_yds_1h': 300}
        return [dict(quoteKey=f'{market}-{i}', market=market, player=f'P-{i}',
                     updatedAt='2026-10-10T12:00:00Z')
                for market, count in counts.items() for i in range(count)]

    def test_large_board_balances_every_market_exactly_once_with_two_queries(self):
        previous = self.large_board()
        groups = props_query_plan(previous)
        self.assertEqual(len(groups), 2)
        self.assertEqual(sorted(market for group in groups for market in group), sorted(GROUPS))
        counts = [sum(row['market'] in group for row in previous) for group in groups]
        self.assertLess(max(counts), 8000)
        self.assertEqual(groups, props_query_plan(list(reversed(previous))))

    def test_internal_cap_never_spends_a_second_page_even_with_has_more(self):
        response = self.response(200, [{'row': 1}], {'x-result-truncated': 'true',
            'x-result-has-more': 'true', 'x-next-offset': '10000',
            'x-result-truncated-hint': 'internal per-source cap'})
        with patch('parlay_feed.requests.get', return_value=response) as get:
            rows = request_rows('nfl', 'props', {'limit': 10000}, 'fixture')
        self.assertEqual(get.call_count, 1)
        self.assertTrue(rows.truncated)
        self.assertIn('internal per-source cap', rows.diagnostics[0]['hint'])

    def test_approved_market_scopes_have_fixed_budget_and_wire_counts(self):
        groups = props_query_plan([], 'markets')
        self.assertEqual(len(groups), 9)
        self.assertEqual(sorted(market for group in groups for market in group), sorted(GROUPS))
        self.assertIn(['first_td'], groups)
        for suffix in ('_1h', '_1q'):
            self.assertIn([market for market in GROUPS if market.endswith(suffix)], groups)
        self.assertIn(['pass_tds', 'rush_tds', 'rec_tds'], groups)
        def get(sport, endpoint, params, key, **kwargs):
            if endpoint != 'props':
                return ProviderRows()
            self.assertEqual(kwargs['max_pages'], 1)
            return ProviderRows([dict(player='P', bookmaker='book', market_key=market,
                                      market='Descriptive provider label', line=.5)
                                 for market in params['markets'].split(',')])
        with patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture', 'PARLAY_PROPS_PARTITIONS': 'markets'}), patch('parlay_feed.request_rows', side_effect=get) as calls:
            result = _fetch_parlay('nfl')
        self.assertEqual(calls.call_count, 11)  # Nine props + existing odds/periods.
        self.assertEqual(result['feed_status'], 'FRESH')
        self.assertEqual(result['coverage']['raw_props'], 8)
        self.assertEqual(result['coverage']['derivative_props'], len(GROUPS) - 8)

    def test_explicit_wire_period_cannot_be_priced_as_full_game(self):
        quote = dict(player='QB', bookmaker='book', market_key='player_pass_yds', line=60.5,
                     market='Descriptive provider label')
        rows = normalize_props([dict(quote, period=period) for period in ('FULL', '1H', 'Q1')])
        self.assertEqual([row['market'] for row in rows], ['pass_yds', 'pass_yds_1h', 'pass_yds_1q'])
        self.assertEqual(len({row['quoteKey'] for row in rows}), 3)
        for period in ('UNKNOWN', '', 'Q2', {}, 'HALFTIME'):
            with self.subTest(period=period):
                self.assertEqual(normalize_props([dict(quote, period=period)]), [])
        self.assertEqual(normalize_props([dict(quote, market_key='player_pass_yds_1st_half', period='FULL')]), [])
        self.assertEqual(normalize_props([dict(quote, market_key='player_anytime_td', period='1H')]), [])

    def test_one_page_budget_does_not_certify_unfetched_continuation(self):
        response = self.response(200, [], {'x-result-has-more': 'true', 'x-next-offset': '10000'})
        with patch('parlay_feed.requests.get', return_value=response) as get:
            rows = request_rows('nfl', 'props', {}, 'fixture', max_pages=1)
        self.assertEqual(get.call_count, 1)
        self.assertTrue(rows.truncated)

    def test_full_read_window_hint_is_retained_but_bounded_and_redacted(self):
        hint = 'read window ' + 'x' * 400 + ' affected scope fixture ' + 'x' * 2000
        response = self.response(200, [], {'x-result-truncated': 'true', 'x-result-truncated-hint': hint})
        with patch('parlay_feed.requests.get', return_value=response):
            rows = request_rows('nfl', 'props', {}, 'fixture')
        captured = rows.diagnostics[0]['hint']
        self.assertIn('affected scope', captured)
        self.assertNotIn('fixture', captured)
        self.assertEqual(len(captured), 2048)

    def test_balanced_refresh_restores_full_synthetic_board_without_more_requests(self):
        previous = self.large_board()
        def get(sport, endpoint, params, key):
            if endpoint != 'props':
                return ProviderRows()
            markets = {MARKET_MAP[key] for key in params['markets'].split(',')}
            rows = [row for row in previous if row['market'] in markets]
            return ProviderRows(rows[:10000], truncated=len(rows) > 10000)
        with patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.request_rows', side_effect=get) as calls:
            result = _fetch_parlay('nfl', {'props': previous})
        self.assertEqual(calls.call_count, 4)
        self.assertEqual(result['feed_status'], 'FRESH')
        self.assertFalse(result['coverage']['possibly_truncated'])
        self.assertEqual(len(result['props']), len(previous))
        self.assertEqual(len({row['quoteKey'] for row in result['props']}), len(previous))
        self.assertTrue(all(row['updatedAt'] == '2026-10-10T12:00:00Z' for row in result['props']))

    def test_mixed_partition_outage_preserves_correct_market_fallback_and_family_states(self):
        previous = self.large_board()
        groups = props_query_plan(previous)
        for fail_index in (0, 1):
            def get(sport, endpoint, params, key):
                if endpoint != 'props':
                    return ProviderRows()
                markets = {MARKET_MAP[key] for key in params['markets'].split(',')}
                if markets == set(groups[fail_index]):
                    raise RuntimeError('partition unavailable')
                return ProviderRows([dict(row, updatedAt='2026-10-11T12:00:00Z') for row in previous if row['market'] in markets])
            with self.subTest(fail_index=fail_index), patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.request_rows', side_effect=get):
                result = _fetch_parlay('nfl', {'props': previous, 'last_fresh_at': 'original'})
            self.assertEqual(result['feed_status'], 'FALLBACK')
            self.assertEqual(result['last_fresh_at'], 'original')
            self.assertNotEqual(result['source_states']['props'], 'FRESH')
            self.assertNotEqual(result['source_states']['derivatives'], 'FRESH')
            self.assertEqual(len(result['props']), len(previous))
            for row in result['props']:
                self.assertEqual(row['updatedAt'], '2026-10-10T12:00:00Z' if row['market'] in groups[fail_index] else '2026-10-11T12:00:00Z')

    def test_unrecoverable_single_market_still_fails_closed(self):
        previous = [dict(quoteKey=str(i), market='atd') for i in range(11000)]
        def get(sport, endpoint, params, key):
            return ProviderRows([], truncated=endpoint == 'props' and 'player_anytime_td' in params['markets'].split(','))
        with patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.request_rows', side_effect=get):
            result = _fetch_parlay('nfl', {'props': previous})
        self.assertEqual(result['feed_status'], 'FALLBACK')
        self.assertEqual(result['source_states']['props'], 'DEGRADED')
        self.assertTrue(result['coverage']['possibly_truncated'])

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

    def test_partial_headers_keep_redacted_actionable_diagnostics_without_paid_retry(self):
        response = self.response(200, [], {
            'x-result-has-more': 'false', 'x-result-truncated': 'true',
            'x-result-degraded': 'book-a,book-b',
            'x-result-truncated-hint': 'internal cap; secret\n narrow query',
            'x-request-id': 'request-secret',
        })
        with patch('parlay_feed.requests.get', return_value=response) as get:
            rows = request_rows('nfl', 'props', {'limit': 10000}, 'secret')
        self.assertTrue(rows.truncated)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(rows.diagnostics[0]['degraded_books'], 'book-a,book-b')
        self.assertIn('internal cap', rows.diagnostics[0]['hint'])
        self.assertNotIn('secret', json.dumps(rows.diagnostics))
        self.assertNotIn('\n', rows.diagnostics[0]['hint'])

    def test_repeated_pagination_offset_stops_without_duplicate_request(self):
        response = self.response(200, [{'page': 1}], {'x-result-has-more': 'true', 'x-next-offset': '0'})
        with patch('parlay_feed.requests.get', return_value=response) as get:
            rows = request_rows('nfl', 'props', {'limit': 10000}, 'secret')
        self.assertTrue(rows.truncated)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(len(rows), 1)

    def test_props_boards_do_not_overlap_or_increase_request_budget(self):
        import threading
        active = 0
        lock = threading.Lock()
        def get(sport, endpoint, params, key):
            nonlocal active
            if endpoint == 'props':
                with lock:
                    active += 1
                    self.assertEqual(active, 1)
                # Yield long enough that the old concurrent implementation overlaps.
                threading.Event().wait(.05)
                with lock:
                    active -= 1
            return ProviderRows()
        with patch.dict('os.environ', {'PARLAY_API_KEY': 'fixture'}), patch('parlay_feed.request_rows', side_effect=get) as calls:
            result = _fetch_parlay('nfl')
        self.assertEqual(calls.call_count, 4)
        self.assertEqual(result['feed_status'], 'FRESH')

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
