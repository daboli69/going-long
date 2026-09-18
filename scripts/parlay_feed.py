"""ParlayAPI adapter shared by nightly ingestion. Keys stay in the environment."""
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
GROUPS = json.loads((ROOT / 'config/parlay-markets.json').read_text())
MARKET_MAP = {alias: market for market, aliases in GROUPS.items() for alias in aliases}
SPORT_KEYS = {'nfl': 'americanfootball_nfl', 'ncaa': 'americanfootball_ncaaf'}
NON_RETRYABLE_503 = {'ENDPOINT_DISABLED', 'ASYNCAPI_NOT_LOADED', 'OPENAPI_UNAVAILABLE'}
RETRY_DELAYS = {'DB_NOT_READY': 30, 'PRIMARY_TIER_UNAVAILABLE': 60,
                'PROPS_BOARD_DEGRADED': 5, 'WARMING': 5}


class ProviderRows(list):
    def __init__(self, rows=(), *, truncated=False):
        super().__init__(rows)
        self.truncated = truncated


def numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def stamp(value):
    if numeric(value):
        return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, timezone.utc).isoformat()
    return value or None


def normalize_props(rows, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(rows, list):
        raise ValueError('Unexpected Parlay props payload')
    output = {}
    for r in rows:
        market = MARKET_MAP.get(r.get('market_key'))
        if not market or not r.get('player') or not r.get('bookmaker'):
            continue
        kickoff = r.get('commence_time')
        if kickoff:
            try:
                if datetime.fromisoformat(kickoff.replace('Z', '+00:00')) <= now:
                    continue
            except ValueError:
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
        if key not in output or (p['updatedAt'] or '') > (output[key]['updatedAt'] or ''):
            output[key] = p
    return list(output.values())


def normalize_periods(rows):
    output = {}
    for r in rows:
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
                in_play = datetime.fromisoformat(kickoff.replace('Z','+00:00')) <= datetime.now(timezone.utc)
            except (ValueError, AttributeError):
                in_play = True
            output[key] = dict(r, period_key=period, quoteKey=key, kickoff=kickoff, updatedAt=r.get('updatedAt') or stamp(r.get('last_observed_ms') or r.get('timestamp_ms')), inPlay=in_play)
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


def request_rows(sport, endpoint, params, key):
    """Use one bounded, response-aware retry; never log credentials or request URLs."""
    request_params, collected, provider_truncated = dict(params), [], False
    for page in range(2):  # Provider currently permits offsets only through 10,000.
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
                    if not isinstance(rows, list):
                        raise RuntimeError(f'Parlay {endpoint}: unexpected response schema')
                    break
                code, message = _provider_error(response, key)
                request_id = response.headers.get('x-request-id', 'unknown').replace(key, '[REDACTED]')[:100]
                reason = (f'HTTP {response.status_code}; code={code or "UNKNOWN"}; '
                          f'message={message or "unavailable"}; request_id={request_id}')
                retryable = response.status_code in (429, 500, 502, 504)
                if response.status_code == 503:
                    retryable = code not in NON_RETRYABLE_503 and code != 'INCIDENTS_PARSE_FAILED'
                    delay = RETRY_DELAYS.get(code, 5)
                try:
                    delay = max(delay, min(60, float(response.headers.get('Retry-After', 0))))
                except ValueError:
                    pass
            except requests.RequestException as exc:
                retryable = isinstance(exc, (requests.Timeout, requests.ConnectionError))
                reason = type(exc).__name__
            if not retryable or attempt == 1:
                raise RuntimeError(f'Parlay {endpoint}: {reason}; attempts={attempt + 1}; previous snapshot retained') from None
            print(f'[parlay] stage={endpoint}; {reason}; retry 2/2 in {delay:g}s', flush=True)
            time.sleep(delay)
        collected.extend(rows)
        provider_truncated = provider_truncated or response.headers.get('x-result-truncated', '').lower() == 'true' or bool(response.headers.get('x-result-degraded'))
        if endpoint == 'props' and 'x-result-has-more' not in response.headers and len(rows) >= int(request_params.get('limit', 10000)):
            provider_truncated = True
        has_more = response.headers.get('x-result-has-more', '').lower() == 'true'
        if endpoint != 'props' or not has_more:
            return ProviderRows(collected, truncated=provider_truncated)
        next_offset = response.headers.get('x-next-offset')
        try:
            next_offset = int(next_offset)
        except (TypeError, ValueError):
            return ProviderRows(collected, truncated=True)
        if page == 1 or next_offset > 10000:
            return ProviderRows(collected, truncated=True)
        request_params['offset'] = next_offset
    return ProviderRows(collected, truncated=True)


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
        atomic_json(path, previous)
        raise


def _fetch_parlay(sport, previous=None):
    key = os.getenv('PARLAY_API_KEY', '').strip()
    if not key:
        raise RuntimeError('PARLAY_API_KEY is not configured')

    def get(endpoint, params):
        return request_rows(sport, endpoint, params, key)

    previous = previous or {}
    derivative_markets = {market for market in GROUPS if market == 'first_td' or market.endswith(('_1h', '_1q'))}
    core_keys = [aliases[0] for market, aliases in GROUPS.items() if market not in derivative_markets]
    derivative_keys = [aliases[0] for market, aliases in GROUPS.items() if market in derivative_markets]
    previous_core = [row for row in previous.get('props', []) if row.get('market') not in derivative_markets]
    previous_derivatives = [row for row in previous.get('props', []) if row.get('market') in derivative_markets]
    errors = {}

    def resolve(name, future, fallback):
        try:
            return future.result(), 'FRESH'
        except RuntimeError as exc:
            errors[name] = str(exc)
            print(f'[parlay] stage={name}; unavailable; {exc}', flush=True)
            return fallback, 'STALE' if fallback else 'FAILED'

    with ThreadPoolExecutor(max_workers=4) as executor:
        odds_future = executor.submit(get, 'odds', {'markets': 'h2h,spreads,totals', 'regions': 'us', 'oddsFormat': 'american'})
        period_future = executor.submit(get, 'live/period_markets', {'period': 'all'})
        core_future = executor.submit(get, 'props', {'markets': ','.join(core_keys), 'limit': 10000}) if sport == 'nfl' else None
        derivative_future = executor.submit(get, 'props', {'markets': ','.join(derivative_keys), 'limit': 10000}) if sport == 'nfl' else None
        games, odds_state = resolve('odds', odds_future, previous.get('games_raw', []))
        periods, period_state = resolve('periods', period_future, previous.get('period_quotes', []))
        if sport == 'nfl':
            core_raw, props_state = resolve('props', core_future, previous_core)
            derivative_raw, derivative_state = resolve('derivatives', derivative_future, previous_derivatives)
            if derivative_state == 'FAILED':
                recovered = [row for row in core_raw if MARKET_MAP.get(row.get('market_key')) in derivative_markets]
                if recovered:
                    derivative_raw, derivative_state = recovered, 'FALLBACK'
        else:
            core_raw, derivative_raw = [], []
            props_state = derivative_state = 'NOT_APPLICABLE'

    # Retained rows are already normalized; provider rows are normalized once here.
    rows = []
    for source in (core_raw, derivative_raw):
        rows.extend(source if source and 'quoteKey' in source[0] else normalize_props(source))
    period_rows = periods if periods and 'quoteKey' in periods[0] else normalize_periods(periods)
    required = [odds_state] + ([props_state, derivative_state] if sport == 'nfl' else [])
    fresh = all(state == 'FRESH' for state in required)
    operational = any(state == 'FRESH' for state in (odds_state, props_state, derivative_state, period_state))
    if not operational:
        raise RuntimeError('; '.join(errors.values()) or 'Parlay returned no usable sources')
    now = datetime.now(timezone.utc).isoformat()
    state = 'FRESH' if fresh else 'FALLBACK'
    return {'provider': 'parlay', 'sport': sport, 'generated_at': now,
            'feed_status': state, 'refresh_status': state,
            'refresh_error': '; '.join(f'{name}: {error}' for name, error in errors.items()) or None,
            'source_errors': errors, 'last_attempt_at': now,
            'last_fresh_at': now if fresh else previous.get('last_fresh_at') or (previous.get('generated_at') if previous.get('feed_status') == 'FRESH' else None),
            'source_states': {'odds': odds_state, 'props': props_state,
                              'derivatives': derivative_state, 'periods': period_state},
            'props': rows, 'derivative_status': derivative_state.lower(),
            'games_raw': games, 'odds_status': odds_state.lower(),
            'period_quotes': period_rows, 'period_status': period_state.lower(),
            'coverage': {'raw_props': len(core_raw), 'derivative_props': len(derivative_raw),
                         'possibly_truncated': bool(getattr(core_raw, 'truncated', len(core_raw) >= 10000)
                                                    or getattr(derivative_raw, 'truncated', len(derivative_raw) >= 10000))}}


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
