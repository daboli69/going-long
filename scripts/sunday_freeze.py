#!/usr/bin/env python3
"""Pregame freeze manifest for a slate day (write-once). Records exactly which code, model policy, data snapshots and shadow predictions were in place BEFORE kickoff, so the
slate can later be scored against what GOING said and nothing can be edited after the fact.

    python scripts/sunday_freeze.py 2026-10-11

It does not snapshot licensed or private material (ownership models, user salary files, lineups: those are frozen on the user's device with "Freeze this lineup").
The tracker (data/public_tracker) separately freezes every GOING pick, price and rating; role_shadow / td_shadow freeze the Challenger predictions.
"""
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FILES = ['history.json', 'nfl_betting.json', 'football_context.json', 'injury_context.json', 'season_learning.json', 'dfs_correlations.json', 'king-endzone.json', 'slate-breaker.json']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generated(path):
    d = json.loads(path.read_text(encoding='utf-8'))
    return d.get('generated_at') or d.get('generatedAt') or (d.get('betting') or {}).get('generated_at')


def main(day):
    out = REPO / 'data' / 'freezes' / f'{day}.json'
    if out.exists():
        print('already frozen (write-once):', out)
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    games = json.loads((REPO / 'data/nfl_betting.json').read_text(encoding='utf-8')).get('games_raw', [])
    kickoffs = sorted(g['commence_time'] for g in games if str(g.get('commence_time', ''))[:10] == day)
    if not kickoffs:
        print('no NFL games on', day, '- nothing to freeze')
        return
    if now >= datetime.datetime.fromisoformat(kickoffs[0].replace('Z', '+00:00')):
        print(f'first kickoff {kickoffs[0]} has passed: not a pregame freeze, nothing written')
        return
    history = json.loads((REPO / 'data/history.json').read_text(encoding='utf-8'))['betting']
    policies, scoring = {}, 0
    for p in history['profiles'].values():
        for market, model in (p.get('stats') or {}).items():
            policies[f"{market}:{model.get('policy', 'v1')}"] = policies.get(f"{market}:{model.get('policy', 'v1')}", 0) + 1
        scoring += 1 if p.get('scoring_role') else 0
    champion = json.loads((REPO / 'config/champion_policy.json').read_text(encoding='utf-8'))
    shadows = {}
    for folder in ('role_shadow', 'td_shadow', 'nb_shadow'):
        for path in sorted((REPO / 'data' / folder).glob('*-week-??.json')):
            doc = json.loads(path.read_text(encoding='utf-8'))
            rows = len(doc.get('rows', [])) or sum(len(g.get('candidates', [])) for g in doc.get('games', []) if isinstance(g, dict))
            shadows[f'{folder}/{path.name}'] = {'sha256': sha(path), 'recorded_at': doc.get('recorded_at'), 'rows': rows}
    doc = {'schema': 'going-pregame-freeze-v1', 'slate_date': day, 'frozen_at': now.isoformat(timespec='seconds'), 'first_kickoff': kickoffs[0] if kickoffs else None,
           'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO).decode().strip(),
           'champion_policy': {'active': champion.get('active'), 'sha256': sha(REPO / 'config/champion_policy.json')},
           'today_ranking_experiment': json.loads((REPO / 'research/today-ranking/experiment-v3.json').read_text(encoding='utf-8')).get('id'),
           'profile_policy_counts': policies, 'profiles_with_scoring_role': scoring, 'scoring_role_ok': scoring >= 0.5 * max(1, len(history['profiles'])),
           'data': {f: {'sha256': sha(REPO / 'data' / f), 'generated_at': generated(REPO / 'data' / f)} for f in FILES if (REPO / 'data' / f).exists()},
           'shadow_files': shadows,
           'note': 'Do not edit. Picks, prices and ratings are frozen by the tracker; ownership models, salary files and lineups stay private on the user device.'}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + '\n', encoding='utf-8')
    print('frozen', out)


if __name__ == '__main__':
    main(sys.argv[1])
