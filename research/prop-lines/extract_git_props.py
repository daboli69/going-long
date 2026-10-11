#!/usr/bin/env python3
"""Extract public committed quotes with immutable source receipts; no API calls.

Usage: extract_git_props.py OUT_DIR [--revision COMMIT] [--market pass_yds]
Raw observations stay in the explicitly selected output folder, not a default
repository location. Importing this module performs no reads or writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ['commit', 'commit_time', 'event', 'player', 'market', 'line', 'book', 'over', 'under',
           'updated', 'kickoff', 'dfs', 'home', 'away', 'gameDate']


def extract(root=ROOT, revision='HEAD', market=None):
    # Resolve an explicit commit; caller-supplied revisions cannot become Git flags.
    rev = subprocess.check_output(['git', 'rev-parse', '--verify', '--end-of-options', f'{revision}^{{commit}}'], cwd=root, text=True).strip()
    log = subprocess.check_output(['git', 'log', '--format=%H|%cI', rev, '--', 'data/nfl_betting.json'], cwd=root, text=True).splitlines()
    rows, receipts = [], []
    for entry in reversed(log):
        sha, observed = entry.split('|')
        shown = subprocess.run(['git', 'show', f'{sha}:data/nfl_betting.json'], cwd=root, capture_output=True)
        receipt = {'revision': sha, 'observed_at': observed, 'sha256': hashlib.sha256(shown.stdout).hexdigest()}
        try:
            if shown.returncode:
                raise ValueError('snapshot absent at revision')
            doc = json.loads(shown.stdout)
            props = doc.get('props') or []
            if not isinstance(props, list):
                raise ValueError('invalid props list')
        except (ValueError, TypeError):
            receipts.append(dict(receipt, status='unparseable'))
            continue
        receipts.append(dict(receipt, status='loaded', rows=len(props), generated_at=doc.get('generated_at')))
        for p in props:
            if not isinstance(p, dict) or (market is not None and p.get('market') != market):
                continue
            rows.append(dict(commit=sha, commit_time=observed, event=p.get('eventId'), player=p.get('player'),
                             market=p.get('market'), line=p.get('line'), book=p.get('bookKey') or p.get('book'),
                             over=p.get('overOdds'), under=p.get('underOdds'), updated=p.get('updatedAt'),
                             kickoff=p.get('kickoff'), dfs=p.get('dfs'), home=p.get('homeName'),
                             away=p.get('awayName'), gameDate=p.get('gameDate')))
    return pd.DataFrame(rows, columns=COLUMNS), receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--revision', default='HEAD')
    parser.add_argument('--market')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    frame, receipts = extract(revision=args.revision, market=args.market)
    frame.to_parquet(args.output / 'git_props_all.parquet')
    (args.output / 'source_receipts.json').write_text(json.dumps(receipts, indent=2) + '\n', encoding='utf-8')
    print(len(receipts), 'commits', len(frame), 'prop rows')


if __name__ == '__main__':
    main()
