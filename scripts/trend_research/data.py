"""Leakage-safe data access for research.

Rules enforced here (tests fail if they are removed):
* A feature frame for season N is built ONLY from Fantasy Points snapshots of season N-1 or earlier (`prior_features`). The retrospective
  full-season file of season N is available solely as an OUTCOME (`outcome_frame`), never as an input for season N.
* Weekly outcomes come from public nflverse player stats; in-season rolling features use weeks strictly before the target week.
* Rows whose identity is unresolved or ambiguous are dropped, never guessed.
"""
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from fp_ingest.store import Manifest, current_entry

WEEKLY_URL = 'https://github.com/nflverse/nflverse-data/releases/download/player_stats/stats_player_week_{season}.csv'
SKILL = ('WR', 'TE', 'RB')


class LeakageError(RuntimeError):
    pass


def snapshot_frame(root, manifest, season, table_id):
    """One current archived snapshot as a DataFrame keyed by gsis id: entity columns plus every metric as 'Group.COL'."""
    entry = current_entry(manifest, season, table_id)
    if entry is None:
        return None
    doc = json.loads((Path(root) / entry['normalized_path']).read_text(encoding='utf-8'))
    rows = []
    for row in doc['rows']:
        entity = row['entity']
        if doc['level'] == 'player' and (not entity.get('player_id') or entity.get('split_entity')):
            continue
        rows.append({'player_id': entity.get('player_id'), 'team_key': entity.get('team') or ','.join(entity.get('teams') or []) or entity.get('name'),
                     'pos': entity.get('position'), 'games': row['context'].get('games'), **row['metrics']})
    frame = pd.DataFrame(rows)
    if doc['level'] == 'player':
        frame = frame.drop_duplicates('player_id', keep=False)  # a player twice in one table is unresolvable: drop both, never pick one
    return frame


def prior_features(root, manifest, target_season, table_id):
    """Features for predicting `target_season`: only snapshots of EARLIER seasons exist for this call."""
    frame = snapshot_frame(root, manifest, target_season - 1, table_id)
    return frame


def outcome_frame(root, manifest, season, table_id):
    """Outcome data of `season` (a completed, retrospective season). Use only as the thing being predicted."""
    return snapshot_frame(root, manifest, season, table_id)


def assert_no_same_season(feature_season, target_season):
    if feature_season >= target_season:
        raise LeakageError(f'features from season {feature_season} cannot predict season {target_season}')


def weekly(root, season):
    """Regular-season weekly player stats (public nflverse), cached under FantasyPoints/research/cache."""
    cache = Path(root) / 'research' / 'cache' / f'stats_player_week_{season}.csv'
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(WEEKLY_URL.format(season=season), timeout=120) as response:
            data = response.read()
        temporary = cache.with_suffix('.tmp')
        temporary.write_bytes(data)
        temporary.replace(cache)
    frame = pd.read_csv(cache, usecols=['player_id', 'position', 'team', 'opponent_team', 'season', 'week', 'season_type', 'receptions', 'targets',
                                        'receiving_yards', 'receiving_tds', 'carries', 'rushing_yards', 'rushing_tds', 'fantasy_points_ppr'])
    return frame[frame.season_type == 'REG'].drop(columns='season_type').reset_index(drop=True)


def per_game(frame, columns, games='games'):
    out = frame.copy()
    for column in columns:
        out[column + '/g'] = out[column] / out[games].replace(0, np.nan)
    return out
