#!/usr/bin/env python3
"""Collapse git-history snapshots into intact quotes proven observed before kickoff.

Both vendor updatedAt and repository commit_time must precede kickoff. A vendor
timestamp alone does not prove a quote was available to this application then.
Join public outcomes and write a parquet to OUT. Previously generated evaluation
figures require regeneration under this corrected observation boundary.
usage: build_quotes.py IN_DIR OUT_DIR (IN_DIR holds git_props_all.parquet)
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT.parent / 'GOING' / 'FantasyPoints' / 'research' / 'cache'


def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r'[^a-z0-9 ]', '', n)
    return re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', ' '.join(n.split()))


def collapse_quotes(raw):
    """Keep each final observed row whole, including a missing opposite side.

    Git commit time is conservative evidence of application availability; it may
    exclude a genuinely earlier retrieval committed after kickoff. We cannot
    reconstruct that missing receipt from vendor timestamps. Counts below refer
    only to qualifying pregame observations, including repeated snapshots.
    """
    d = raw.copy()
    d['kick'] = pd.to_datetime(d.kickoff, utc=True, format='ISO8601', errors='coerce')
    d['upd'] = pd.to_datetime(d.updated, utc=True, format='ISO8601', errors='coerce')
    receipt = d['commit_time'] if 'commit_time' in d else pd.Series(None, index=d.index, dtype=object)
    d['observed_at'] = pd.to_datetime(receipt, utc=True, format='ISO8601', errors='coerce')
    d['dfs'] = d.dfs.fillna(False).astype(bool)
    priced = d[(~d.dfs) & (d.over.notna() | d.under.notna())]
    pre = priced[(priced.upd < priced.kick) & (priced.observed_at < priced.kick)
                 & (priced.upd <= priced.observed_at)].copy()
    pre['gameday'] = pre.kick.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    key = ['gameday', 'home', 'away', 'player', 'market', 'book', 'line']
    pre = pre.sort_values(['upd', 'observed_at'], kind='stable')
    g = pre.groupby(key, sort=False, dropna=False)
    # last() skips nulls COLUMN BY COLUMN and can manufacture a two-way quote
    # from prices never offered together. tail(1) preserves the observed row.
    q = g.tail(1)[key + ['over', 'under', 'upd', 'kick', 'observed_at']].copy()
    q = q.merge(g.size().rename('n_upd').reset_index(), on=key, how='left')
    q = q.merge(g.upd.min().rename('first_upd').reset_index(), on=key, how='left')
    return q, {'raw': len(d), 'priced': len(priced), 'pregame': len(pre)}


def lookup_outcome(names, results, player, day):
    matches = [(pid, results[f'{pid}|{day}']) for pid in names.get(norm(player), ())
               if f'{pid}|{day}' in results]
    # A normalized name can belong to multiple real athletes. Set iteration is
    # not identity evidence; unresolved collisions must not receive an outcome.
    return matches[0] if len(matches) == 1 else (None, None)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        raise SystemExit('usage: build_quotes.py IN_DIR OUT_DIR')
    in_dir, out_dir = map(Path, args)
    q, counts = collapse_quotes(pd.read_parquet(in_dir / 'git_props_all.parquet'))
    gm = pd.read_csv(CACHE / 'games.csv')
    gm = gm[(gm.season == 2026) & (gm.game_type == 'REG')]
    q['week'] = q.gameday.map(dict(zip(gm.gameday, gm.week)))
    q = q[q.week.notna()].copy()  # No preseason or non-regular-season date leakage.
    st = pd.concat([pd.read_csv(CACHE / f'stats_player_week_{y}.csv', low_memory=False,
                               usecols=['player_id', 'player_display_name', 'position']) for y in (2024, 2025, 2026)])
    names = {}
    for pid, name in zip(st.player_id, st.player_display_name):
        names.setdefault(norm(name), set()).add(pid)
    with (ROOT / 'data' / 'results.json').open(encoding='utf-8') as source:
        results = json.load(source)['players']

    cache, pids, vals = {}, [], []
    markets = {'pass_yds', 'rush_yds', 'rec_yds', 'receptions', 'pass_tds', 'rush_tds', 'rec_tds', 'atd'}
    for player, day, market in zip(q.player, q.gameday, q.market):
        key = (player, day)
        if key not in cache:
            cache[key] = lookup_outcome(names, results, player, day)
        pid, row = cache[key]
        pids.append(pid)
        vals.append(row.get(market) if row is not None and market in markets else np.nan)
    q['pid'], q['actual'] = pids, vals
    q['has_row'] = q.pid.notna()
    q.to_parquet(out_dir / 'quotes_pregame.parquet')
    print('raw prop rows', counts['raw'], 'non-DFS priced', counts['priced'], 'pregame', counts['pregame'],
          'unique pregame quotes', len(q), 'with outcome', int(q.actual.notna().sum()))


if __name__ == '__main__':
    main()
