#!/usr/bin/env python3
"""Task 1: collapse the git-history prop snapshots into one row per (game, player, market, book, line) = the LAST quote observed strictly before kickoff
(vendor updatedAt < kickoff), join outcomes from data/results.json (public nflverse-derived appearance-aware logs) and write a parquet to OUT.
usage: build_quotes.py IN_DIR OUT_DIR   (IN_DIR holds git_props_all.parquet from extract_git_props.py)"""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT.parent / 'GOING' / 'FantasyPoints' / 'research' / 'cache'
IN, OUT = Path(sys.argv[1]), Path(sys.argv[2])

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r'[^a-z0-9 ]', '', n)
    return re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', ' '.join(n.split()))

d = pd.read_parquet(IN / 'git_props_all.parquet')
d['kick'] = pd.to_datetime(d.kickoff, utc=True, format='ISO8601', errors='coerce')
d['upd'] = pd.to_datetime(d.updated, utc=True, format='ISO8601', errors='coerce')
d['dfs'] = d.dfs.fillna(False).astype(bool)
n_all = len(d)
priced = d[(~d.dfs) & (d.over.notna() | d.under.notna())]  # TD markets are posted one-sided (Yes price only)
pre = priced[priced.upd < priced.kick]
pre = pre.assign(gameday=(pre.kick - pd.Timedelta(hours=4)).dt.strftime('%Y-%m-%d'))  # ET calendar day; event ids/kick strings differ by book
key = ['gameday', 'player', 'market', 'book', 'line']
pre = pre.sort_values('upd')
g = pre.groupby(key, sort=False)
q = g.last().reset_index()[key + ['over', 'under', 'upd', 'kick', 'home', 'away']]
q['n_upd'] = g.size().values
q['first_upd'] = g.upd.first().values
# games / week / outcomes
gm = pd.read_csv(CACHE / 'games.csv'); gm = gm[(gm.season == 2026) & (gm.game_type == 'REG')]
day2week = dict(zip(gm.gameday, gm.week))
q['week'] = q.gameday.map(day2week)
st = pd.concat([pd.read_csv(CACHE / f'stats_player_week_{y}.csv', low_memory=False, usecols=['player_id', 'player_display_name', 'position']) for y in (2024, 2025, 2026)])
nm = {}
for pid, name in zip(st.player_id, st.player_display_name):
    nm.setdefault(norm(name), set()).add(pid)
res = json.load(open(ROOT / 'data' / 'results.json'))['players']
def lookup(player, day):
    for pid in nm.get(norm(player), ()):
        r = res.get(f'{pid}|{day}')
        if r is not None:
            return pid, r
    return None, None
cache = {}
pids, vals = [], []
MK = {'pass_yds': 'pass_yds', 'rush_yds': 'rush_yds', 'rec_yds': 'rec_yds', 'receptions': 'receptions', 'pass_tds': 'pass_tds', 'rush_tds': 'rush_tds', 'rec_tds': 'rec_tds', 'atd': 'atd'}
for player, day, mk in zip(q.player, q.gameday, q.market):
    k = (player, day)
    if k not in cache:
        cache[k] = lookup(player, day)
    pid, r = cache[k]
    pids.append(pid)
    vals.append(r.get(MK[mk]) if (r is not None and mk in MK) else np.nan)
q['pid'], q['actual'] = pids, vals
q['has_row'] = q.pid.notna()
q.to_parquet(OUT / 'quotes_pregame.parquet')
print('raw prop rows', n_all, 'non-DFS two-sided', len(priced), 'pregame', len(pre), 'unique pregame quotes', len(q), 'with outcome', int(q.actual.notna().sum()))
