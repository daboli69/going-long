"""Finite, private The Odds API historical archive. Never fetches current odds.

The lifetime ledger does not reset monthly. Unknown charges stay reserved;
completed requests are immutable and reusable without a subscription/key.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
HOST = 'https://api.the-odds-api.com'
BOOKS = 'pinnacle,draftkings,fanduel,betmgm,williamhill_us,betonlineag,bovada,lowvig,betrivers,fanatics'
PROPS = 'player_pass_yds,player_rush_yds,player_reception_yds,player_receptions,player_pass_tds,player_anytime_td'
ALLOWED = re.compile(r'^/v4/historical/sports/americanfootball_(?:nfl|ncaaf)/(?:odds|events|events/[a-zA-Z0-9_-]{1,80}/odds)$')


def iso(value):
    if not isinstance(value, str):
        raise ValueError('Aware ISO timestamp required')
    date = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if date.tzinfo is None:
        raise ValueError('Aware ISO timestamp required')
    return date.astimezone(timezone.utc)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def default_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'GOING/private/odds-history'


class Archive:
    def __init__(self, root, *, limit=20000, fetch=requests.get):
        if not 1 <= limit <= 20000:
            raise ValueError('Historical lifetime ceiling is 20,000 credits')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'raw').mkdir(exist_ok=True)
        self.db = self.root / 'index.sqlite3'
        self.limit, self.fetch = limit, fetch
        with closing(self.connect()) as db, db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS control(key TEXT PRIMARY KEY,value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS pulls(id TEXT PRIMARY KEY,path TEXT,params TEXT,
                charge INTEGER,state TEXT,sha256 TEXT,snapshot_at TEXT,captured_at TEXT);
              CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY,pull_id TEXT,event_id TEXT,
                kickoff TEXT,home TEXT,away TEXT,book TEXT,market TEXT,player TEXT,side TEXT,
                line REAL,price REAL,quote_at TEXT,snapshot_at TEXT);
              CREATE INDEX IF NOT EXISTS lookup ON quotes(event_id,market,player,book,snapshot_at);
            ''')

    def connect(self):
        return sqlite3.connect(self.db, timeout=60)

    def status(self):
        with closing(self.connect()) as db:
            return {'schema': 'going-historical-odds-v1', 'provider': 'the-odds-api',
                    'historical_only': True, 'lifetime_limit': self.limit,
                    'credits_charged_or_reserved': db.execute('SELECT COALESCE(SUM(charge),0) FROM pulls').fetchone()[0],
                    'requests': dict(db.execute('SELECT state,COUNT(*) FROM pulls GROUP BY state')),
                    'quotes': db.execute('SELECT COUNT(*) FROM quotes').fetchone()[0],
                    'events': db.execute('SELECT COUNT(DISTINCT event_id) FROM quotes').fetchone()[0],
                    'markets': dict(db.execute('SELECT market,COUNT(*) FROM quotes GROUP BY market')),
                    'books': dict(db.execute('SELECT book,COUNT(*) FROM quotes GROUP BY book')),
                    'first_snapshot': db.execute('SELECT MIN(snapshot_at) FROM quotes').fetchone()[0],
                    'last_snapshot': db.execute('SELECT MAX(snapshot_at) FROM quotes').fetchone()[0],
                    'raw_compressed_bytes': sum(p.stat().st_size for p in (self.root / 'raw').glob('*.gz')),
                    'control': dict(db.execute('SELECT key,value FROM control'))}

    def request(self, path, params, max_cost, key):
        if not ALLOWED.fullmatch(path) or 'apiKey' in params or not 1 <= max_cost <= 300:
            raise ValueError('Only bounded historical endpoints are permitted')
        if set(params) - {'date', 'bookmakers', 'markets', 'oddsFormat'}:
            raise ValueError('Unsupported historical request parameters')
        if path.endswith('/odds'):
            markets = params.get('markets', 'h2h').split(',')
            books = params.get('bookmakers', BOOKS).split(',')
            if (not set(markets) <= set(PROPS.split(',') + ['h2h', 'spreads', 'totals'])
                    or not set(books) <= set(BOOKS.split(',')) or len(books) > 10
                    or max_cost < 10 * len(set(markets))):
                raise ValueError('Reservation must cover the full historical request cost')
        requested = iso(params.get('date'))
        if requested >= datetime.now(timezone.utc) - timedelta(hours=24):
            raise ValueError('Historical requests must be at least 24 hours old')
        params = {**params, 'date': requested.isoformat(timespec='seconds').replace('+00:00', 'Z')}
        identity = hashlib.sha256(encoded([path, params])).hexdigest()
        archive_path = self.root / 'raw' / (identity + '.json.gz')
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT state,sha256 FROM pulls WHERE id=?', (identity,)).fetchone()
            if old:
                if old[0] != 'complete':
                    return None  # Ambiguous/failed requests are not silently repurchased.
                raw = gzip.decompress(archive_path.read_bytes())
                if hashlib.sha256(raw).hexdigest() != old[1]:
                    raise RuntimeError('Archive checksum failed; no replacement purchase attempted')
                return json.loads(raw)
            controls = dict(db.execute('SELECT key,value FROM control'))
            if controls.get('stopped'):
                raise RuntimeError('Historical importer stopped: ' + controls['stopped'])
            spent = db.execute('SELECT COALESCE(SUM(charge),0) FROM pulls').fetchone()[0]
            pending = db.execute("SELECT COALESCE(SUM(charge),0) FROM pulls WHERE state!='complete'").fetchone()[0]
            remaining = min(self.limit - spent, int(controls.get('provider_remaining', 20000)) - pending)
            if max_cost > remaining or int(controls.get('provider_used', 0)) + pending + max_cost > 20000:
                return None
            captured = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO pulls VALUES(?,?,?,?,?,?,?,?)',
                       (identity, path, encoded(params).decode(), max_cost, 'reserved', None, None, captured))
        try:
            response = self.fetch(HOST + path, params={**params, 'apiKey': key}, timeout=(10, 60), allow_redirects=False)
        except requests.RequestException:
            self.fail(identity, 'unknown', 'Transport failure; charge remains reserved')
            raise RuntimeError('Historical transport failed; charge reserved, key and URL withheld') from None
        if response.status_code != 200:
            # Persist only redacted structured errors, never response/request URLs.
            try:
                detail = response.json()
                detail = json.loads(json.dumps(detail).replace(key, '[REDACTED]'))
            except (ValueError, TypeError):
                detail = {'error': 'Non-JSON provider error'}
            (self.root / (identity + '.error.json')).write_text(json.dumps({'http': response.status_code, 'detail': detail}, indent=2))
            # Missing historical events are genuine coverage gaps. Continue only
            # when authoritative quota headers prove this rejection cost zero.
            try:
                charge, remaining, used = (int(response.headers[name]) for name in
                    ('x-requests-last', 'x-requests-remaining', 'x-requests-used'))
                with closing(self.connect()) as db, db:
                    old_used = db.execute("SELECT value FROM control WHERE key='provider_used'").fetchone()
                    if (response.status_code == 404 and detail.get('error_code') == 'EVENT_NOT_FOUND'
                            and charge == 0 and old_used and used == int(old_used[0]) and remaining >= 0):
                        db.execute("UPDATE pulls SET charge=0,state='unavailable-uncharged' WHERE id=?", (identity,))
                        db.execute("INSERT OR REPLACE INTO control VALUES('provider_remaining',?)", (str(remaining),))
                        return None
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
            self.fail(identity, 'failed', f'Provider HTTP {response.status_code}; inspect account before resuming')
            raise RuntimeError(f'Historical provider HTTP {response.status_code}; stopped without logging credentials')
        try:
            body = response.json()
            snapshot = iso(body['timestamp'])
            if snapshot > requested or not isinstance(body['data'], (dict, list)):
                raise ValueError('Invalid snapshot')
            raw = encoded(body)
            if key and key.encode() in raw:
                raise ValueError('Credential in response')
            charge, remaining, used = (int(response.headers[name]) for name in
                ('x-requests-last', 'x-requests-remaining', 'x-requests-used'))
            if min(charge, remaining, used) < 0 or charge > max_cost or used > 20000:
                raise ValueError('Unexpected credit accounting')
        except (ValueError, TypeError, KeyError):
            self.fail(identity, 'invalid', 'Response or quota verification failed')
            raise RuntimeError('Historical response/quota verification failed; stopped') from None
        digest = hashlib.sha256(raw).hexdigest()
        temporary = archive_path.with_suffix('.tmp')
        temporary.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
        temporary.replace(archive_path)
        quotes = normalize(body, identity)
        with closing(self.connect()) as db, db:
            old_used = db.execute("SELECT value FROM control WHERE key='provider_used'").fetchone()
            if old_used and used < int(old_used[0]):
                db.execute("INSERT OR REPLACE INTO control VALUES('stopped','Quota reset detected; lifetime import does not renew')")
            db.execute("UPDATE pulls SET charge=?,state='complete',sha256=?,snapshot_at=? WHERE id=?",
                       (charge, digest, snapshot.isoformat(), identity))
            db.executemany('INSERT OR IGNORE INTO quotes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', quotes)
            db.executemany('INSERT OR REPLACE INTO control VALUES(?,?)',
                           [('provider_remaining', str(remaining)), ('provider_used', str(used))])
        return body

    def fail(self, identity, state, reason):
        with closing(self.connect()) as db, db:
            db.execute('UPDATE pulls SET state=? WHERE id=?', (state, identity))
            db.execute("INSERT OR REPLACE INTO control VALUES('stopped',?)", (reason,))

    def quotes(self, *, event_id=None, market=None, limit=1000):
        where, args = [], []
        for field, value in [('event_id', event_id), ('market', market)]:
            if value:
                where.append(field + '=?'); args.append(value)
        with closing(self.connect()) as db:
            db.row_factory = sqlite3.Row
            sql = 'SELECT * FROM quotes' + (' WHERE ' + ' AND '.join(where) if where else '')
            return [dict(row) for row in db.execute(sql + ' ORDER BY snapshot_at DESC LIMIT ?', args + [min(10000, max(1, limit))])]


def normalize(body, pull_id):
    """Keep pregame observations only; never pair lines across snapshots/books."""
    snapshot = iso(body['timestamp'])
    events = body['data'] if isinstance(body['data'], list) else [body['data']]
    result = {}
    for event in events:
        if not isinstance(event, dict) or not event.get('id'):
            continue
        try:
            kickoff = iso(event['commence_time'])
        except (KeyError, TypeError, ValueError):
            continue
        if kickoff <= snapshot:
            continue
        if not all(isinstance(event.get(k), str) and event[k] for k in ('id', 'home_team', 'away_team')):
            continue
        books = event.get('bookmakers')
        for book in books if isinstance(books, list) else []:
            if not isinstance(book, dict) or not isinstance(book.get('key'), str): continue
            markets = book.get('markets')
            for market in markets if isinstance(markets, list) else []:
                if not isinstance(market, dict) or not isinstance(market.get('key'), str): continue
                try:
                    stamp = iso(market.get('last_update') or book['last_update'])
                except (KeyError, TypeError, ValueError):
                    continue
                if stamp > snapshot:
                    continue
                outcomes = market.get('outcomes')
                for outcome in outcomes if isinstance(outcomes, list) else []:
                    if not isinstance(outcome, dict) or not isinstance(outcome.get('name'), str): continue
                    if outcome.get('description') is not None and not isinstance(outcome['description'], str): continue
                    price, line = outcome.get('price'), outcome.get('point')
                    if isinstance(price, bool) or not isinstance(price, (float, int)) or not math.isfinite(price) or abs(price) < 100:
                        continue
                    if line is not None and (isinstance(line, bool) or not isinstance(line, (float, int)) or not math.isfinite(line)):
                        continue
                    identity = [pull_id, event['id'], book['key'], market['key'], outcome.get('description'), outcome.get('name'), line]
                    quote_id = hashlib.sha256(encoded(identity)).hexdigest()
                    row = (quote_id, pull_id, event['id'], kickoff.isoformat(), event.get('home_team'), event.get('away_team'),
                           book['key'], market['key'], outcome.get('description'), outcome.get('name'), line, price,
                           stamp.isoformat(), snapshot.isoformat())
                    if quote_id not in result or row[-2] > result[quote_id][-2]:
                        result[quote_id] = row
    return list(result.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'sample', 'query'])
    parser.add_argument('--root', type=Path, default=default_root())
    parser.add_argument('--market')
    args = parser.parse_args()
    archive = Archive(args.root)
    if args.command == 'sample':
        key = json.loads((args.root / 'credential.json').read_text())['api_key']
        archive.request('/v4/historical/sports/americanfootball_nfl/events', {'date': '2025-10-12T16:00:00Z'}, 1, key)
    print(json.dumps(archive.quotes(market=args.market) if args.command == 'query' else archive.status(), indent=2))


if __name__ == '__main__':
    main()
