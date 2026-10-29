"""Prospective capture of live NBA game state (ESPN) and Kalshi quotes, one record per minute, append-only with a hash chain.

Read-only public GET requests. Never places, simulates or cancels an order. Each line holds the retrieval time of every call, so quote age is explicit.
Per game: ESPN period/clock/score; Kalshi moneyline markets (top of book and 3 levels of depth from the order book); spread and total markets with
bid/ask for the strikes whose last/mid price is nearest 50%. A line's `prev_sha256` chains it to the previous line so later edits are detectable.

    python -m nba_xgb.live_collector --date 2026-10-29
"""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path
import pandas as pd
import requests
from . import kalshi
from .avail_study import OUT

DIR = OUT / 'live_capture'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}'
UA = {'User-Agent': 'NBA-Ensemble-Local-Research/1.0'}


def now_iso():
    return pd.Timestamp.now(tz='UTC').isoformat()


def espn_state(date: str):
    r = requests.get(ESPN.format(d=date.replace('-', '')), headers=UA, timeout=15)
    out = []
    for e in r.json().get('events', []):
        c = e['competitions'][0]
        teams = {t['homeAway']: t for t in c['competitors']}
        st = e['status']
        out.append({'event_id': e['id'], 'start': e['date'], 'state': st['type']['state'], 'detail': st['type'].get('shortDetail'),
                    'period': st.get('period'), 'clock': st.get('displayClock'), 'clock_s': st.get('clock'),
                    'home': teams['home']['team']['abbreviation'], 'away': teams['away']['team']['abbreviation'],
                    'home_score': int(teams['home'].get('score') or 0), 'away_score': int(teams['away'].get('score') or 0)})
    return out, now_iso()


def top_levels(ob, n=3):
    j = ob.get('orderbook_fp', ob.get('orderbook', {}))
    yes = sorted(([float(p), float(q)] for p, q in j.get('yes_dollars', [])), reverse=True)[:n]       # best bid first
    no = sorted(([float(p), float(q)] for p, q in j.get('no_dollars', [])), reverse=True)[:n]
    return {'yes_bids': yes, 'no_bids': no, 'yes_ask_best': (1.0 - no[0][0]) if no else None, 'yes_bid_best': yes[0][0] if yes else None}


def kalshi_event_markets(series, event_ticker):
    r = kalshi.get('/markets', series_ticker=series, event_ticker=event_ticker, limit=200)
    return r.json().get('markets', []) if r.ok else []


def near_half(markets, k=3):
    rows = []
    for m in markets:
        try:
            b, a = float(m['yes_bid_dollars']), float(m['yes_ask_dollars'])
        except (KeyError, TypeError, ValueError):
            continue
        if a > b:
            rows.append((abs((a + b) / 2 - 0.5), m['ticker'], m.get('floor_strike'), m.get('yes_sub_title'), b, a, m.get('last_price_dollars')))
    rows.sort()
    return [{'ticker': t, 'strike': s, 'label': lab, 'yes_bid': b, 'yes_ask': a, 'last': last} for _, t, s, lab, b, a, last in rows[:k]]


def run(date: str, poll=60, start_before_min=90, log=print):
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / f'capture_{date.replace("-", "")}.jsonl'
    prev = '0' * 64
    if path.exists():
        prev = json.loads(path.read_text(encoding='utf-8').strip().splitlines()[-1])['sha256']
    state, _ = espn_state(date)
    if not state:
        raise SystemExit(f'no games on {date}')
    first_start = min(pd.Timestamp(e['start']) for e in state)
    quiet_until = first_start - pd.Timedelta(minutes=start_before_min)
    log('first tipoff', first_start, '| capture begins', quiet_until)
    while pd.Timestamp.now(tz='UTC') < quiet_until:
        time.sleep(30)
    # map ESPN games to Kalshi event tickers once per hour
    mk_time, ev_map = None, {}
    while True:
        t0 = time.time()
        rec = {'captured_utc': now_iso(), 'espn': None, 'kalshi': {}, 'errors': []}
        try:
            state, rec['espn_retrieved_utc'] = espn_state(date)
            rec['espn'] = state
        except Exception as e:
            rec['errors'].append(f'espn:{type(e).__name__}')
            state = rec['espn'] or []
        try:
            if mk_time is None or time.time() - mk_time > 3600:
                mk = kalshi.list_markets(lambda *a: None)
                mk = mk[mk.status.isin(['active', 'open', 'initialized', 'unopened'])] if 'status' in mk else mk
                ev_map = {}
                for _, r in mk.drop_duplicates('event_ticker').iterrows():
                    p = kalshi.parse_event(r.event_ticker)
                    if p and p[0] == date:
                        ev_map[frozenset([p[1], p[2]])] = r.event_ticker
                mk_time = time.time()
            for e in state:
                code = frozenset([kalshi.CODE.get(e['home']), kalshi.CODE.get(e['away'])])
                et = ev_map.get(code)
                if not et or e['state'] == 'post':
                    continue
                suffix = et.split('-', 1)[1]
                k = {'event_ticker': et, 'retrieved_utc': now_iso()}
                ml = kalshi_event_markets('KXNBAGAME', et)
                k['moneyline'] = []
                for m in ml:
                    ob = kalshi.get(f'/markets/{m["ticker"]}/orderbook')
                    k['moneyline'].append({'ticker': m['ticker'], 'bid': m.get('yes_bid_dollars'), 'ask': m.get('yes_ask_dollars'),
                                           'last': m.get('last_price_dollars'), 'book': top_levels(ob.json()) if ob.ok else None,
                                           'retrieved_utc': now_iso()})
                k['spread_near_half'] = near_half(kalshi_event_markets('KXNBASPREAD', 'KXNBASPREAD-' + suffix))
                k['total_near_half'] = near_half(kalshi_event_markets('KXNBATOTAL', 'KXNBATOTAL-' + suffix))
                rec['kalshi'][f"{e['away']}@{e['home']}"] = k
        except Exception as ex:
            rec['errors'].append(f'kalshi:{type(ex).__name__}:{str(ex)[:80]}')
        rec['prev_sha256'] = prev
        body = json.dumps(rec, sort_keys=True)
        rec['sha256'] = hashlib.sha256(body.encode()).hexdigest()
        with path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, sort_keys=True) + '\n')
        prev = rec['sha256']
        if state and all(e['state'] == 'post' for e in state):
            log('all games final; capture complete')
            return path
        time.sleep(max(1.0, poll - (time.time() - t0)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', required=True)
    ap.add_argument('--poll', type=int, default=60)
    a = ap.parse_args()
    run(a.date, a.poll)
