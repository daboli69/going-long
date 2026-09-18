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


def request_rows(sport, endpoint, params, key):
    """Retry transient provider overload; never log credentials or request URLs."""
    for attempt in range(3):
        delay = 2 ** (attempt + 1)
        retryable = False
        try:
            response = requests.get(f'https://parlay-api.com/v1/sports/{SPORT_KEYS[sport]}/{endpoint}',
                                    headers={'X-API-Key': key, 'Accept': 'application/json'},
                                    params=params, timeout=(10, 60))
            if response.ok:
                try:
                    rows = response.json()
                except ValueError:
                    raise RuntimeError(f'Parlay {endpoint}: invalid JSON response') from None
                if endpoint == 'live/period_markets' and isinstance(rows, dict):
                    rows = rows.get('results')
                if not isinstance(rows, list):
                    raise RuntimeError(f'Parlay {endpoint}: unexpected response schema')
                return rows
            retryable = response.status_code in (429, 500, 502, 503, 504)
            # Only expose short, redacted diagnostic fields, never an arbitrary body.
            request_id = response.headers.get('x-request-id', 'unknown').replace(key, '[REDACTED]')[:100]
            error = ''
            try:
                body = response.json()
                if isinstance(body, dict):
                    detail = body.get('detail')
                    error = body.get('error') or (detail.get('error') if isinstance(detail, dict) else '')
            except ValueError:
                pass
            error = str(error).replace(key, '[REDACTED]')[:100]
            reason = f'HTTP {response.status_code}; code={error or "unknown"}; request_id={request_id}'
            try:
                delay = max(delay, min(30, float(response.headers.get('Retry-After', 0))))
            except ValueError:
                pass
        except requests.RequestException as exc:
            retryable = isinstance(exc, (requests.Timeout, requests.ConnectionError))
            reason = type(exc).__name__
        if not retryable or attempt == 2:
            raise RuntimeError(f'Parlay {endpoint}: {reason}; attempts={attempt + 1}; previous snapshot retained') from None
        print(f'[parlay] {endpoint}: {reason}; retry {attempt + 2}/3 in {delay:g}s', flush=True)
        time.sleep(delay)


def fetch_parlay(sport):
    """Keep quote timestamps and the last successful generation time on failure."""
    try:
        return _fetch_parlay(sport)
    except RuntimeError as exc:
        from build_pipeline import atomic_json, load_json
        path = ROOT / 'data' / ('nfl_betting.json' if sport == 'nfl' else 'ncaa_lines.json')
        previous = load_json(path)
        previous.update(feed_status='STALE' if previous.get('generated_at') else 'FAILED',
                        refresh_status='FAILED', last_attempt_at=datetime.now(timezone.utc).isoformat(),
                        refresh_error=str(exc))
        previous['source_states'] = {name: ('STALE' if previous.get(field) else 'FAILED')
                                     for name, field in [('odds', 'games_raw'), ('props', 'props'),
                                                         ('derivatives', 'props'), ('periods', 'period_quotes')]}
        atomic_json(path, previous)
        raise


def _fetch_parlay(sport):
    key = os.getenv('PARLAY_API_KEY', '').strip()
    if not key:
        raise RuntimeError('PARLAY_API_KEY is not configured')

    def get(endpoint, params):
        return request_rows(sport, endpoint, params, key)

    with ThreadPoolExecutor(max_workers=3) as executor:
        future = executor.submit(get, 'odds', {'markets': 'h2h,spreads,totals', 'regions': 'us', 'oddsFormat': 'american'})
        period_future = executor.submit(get, 'live/period_markets', {'period': 'all'})
        derivative_keys = [alias for market, aliases in GROUPS.items() if market == 'first_td' or market.endswith(('_1h','_1q')) for alias in aliases]
        rows = get('props', {'markets': ','.join(MARKET_MAP), 'limit': 10000}) if sport == 'nfl' else []
        # The primary request already contains derivatives. Avoid rebuilding the same
        # overloaded props board twice unless its row cap requires a narrower read.
        derivative_future = executor.submit(get, 'props', {'markets': ','.join(derivative_keys), 'limit': 10000}) if sport == 'nfl' and len(rows) >= 10000 else None
        games = future.result()
        try:
            derivative_rows = derivative_future.result() if derivative_future else []
            derivative_status = 'loaded' if sport == 'nfl' else 'not_applicable'
        except RuntimeError as exc:
            print(f'[parlay] derivatives unavailable: {exc}')
            derivative_rows = []
            derivative_status = 'fallback' if any(r.get('market_key') in derivative_keys for r in rows) else 'unavailable'
        try:
            period_rows, period_status = normalize_periods(period_future.result()), 'loaded'
        except RuntimeError as exc:
            print(f'[parlay] periods unavailable: {exc}')
            period_rows, period_status = [], 'unavailable'
    return {'provider': 'parlay', 'sport': sport, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'feed_status': 'FRESH', 'refresh_status': 'FRESH', 'refresh_error': None,
            'last_attempt_at': datetime.now(timezone.utc).isoformat(),
            'source_states': {'odds': 'FRESH', 'props': 'FRESH' if sport == 'nfl' else 'NOT_APPLICABLE',
                              'derivatives': {'loaded': 'FRESH', 'fallback': 'FALLBACK', 'unavailable': 'FAILED',
                                              'not_applicable': 'NOT_APPLICABLE'}[derivative_status],
                              'periods': 'FRESH' if period_status == 'loaded' else 'FAILED'},
            'props': normalize_props(rows + derivative_rows), 'derivative_status': derivative_status, 'games_raw': games, 'odds_status': 'loaded',
            'period_quotes': period_rows, 'period_status': period_status,
            'coverage': {'raw_props': len(rows), 'possibly_truncated': len(rows) >= 10000}}


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
