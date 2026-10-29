"""Kalshi NBA game-winner markets as the market benchmark (public market-data endpoints, no key, no orders).

Kalshi is a CFTC-regulated prediction market, so a contract price is an implied probability. It is used only as a scoring benchmark and as the
partner in the encompassing test, never as a model feature. No API key is used or stored: every endpoint here is unauthenticated market data.

Per game we keep, from hourly candles with their own timestamps: the bid/ask midpoint of the home-team contract and of the away-team contract at
(a) the model cutoff (tipoff minus 60 minutes) and (b) the last candle at or before tipoff, plus spread, volume and the exact candle time.
Raw responses are archived with SHA-256 and retrieval time.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import re
import time
from pathlib import Path
import pandas as pd
import requests
from . import data
from .avail_study import OUT

BASE = 'https://api.elections.kalshi.com/trade-api/v2'
HEAD = {'Accept': 'application/json', 'User-Agent': 'NBA-Ensemble-Local-Research/1.0'}
SERIES = 'KXNBAGAME'
RAW = OUT / 'kalshi_raw'
# canonical (ESPN) abbreviation -> Kalshi three-letter code
CODE = {'ATL': 'ATL', 'BOS': 'BOS', 'BKN': 'BKN', 'CHA': 'CHA', 'CHI': 'CHI', 'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN', 'DET': 'DET',
        'GS': 'GSW', 'HOU': 'HOU', 'IND': 'IND', 'LAC': 'LAC', 'LAL': 'LAL', 'MEM': 'MEM', 'MIA': 'MIA', 'MIL': 'MIL', 'MIN': 'MIN',
        'NO': 'NOP', 'NY': 'NYK', 'OKC': 'OKC', 'ORL': 'ORL', 'PHI': 'PHI', 'PHX': 'PHX', 'POR': 'POR', 'SAC': 'SAC', 'SA': 'SAS',
        'TOR': 'TOR', 'UTAH': 'UTA', 'WSH': 'WAS'}
MONTHS = {m: i + 1 for i, m in enumerate(['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'])}
_session = requests.Session()


def get(path, **params):
    for k in range(5):
        r = _session.get(BASE + path, params=params, headers=HEAD, timeout=40)
        if r.status_code == 429:
            time.sleep(1.5 * (k + 1))
            continue
        return r
    return r


def list_markets(log=print):
    rows = []
    for source, path, statuses in (('historical', '/historical/markets', [None]),
                                   ('live', '/markets', ['unopened', 'open', 'closed', 'settled'])):
        for st in statuses:
            cursor = None
            while True:
                p = {'series_ticker': SERIES, 'limit': 1000}
                if st:
                    p['status'] = st
                if cursor:
                    p['cursor'] = cursor
                r = get(path, **p)
                r.raise_for_status()
                j = r.json()
                for m in j.get('markets', []):
                    m['_source'] = source
                    rows.append(m)
                cursor = j.get('cursor')
                if not cursor:
                    break
        log(source, len(rows))
    d = pd.DataFrame(rows).drop_duplicates('ticker', keep='first')
    return d


def parse_event(event_ticker: str):
    m = re.match(r'KXNBAGAME-(\d{2})([A-Z]{3})(\d{2})([A-Z]{3})([A-Z]{3})$', event_ticker)
    if not m:
        return None
    yy, mon, dd, a, b = m.groups()
    return pd.Timestamp(2000 + int(yy), MONTHS[mon], int(dd)).strftime('%Y-%m-%d'), a, b


def map_games(markets: pd.DataFrame, games: pd.DataFrame):
    g = games.copy()
    g['hc'] = g.home.map(CODE)
    g['ac'] = g.away.map(CODE)
    assert g.hc.notna().all() and g.ac.notna().all(), 'unmapped team abbreviation'
    g['pair'] = [frozenset(x) for x in zip(g.hc, g.ac)]
    g['d'] = pd.to_datetime(g.game_date)
    ev = markets[['event_ticker']].drop_duplicates()
    out = []
    for e in ev.event_ticker:
        p = parse_event(e)
        if p is None:
            continue
        day, a, b = p
        cand = g[(g.pair == frozenset([a, b])) & ((g.d - pd.Timestamp(day)).abs() <= pd.Timedelta(days=1))]
        if len(cand) == 1:
            r = cand.iloc[0]
            out.append({'event_ticker': e, 'game_id': r.game_id, 'home_code': r.hc, 'away_code': r.ac})
    return pd.DataFrame(out)


def candles(source: str, ticker: str, start: int, end: int):
    if source == 'historical':
        r = get(f'/historical/markets/{ticker}/candlesticks', start_ts=start, end_ts=end, period_interval=60)
    else:
        r = get(f'/series/{SERIES}/markets/{ticker}/candlesticks', start_ts=start, end_ts=end, period_interval=60)
    if r.status_code != 200:
        return None, r.status_code, b''
    return r.json().get('candlesticks', []), 200, r.content


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_candle(c):
    """Return (end_ts, bid, ask, price, volume) from either response dialect."""
    def pick(block, key):
        if not block:
            return None
        v = block.get(f'{key}_dollars', block.get(key))
        return num(v)
    return (c['end_period_ts'], pick(c.get('yes_bid'), 'close'), pick(c.get('yes_ask'), 'close'), pick(c.get('price'), 'close'),
            num(c.get('volume_fp', c.get('volume'))) or 0.0)


def state_at(parsed, t):
    """Last known bid/ask/price from candles ending at or before t (carry-forward through quiet hours)."""
    bid = ask = price = None
    ts = None
    vol = 0.0
    for end, b, a, p, v in parsed:
        if end > t:
            break
        if b is not None:
            bid = b
        if a is not None:
            ask = a
        if p is not None:
            price = p
        ts = end
        vol += v
    return bid, ask, price, ts, vol


def mid(bid, ask):
    if bid is None or ask is None or ask <= bid - 1e-9:
        return None
    return (bid + ask) / 2.0


def collect(log=print, limit=None):
    games, _ = data.load(verify=False)
    games = games[games.season >= 2026].copy()
    mk = list_markets(log)
    ev = map_games(mk, games)
    log('events mapped to canonical games:', len(ev), 'of', mk.event_ticker.nunique())
    assert len(ev) > 500, 'too few Kalshi events mapped; the benchmark would cover almost nothing'
    mk = mk.merge(ev, on='event_ticker')
    mk['suffix'] = mk.ticker.str.rsplit('-', n=1).str[1]
    tip = games.set_index('game_id').tipoff_utc
    RAW.mkdir(parents=True, exist_ok=True)
    stamp = pd.Timestamp.now(tz='UTC').strftime('%Y%m%dT%H%M%SZ')
    raw_path = RAW / f'candles_{stamp}.jsonl.gz'
    rows = []
    games_ids = mk.game_id.unique()
    if limit:
        games_ids = games_ids[:limit]
    with gzip.open(raw_path, 'wt', encoding='utf-8') as raw:
        for n, gid in enumerate(games_ids):
            g = games[games.game_id == gid].iloc[0]
            t0 = int(pd.Timestamp(g.tipoff_utc).timestamp())
            sub = mk[mk.game_id == gid]
            rec = {'game_id': gid}
            for side, code in (('home', CODE[g.home]), ('away', CODE[g.away])):
                m = sub[sub.suffix == code]
                if m.empty:
                    continue
                m = m.iloc[0]
                res, status, body = candles(m._source, m.ticker, t0 - 5 * 86400, t0 + 3600)
                retrieved = pd.Timestamp.now(tz='UTC').isoformat()
                if res is None:
                    rec[f'{side}_error'] = status
                    continue
                raw.write(json.dumps({'ticker': m.ticker, 'source': m._source, 'retrieved_utc': retrieved,
                                      'sha256': hashlib.sha256(body).hexdigest(), 'candles': res}) + '\n')
                parsed = [parse_candle(c) for c in res]
                cut = t0 - 3600
                for label, t in (('cut', cut), ('close', t0)):
                    bid, ask, price, ts, vol = state_at(parsed, t)
                    rec[f'{side}_{label}_bid'] = bid
                    rec[f'{side}_{label}_ask'] = ask
                    rec[f'{side}_{label}_mid'] = mid(bid, ask)
                    rec[f'{side}_{label}_last'] = price
                    rec[f'{side}_{label}_candle_end'] = ts
                rec[f'{side}_ticker'] = m.ticker
                rec[f'{side}_result'] = m.get('result')
                rec[f'{side}_source'] = m._source
            rows.append(rec)
            if n % 100 == 0:
                log('candles', n, '/', len(games_ids))
            time.sleep(0.12)
    d = pd.DataFrame(rows)
    d['retrieved_stamp'] = stamp
    d['raw_file'] = raw_path.name
    return d


if __name__ == '__main__':
    d = collect()
    d.to_parquet(OUT / 'kalshi_prices.parquet', index=False)
    print(d.shape)
    print(d[['home_cut_mid', 'away_cut_mid', 'home_close_mid', 'away_close_mid']].describe().round(3))
