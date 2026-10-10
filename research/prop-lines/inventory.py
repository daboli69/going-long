#!/usr/bin/env python3
"""Task 1 inventory of posted-line data (aggregates only). usage: inventory.py QUOTES_PARQUET (from build_quotes.py) """
import sys, warnings
from pathlib import Path
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import calibration_audit_a as A
q = pd.read_parquet(sys.argv[1])
q['pg'] = q.gameday + '|' + q.player
s = q[q.gameday <= '2026-10-08']
print('GIT-HISTORY QUOTES (data/nfl_betting.json, last pregame quote per game/player/market/book/line); played games only')
two = s.over.notna() & s.under.notna()
t = s.assign(two=two).groupby('market').agg(quotes=('line', 'size'), two_sided=('two', 'sum'), player_games=('pg', 'nunique'), books=('book', 'nunique'), settled_quotes=('actual', lambda x: int(x.notna().sum())))
t['settled_player_games'] = s[s.actual.notna()].groupby('market').pg.nunique()
print(t.to_string())
print('weeks with settled quotes (player-games):', s[s.actual.notna()].groupby('week').pg.nunique().to_dict())
lead = (s.kick - s.upd).dt.total_seconds() / 3600
print('hours between last pregame quote and kickoff: p10 %.1f median %.1f p90 %.1f' % tuple(np.percentile(lead, [10, 50, 90])))
print('unique quote versions seen per (game,player,market,book,line): median', int(s.n_upd.median()), 'max', int(s.n_upd.max()))
ml = s[s.actual.notna()].groupby(['market', 'pg']).line.nunique()
print('player-games with >1 distinct line (alternate ladders), settled:', ml[ml > 1].groupby('market').size().to_dict(), 'of', ml.groupby('market').size().to_dict())
print('\nLIVE TRACKER (data/public_tracker via tracker_store.load_tracker)')
df, recs = A.load_frame()
n = df[df.sport == 'nfl']
d = A.settled_universe(n)
U = d.drop_duplicates('contract')
r = n.groupby('market').agg(predictions=('id', 'size'), unique_contracts=('contract', 'nunique')).join(U.groupby('market').size().rename('settled_pregame_unique'))
print(r.to_string())
print('first/last observation', n.obs_t.min(), n.obs_t.max(), '| weeks (kickoff dates):', sorted(U.ko_t.dt.strftime('%m-%d').unique()))
from collections import Counter
print('record kinds', dict(Counter(x['kind'] for x in recs)))
