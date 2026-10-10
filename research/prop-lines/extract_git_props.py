#!/usr/bin/env python3
"""Task 1: extract every posted player-prop quote ever committed to data/nfl_betting.json (git history). Read-only on git; writes a parquet of quotes to an
OUT directory (default: a temp dir, not the repo). Prints nothing row-level."""
import json, subprocess, sys, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
log = subprocess.run(['git', 'log', '--format=%H|%cI', '--', 'data/nfl_betting.json'], cwd=ROOT, capture_output=True, text=True).stdout.strip().splitlines()
rows = []; meta = []
for line in reversed(log):
    sha, ct = line.split('|')
    raw = subprocess.run(['git', 'show', f'{sha}:data/nfl_betting.json'], cwd=ROOT, capture_output=True).stdout
    try:
        d = json.loads(raw)
    except Exception as e:
        meta.append((sha[:7], ct, 'unparseable')); continue
    props = d.get('props') or []
    meta.append((sha[:7], ct, len(props), d.get('generated_at'), d.get('props_status') or (d.get('source_states') or {}).get('props')))
    for p in props:
        rows.append({'commit': sha[:7], 'commit_time': ct, 'event': p.get('eventId'), 'player': p.get('player'), 'market': p.get('market'), 'line': p.get('line'),
                     'book': p.get('bookKey') or p.get('book'), 'over': p.get('overOdds'), 'under': p.get('underOdds'), 'updated': p.get('updatedAt'),
                     'kickoff': p.get('kickoff'), 'dfs': p.get('dfs'), 'home': p.get('homeName'), 'away': p.get('awayName'), 'gameDate': p.get('gameDate')})
df = pd.DataFrame(rows)
df.to_parquet(OUT / 'git_props_all.parquet')
pd.DataFrame(meta).to_csv(OUT / 'git_meta.csv', index=False)
print(len(log), 'commits', len(df), 'prop rows')
