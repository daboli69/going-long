"""Historical in-game Kalshi quotes (1-minute candles) for NBA game-winner, spread and total markets. Read-only public market data.

Per market the response is archived as JSONL (gzip) with SHA-256 and retrieval time. The parsed table keeps, per minute: bid, ask, last price
and volume as published; minutes with no activity carry no new bid/ask in the response, so consumers must forward-fill and treat the age of the quote explicitly.
Nothing here places, simulates or fills an order.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path
import pandas as pd
from . import data, kalshi
from .avail_study import OUT

DIR = OUT / 'kalshi_inplay'
PRE, POST = 3600, 4 * 3600 + 1800        # one hour before tipoff through 4.5 hours after (covers overtime)


def fetch_candles(source: str, series: str, ticker: str, start: int, end: int, period=1):
    if source == 'historical':
        r = kalshi.get(f'/historical/markets/{ticker}/candlesticks', start_ts=start, end_ts=end, period_interval=period)
    else:
        r = kalshi.get(f'/series/{series}/markets/{ticker}/candlesticks', start_ts=start, end_ts=end, period_interval=period)
    return r


def parse_rows(ticker, candles, retrieved):
    rows = []
    for c in candles:
        end, bid, ask, price, vol = kalshi.parse_candle(c)
        rows.append((ticker, end, bid, ask, price, vol, retrieved))
    return rows


def collect_moneyline(limit=None, log=print):
    DIR.mkdir(parents=True, exist_ok=True)
    games, _ = data.load(verify=False)
    games = games[games.season == 2026].copy()
    mk = kalshi.list_markets(log)
    ev = kalshi.map_games(mk, games)
    mk = mk.merge(ev, on='event_ticker')
    mk['suffix'] = mk.ticker.str.rsplit('-', n=1).str[1]
    done_path = DIR / 'moneyline_minutes.parquet'
    done = pd.read_parquet(done_path) if done_path.exists() else pd.DataFrame()
    done_tickers = set(done.ticker) if len(done) else set()
    stamp = pd.Timestamp.now(tz='UTC').strftime('%Y%m%dT%H%M%SZ')
    raw_path = DIR / f'moneyline_raw_{stamp}.jsonl.gz'
    out, ids = [done] if len(done) else [], games.game_id.tolist()[: limit or None]
    n = 0
    with gzip.open(raw_path, 'wt', encoding='utf-8') as raw:
        for gid in ids:
            g = games[games.game_id == gid].iloc[0]
            t0 = int(pd.Timestamp(g.tipoff_utc).timestamp())
            for code in (kalshi.CODE[g.home], kalshi.CODE[g.away]):
                m = mk[(mk.game_id == gid) & (mk.suffix == code)]
                if m.empty or m.iloc[0].ticker in done_tickers:
                    continue
                m = m.iloc[0]
                r = fetch_candles(m._source, kalshi.SERIES, m.ticker, t0 - PRE, t0 + POST)
                retrieved = pd.Timestamp.now(tz='UTC').isoformat()
                if r.status_code != 200:
                    log('error', m.ticker, r.status_code)
                    continue
                cs = r.json().get('candlesticks', [])
                raw.write(json.dumps({'ticker': m.ticker, 'source': m._source, 'retrieved_utc': retrieved,
                                      'sha256': hashlib.sha256(r.content).hexdigest(), 'candles': cs}) + '\n')
                df = pd.DataFrame(parse_rows(m.ticker, cs, retrieved), columns=['ticker', 'end_ts', 'bid', 'ask', 'last', 'volume', 'retrieved_utc'])
                df['game_id'] = gid
                df['side'] = 'home' if code == kalshi.CODE[g.home] else 'away'
                df['result'] = m.result
                out.append(df)
                n += 1
                time.sleep(0.1)
            if len(out) and n % 100 == 0 and n:
                pd.concat(out, ignore_index=True).to_parquet(done_path, index=False)
                log('moneyline markets collected', n)
    res = pd.concat(out, ignore_index=True)
    res.to_parquet(done_path, index=False)
    log('done', res.ticker.nunique(), 'markets', len(res), 'minute rows')
    return res


if __name__ == '__main__':
    collect_moneyline(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
