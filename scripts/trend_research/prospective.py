"""Outcome files and the join that answers the prospective question: did the trend detected BEFORE a game predict what happened in it?

Trend states (fp_ingest/trends.py) never contain outcomes. Outcomes live in separate write-once files, one per NFL week, built from public nflverse weekly
stats. The join pairs a trend state (usage in a player's g-th game of the season) with that player's NEXT appearance, found by counting the player's
own appearances, so byes and inactive weeks cannot misalign it; an alignment check compares the state's weekly line with the stat line of the
appearance it claims to describe.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd

from . import champion

OUTCOME_COLUMNS = ['targets', 'receptions', 'receiving_yards', 'receiving_tds', 'carries', 'rushing_yards', 'rushing_tds', 'attempts', 'passing_yards', 'passing_tds']


def write_outcomes(root, season, weekly=None, refresh=False):
    """Write outcomes/<season>/week-NN.json for every completed NFL week not written yet. Existing files are never edited."""
    root = Path(root)
    if weekly is None:
        cache = champion.cache(root) / f'stats_player_week_{season}.csv'
        if refresh and cache.exists():
            cache.unlink()
        weekly = champion.load_weekly(root, [season])
    weekly = weekly[(weekly.season == season) & (weekly.season_type == 'REG')].dropna(subset=['player_id'])
    last_week = int(weekly.week.max()) if len(weekly) else 0
    written = []
    for week in range(1, last_week):  # the latest week may still be in progress
        rows = weekly[weekly.week == week]
        if rows.empty:
            continue
        target = root / 'outcomes' / str(season) / f'week-{week:02d}.json'
        if target.exists():
            continue
        players = {r.player_id: {'team': None if pd.isna(r.team) else r.team, 'opponent': None if pd.isna(r.opponent_team) else r.opponent_team, 'position': None if pd.isna(r.position) else r.position,
                                 **{c: (None if pd.isna(getattr(r, c)) else float(getattr(r, c))) for c in OUTCOME_COLUMNS}} for r in rows.itertuples()}
        digest = hashlib.sha256(json.dumps(players, sort_keys=True).encode('utf-8')).hexdigest()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({'schema': 'fp-outcome-v1', 'season': season, 'week': week, 'source': 'nflverse stats_player (public)', 'players_sha256': digest,
                                      'players': players}, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        written.append(target.relative_to(root).as_posix())
    return written


def appearances_by_player(root, season):
    """{player_id: [(week, stat line), ...]} from the written outcome files, in week order."""
    out = {}
    for path in sorted((Path(root) / 'outcomes' / str(season)).glob('week-*.json')):
        doc = json.loads(path.read_text(encoding='utf-8'))
        for pid, line in doc['players'].items():
            out.setdefault(pid, []).append((doc['week'], line))
    return out


def join_next_game(state, appearances):
    """For each player in a trend state, the stat line of the appearance that FOLLOWED the state's game, plus an alignment flag."""
    pairs = {}
    for pid, record in state['players'].items():
        before = (record.get('games_before') or {}).get('receiving_routes_run')
        if before is None or 'week' not in record:
            continue
        lines = appearances.get(pid, [])
        index = before  # 0-based index of the state's own game
        if index + 1 >= len(lines):
            continue  # the next game has not happened (or has no outcome file yet)
        own_week, own_line = lines[index]
        next_week, next_line = lines[index + 1]
        aligned = own_line.get('targets') is not None and abs((own_line.get('targets') or 0) - (record['week'].get('targets') or 0)) < 0.5
        pairs[pid] = {'state_week': own_week, 'next_week': next_week, 'aligned': bool(aligned), 'next': next_line, 'labels': [l['label'] for l in record.get('labels', [])]}
    return pairs
