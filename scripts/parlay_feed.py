"""ParlayAPI adapter shared by nightly ingestion. Keys stay in the environment."""
import json
import math
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from eligibility import _age_hours

ROOT = Path(__file__).resolve().parents[1]
GROUPS = json.loads((ROOT / 'config/parlay-markets.json').read_text())
MARKET_MAP = {alias: market for market, aliases in GROUPS.items() for alias in aliases}
SPORT_KEYS = {'nfl': 'americanfootball_nfl', 'ncaa': 'americanfootball_ncaaf'}
NON_RETRYABLE_503 = {'ENDPOINT_DISABLED', 'ASYNCAPI_NOT_LOADED', 'OPENAPI_UNAVAILABLE'}
RETRY_DELAYS = {'DB_NOT_READY': 30, 'PRIMARY_TIER_UNAVAILABLE': 60,
                'PROPS_BOARD_DEGRADED': 5, 'PROPS_TEMPORARILY_BUSY': 5, 'WARMING': 5}


def retry_after_seconds(value, now=None):
    """RFC Retry-After supports seconds or HTTP-date; never sleep NaN/infinity."""
    try:
        delay = float(value)
        return max(0, min(60, delay)) if math.isfinite(delay) else 0
    except (TypeError, ValueError):
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return 0
            return max(0, min(60, (date - (now or datetime.now(timezone.utc))).total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0


def quote_time(value):
    try:
        if _age_hours(value, datetime.now(timezone.utc)) is None:
            return 0
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return date.timestamp() if date.tzinfo else 0
    except (TypeError, ValueError, AttributeError, OverflowError):
        return 0


class ProviderRows(list):
    def __init__(self, rows=(), *, truncated=False, diagnostics=()):
        super().__init__(rows)
        self.truncated = truncated
        self.diagnostics = list(diagnostics)


def props_query_plan(previous_rows, partitions=2):
    """Balance a fixed, explicitly configured number of requests.

    Counts are planning estimates only; response headers still decide completeness.
    Retain the legacy split for small/unknown boards. Above 80% of the serving
    cap, distribute whole markets across disjoint bins with growth headroom.
    """
    if partitions != 'markets' and (type(partitions) is not int or partitions not in (2, 3, 4)):
        raise ValueError('Props query partitions must be 2, 3 or 4')
    derivatives = {market for market in GROUPS if market == 'first_td' or market.endswith(('_1h', '_1q'))}
    original = [[market for market in GROUPS if market not in derivatives],
                [market for market in GROUPS if market in derivatives]]
    if partitions == 'markets':
        # Explicitly approved credit budget: narrow high-volume main markets;
        # retain the small derivative board rather than pay for empty families.
        return [[market] for market in original[0]] + [original[1]]
    counts = Counter(row.get('market') for row in previous_rows if isinstance(row, dict)
                     and isinstance(row.get('market'), str) and row['market'] in GROUPS)
    weights = {market: max(1, counts[market]) for market in GROUPS}
    load = lambda group: sum(weights[market] for market in group)
    if partitions == 2 and max(map(load, original)) <= 8000:
        return original
    groups, loads = [[] for _ in range(partitions)], [0] * partitions
    for market in sorted(GROUPS, key=lambda market: (-weights[market], market)):
        index = min(range(partitions), key=lambda index: loads[index])
        groups[index].append(market)
        loads[index] += weights[market]
    return groups if partitions > 2 or max(loads) < max(map(load, original)) else original


def family_state(markets, groups, states):
    """A mixed query failure affects every family requested in that query."""
    rank = {'FRESH': 0, 'FALLBACK': 1, 'DEGRADED': 2, 'STALE': 3, 'FAILED': 4}
    return max((state for group, state in zip(groups, states) if markets.intersection(group)), key=rank.get)


def numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def valid_string_fields(row, fields):
    return all(row.get(name) is None or isinstance(row[name], str) for name in fields)


def stamp(value):
    if numeric(value):
        try:
            return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        return value if _age_hours(value, datetime.now(timezone.utc)) is not None else None
    return None


def normalize_props(rows, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(rows, list):
        raise ValueError('Unexpected Parlay props payload')
    output = {}
    for r in rows:
        if not isinstance(r, dict) or not valid_string_fields(r, ('market_key', 'player', 'bookmaker')):
            continue
        market = MARKET_MAP.get(r.get('market_key'))
        if not market or not r.get('player') or not r.get('bookmaker'):
            continue
        kickoff = r.get('commence_time')
        if kickoff:
            try:
                if _age_hours(kickoff, now) is None:
                    continue
                date = datetime.fromisoformat(kickoff.replace('Z', '+00:00'))
                if date.tzinfo is None or date <= now:
                    continue
            except (ValueError, TypeError, AttributeError, OverflowError):
                continue
        line = .5 if market in ('atd', 'first_td') and r.get('line') in (None, 0) else r.get('line')
        if not numeric(line):
            continue
        event_id = r.get('canonical_event_id') or r.get('event_id') or f"player:{r.get('game_date', 'unknown')}:{r['player']}"
        key = json.dumps([event_id, r['bookmaker'], market, r['player'], line], separators=(',', ':'))
        dfs = bool(r.get('is_dfs_flat_payout') or r.get('dfs_normalized') or r['bookmaker'] in {'prizepicks', 'betr', 'pick6', 'sleeper', 'underdog'})
        odds = lambda v: v if not dfs and numeric(v) and abs(v) >= 100 else None
        p = {'quoteKey': key, 'eventId': event_id, 'player': r['player'], 'team': '', 'opp': '',
             'homeName': r.get('home_team') or '', 'awayName': r.get('away_team') or '', 'market': market,
             'line': line, 'book': r.get('bookmaker_title') or r['bookmaker'], 'bookKey': r['bookmaker'],
             'overOdds': odds(r.get('over_price')), 'underOdds': odds(r.get('under_price')),
             'source': 'parlay', 'updatedAt': stamp(r.get('last_update')), 'kickoff': kickoff,
             'dfs': dfs, 'gameDate': r.get('game_date')}
        if key not in output or quote_time(p['updatedAt']) > quote_time(output[key]['updatedAt']):
            output[key] = p
    return list(output.values())


def normalize_periods(rows):
    output = {}
    for r in rows:
        if not isinstance(r, dict) or not valid_string_fields(r, ('match_id', 'source')):
            continue
        period = str(r.get('period_key', '')).upper()
        if period not in ('Q1', '1H') or not r.get('match_id') or not r.get('source'):
            continue
        if r.get('market') not in ('spread', 'total', 'team_total', 'h2h') or not numeric(r.get('price')) or abs(r['price']) < 100:
            continue
        if r['market'] != 'h2h' and not numeric(r.get('line')):
            continue
        if r.get('side') not in ('home', 'away', 'over', 'under', 'draw'):
            continue
        if r['market'] == 'team_total' and r.get('team') not in ('home', 'away'):
            continue
        key = json.dumps([r['match_id'], r['source'], period, r['market'], r.get('team'), r['side'], r.get('line')], separators=(',', ':'))
        old = output.get(key)
        if old is None or (numeric(r.get('age_seconds')) and (not numeric(old.get('age_seconds')) or r['age_seconds'] < old['age_seconds'])):
            kickoff = r.get('kickoff') or r.get('commence_time')
            try:
                if _age_hours(kickoff, datetime.now(timezone.utc)) is None:
                    raise ValueError('Invalid period kickoff')
                in_play = datetime.fromisoformat(kickoff.replace('Z','+00:00')) <= datetime.now(timezone.utc)
            except (ValueError, TypeError, AttributeError, OverflowError):
                in_play = True
            output[key] = dict(r, period_key=period, quoteKey=key, kickoff=kickoff, updatedAt=stamp(r.get('updatedAt')) or stamp(r.get('last_observed_ms') or r.get('timestamp_ms')), inPlay=in_play)
    result = list(output.values())
    three_way = {(q['match_id'],q['source'],q['period_key']) for q in result if q['market']=='h2h' and q['side']=='draw'}
    for q in result:
        q['threeWay'] = (q['match_id'],q['source'],q['period_key']) in three_way
    return result


def _provider_error(response, key):
    """Return a short structured provider diagnostic without echoing credentials."""
    code, message = '', ''
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get('detail')
            nested = detail if isinstance(detail, dict) else {}
            code = body.get('code') or body.get('error') or nested.get('code') or nested.get('error') or body.get('status') or ''
            message = body.get('message') or nested.get('message') or (detail if isinstance(detail, str) else '')
    except ValueError:
        pass
    clean = lambda value: str(value).replace(key, '[REDACTED]').replace('\n', ' ')[:160]
    return clean(code).upper(), clean(message)


def request_rows(sport, endpoint, params, key, *, max_pages=2):
    """Use one bounded, response-aware retry; never log credentials or request URLs."""
    request_params, collected, provider_truncated = dict(params), [], False
    diagnostics = []
    def finish(truncated):
        return ProviderRows(collected, truncated=truncated, diagnostics=diagnostics)
    for page in range(max_pages):  # Provider currently permits offsets only through 10,000.
        for attempt in range(2):
            delay, retryable = 2, False
            try:
                response = requests.get(f'https://parlay-api.com/v1/sports/{SPORT_KEYS[sport]}/{endpoint}',
                                        headers={'X-API-Key': key, 'Accept': 'application/json'},
                                        params=request_params, timeout=(10, 60))
                if response.ok:
                    try:
                        rows = response.json()
                    except ValueError:
                        raise RuntimeError(f'Parlay {endpoint}: invalid JSON response') from None
                    if endpoint == 'live/period_markets' and isinstance(rows, dict):
                        rows = rows.get('results')
                    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                        raise RuntimeError(f'Parlay {endpoint}: unexpected response schema')
                    if endpoint == 'odds' and not valid_odds_rows(rows):
                        raise RuntimeError('Parlay odds: unexpected nested response schema')
                    fields = ('market_key', 'player', 'bookmaker') if endpoint == 'props' else ('match_id', 'source') if endpoint == 'live/period_markets' else ()
                    if any(not valid_string_fields(row, fields) for row in rows):
                        raise RuntimeError(f'Parlay {endpoint}: unexpected identity schema')
                    break
                code, message = _provider_error(response, key)
                request_id = response.headers.get('x-request-id', 'unknown').replace(key, '[REDACTED]')[:100]
                reason = (f'HTTP {response.status_code}; code={code or "UNKNOWN"}; '
                          f'message={message or "unavailable"}; request_id={request_id}')
                retryable = response.status_code in (429, 500, 502, 504)
                if response.status_code == 503:
                    retryable = code not in NON_RETRYABLE_503 and code != 'INCIDENTS_PARSE_FAILED'
                    delay = RETRY_DELAYS.get(code, 5)
                delay = max(delay, retry_after_seconds(response.headers.get('Retry-After')))
            except requests.RequestException as exc:
                retryable = isinstance(exc, (requests.Timeout, requests.ConnectionError))
                reason = type(exc).__name__
            if not retryable or attempt == 1:
                raise RuntimeError(f'Parlay {endpoint}: {reason}; attempts={attempt + 1}; previous snapshot retained') from None
            print(f'[parlay] stage={endpoint}; {reason}; retry 2/2 in {delay:g}s', flush=True)
            time.sleep(delay)
        collected.extend(rows)
        truncated = response.headers.get('x-result-truncated', '').strip().lower() == 'true'
        degraded = response.headers.get('x-result-degraded', '').strip()
        degraded = degraded if degraded.lower() not in ('', 'false', '0') else ''
        provider_truncated = provider_truncated or truncated or bool(degraded)
        if truncated or degraded:
            # Only allowlisted headers; never persist the response body, URL or key.
            clean = lambda value, limit=240: ' '.join(str(value).replace(key, '[REDACTED]').split())[:limit]
            diagnostics.append({
                'offset': request_params.get('offset', 0), 'rows': len(rows),
                'truncated': truncated, 'degraded_books': clean(degraded),
                'hint': clean(response.headers.get('x-result-truncated-hint', ''), 2048),
                'request_id': clean(response.headers.get('x-request-id', 'unknown')),
            })
        if endpoint == 'props' and 'x-result-has-more' not in response.headers and len(rows) >= int(request_params.get('limit', 10000)):
            provider_truncated = True
            diagnostics.append({'reason': 'Full page without pagination metadata'})
        has_more = response.headers.get('x-result-has-more', '').strip().lower() == 'true'
        # Internal per-source truncation is explicitly not recoverable by offset.
        # Do not spend another page request downloading another sample of that cap.
        if truncated or endpoint != 'props' or not has_more:
            return finish(provider_truncated)
        next_offset = response.headers.get('x-next-offset')
        try:
            next_offset = int(next_offset)
        except (TypeError, ValueError):
            diagnostics.append({'reason': 'Missing or malformed continuation offset'})
            return finish(True)
        if next_offset <= request_params.get('offset', 0) or page == max_pages - 1 or next_offset > 10000:
            diagnostics.append({'reason': 'Continuation exceeds bounded pagination or does not advance'})
            return finish(True)
        request_params['offset'] = next_offset
    return finish(True)


def valid_odds_rows(rows):
    """Reject malformed containers before a source can be labelled healthy."""
    def children(row, name):
        value = row.get(name, [])
        return value if isinstance(value, list) and all(isinstance(item, dict) for item in value) else None
    for event in rows:
        if not valid_string_fields(event, ('id', 'canonical_event_id', 'home_team', 'away_team')):
            return False
        books = children(event, 'bookmakers')
        if books is None:
            return False
        for book in books:
            if not valid_string_fields(book, ('key',)):
                return False
            markets = children(book, 'markets')
            if markets is None:
                return False
            if any(('key' in market and not isinstance(market['key'], str)) or children(market, 'outcomes') is None for market in markets):
                return False
            if any(not valid_string_fields(outcome, ('name', 'description')) for market in markets for outcome in market.get('outcomes', [])):
                return False
    return True


def fetch_parlay(sport):
    """Keep quote timestamps and the last successful generation time on failure."""
    from build_pipeline import atomic_json, load_json
    path = ROOT / 'data' / ('nfl_betting.json' if sport == 'nfl' else 'ncaa_lines.json')
    previous = load_json(path)
    try:
        return _fetch_parlay(sport, previous)
    except RuntimeError as exc:
        previous.update(feed_status='STALE' if previous.get('generated_at') else 'FAILED',
                        refresh_status='FAILED', last_attempt_at=datetime.now(timezone.utc).isoformat(),
                        refresh_error=str(exc))
        previous['source_states'] = {name: ('STALE' if previous.get(field) else 'FAILED')
                                     for name, field in [('odds', 'games_raw'), ('props', 'props'),
                                                         ('derivatives', 'props'), ('periods', 'period_quotes')]}
        if sport == 'ncaa':
            previous['source_states'].update(props='NOT_APPLICABLE', derivatives='NOT_APPLICABLE')
        atomic_json(path, previous)
        raise


def _fetch_parlay(sport, previous=None):
    key = os.getenv('PARLAY_API_KEY', '').strip()
    if not key:
        raise RuntimeError('PARLAY_API_KEY is not configured')

    def get(endpoint, params):
        if endpoint == 'props' and configured_partitions == 'markets':
            return request_rows(sport, endpoint, params, key, max_pages=1)
        return request_rows(sport, endpoint, params, key)

    previous = previous if isinstance(previous, dict) else {}
    previous_observed = previous.get('source_observed_at')
    previous_observed = previous_observed if isinstance(previous_observed, dict) else {}
    derivative_markets = {market for market in GROUPS if market == 'first_td' or market.endswith(('_1h', '_1q'))}
    # Increasing this consumes more included/metered credits; default stays two.
    configured_partitions = os.getenv('PARLAY_PROPS_PARTITIONS', '2')
    if configured_partitions not in ('2', '3', '4', 'markets'):
        raise RuntimeError('PARLAY_PROPS_PARTITIONS must be 2, 3, 4 or markets')
    query_groups = props_query_plan(previous.get('props', []), configured_partitions if configured_partitions == 'markets' else int(configured_partitions))
    mixed_queries = any(set(group).intersection(derivative_markets) and set(group) - derivative_markets
                        for group in query_groups)
    query_names = ([f'props_partition_{i+1}' for i in range(len(query_groups))]
                   if mixed_queries or len(query_groups) != 2 else ['props', 'derivatives'])
    query_keys = [[GROUPS[market][0] for market in group] for group in query_groups]
    previous_groups = [[row for row in previous.get('props', []) if row.get('market') in group]
                       for group in query_groups]
    errors = {}

    def resolve(name, future, fallback):
        try:
            rows = future.result()
            if getattr(rows, 'truncated', False):
                errors[name] = 'Provider returned incomplete/degraded coverage; available quotes retained'
                details = getattr(rows, 'diagnostics', [])
                if details:
                    errors[name] += '; ' + json.dumps(details, separators=(',', ':'))
                print(f'[parlay] stage={name}; {errors[name]}', flush=True)
                return rows, 'DEGRADED'
            return rows, 'FRESH'
        except RuntimeError as exc:
            errors[name] = str(exc)
            print(f'[parlay] stage={name}; unavailable; {exc}', flush=True)
            return fallback, 'STALE' if fallback else 'FAILED'

    with ThreadPoolExecutor(max_workers=4) as executor:
        odds_future = executor.submit(get, 'odds', {'markets': 'h2h,spreads,totals', 'regions': 'us', 'oddsFormat': 'american'})
        period_future = executor.submit(get, 'live/period_markets', {'period': 'all'})
        core_future = executor.submit(get, 'props', {'markets': ','.join(query_keys[0]), 'limit': 10000}) if sport == 'nfl' else None
        games, odds_state = resolve('odds', odds_future, previous.get('games_raw', []))
        periods, period_state = resolve('periods', period_future, previous.get('period_quotes', []))
        if sport == 'nfl':
            core_raw, first_state = resolve(query_names[0], core_future, previous_groups[0])
            # These share the provider's expensive props-board backend. Serialize
            # them without adding requests, retries or dropping market families.
            query_rows, query_states = [core_raw], [first_state]
            for index in range(1, len(query_groups)):
                future = executor.submit(get, 'props', {'markets': ','.join(query_keys[index]), 'limit': 10000})
                source_rows, source_state = resolve(query_names[index], future, previous_groups[index])
                query_rows.append(source_rows)
                query_states.append(source_state)
            props_state = family_state(set(GROUPS) - derivative_markets, query_groups, query_states)
            derivative_state = family_state(derivative_markets, query_groups, query_states)
            if len(query_groups) == 2 and derivative_state == 'FAILED' and not set(query_groups[0]).intersection(derivative_markets):
                recovered = [row for row in core_raw if MARKET_MAP.get(row.get('market_key')) in derivative_markets]
                if recovered:
                    query_rows[1], derivative_state = recovered, 'FALLBACK'
        else:
            query_rows, query_states = [], []
            props_state = derivative_state = 'NOT_APPLICABLE'

    # Retained rows are already normalized; provider rows are normalized once here.
    rows = []
    for source in query_rows:
        rows.extend(source if source and 'quoteKey' in source[0] else normalize_props(source))
    period_rows = periods if periods and 'quoteKey' in periods[0] else normalize_periods(periods)
    required = [odds_state] + ([props_state, derivative_state] if sport == 'nfl' else [])
    fresh = all(state == 'FRESH' for state in required) and not errors
    operational = any(state in ('FRESH', 'DEGRADED') for state in (odds_state, props_state, derivative_state, period_state))
    if not operational:
        raise RuntimeError('; '.join(errors.values()) or 'Parlay returned no usable sources')
    now = datetime.now(timezone.utc).isoformat()
    state = 'FRESH' if fresh else 'FALLBACK'
    raw_markets = [MARKET_MAP.get(row.get('market_key')) or row.get('market')
                   for source in query_rows for row in source]
    return {'provider': 'parlay', 'sport': sport, 'generated_at': now,
            'feed_status': state, 'refresh_status': state,
            'refresh_error': '; '.join(f'{name}: {error}' for name, error in errors.items()) or None,
            'source_errors': errors, 'last_attempt_at': now,
            'last_fresh_at': now if fresh else previous.get('last_fresh_at') or (previous.get('generated_at') if previous.get('feed_status') == 'FRESH' else None),
            'source_states': {'odds': odds_state, 'props': props_state,
                              'derivatives': derivative_state, 'periods': period_state},
            'source_observed_at': {name: now if source in ('FRESH', 'DEGRADED') else previous_observed.get(name)
                                   for name, source in (('odds', odds_state), ('props', props_state), ('derivatives', derivative_state), ('periods', period_state))},
            'props': rows, 'derivative_status': derivative_state.lower(),
            'games_raw': games, 'odds_status': odds_state.lower(),
            'period_quotes': period_rows, 'period_status': period_state.lower(),
            'coverage': {'raw_props': sum(market not in derivative_markets for market in raw_markets),
                         'derivative_props': sum(market in derivative_markets for market in raw_markets),
                         'query_partitions': [{'name': name, 'markets': group, 'rows': len(source), 'state': source_state}
                                              for name, group, source, source_state in zip(query_names, query_groups, query_rows, query_states)],
                         'possibly_truncated': any(getattr(source, 'truncated', len(source) >= 10000)
                                                   for source in query_rows)}}


def refresh():
    from build_pipeline import atomic_json, load_json
    for sport, name in [('nfl', 'nfl_betting.json'), ('ncaa', 'ncaa_lines.json')]:
        fresh = fetch_parlay(sport)
        path = ROOT / 'data' / name
        payload = load_json(path)
        payload.update(fresh)
        payload.pop('props_raw', None)
        payload['has_live_odds'] = bool(fresh['props'] or fresh['games_raw'])
        atomic_json(path, payload)
        print(f"{sport}: {len(fresh['props'])} props, {len(fresh['games_raw'])} game events")


if __name__ == '__main__':
    refresh()
