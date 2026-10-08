"""Point-in-time reader and audit for the by-game Fantasy Points tables (one row per player or team per game).

Rule: features for predicting week N use rows with WEEK < N (``features_through``). A by-game row describes only its own game (G == 1), so no
row can contain a later game; ``audit`` proves this against public nflverse box scores instead of trusting the file names or headers.
Licensed values stay in the local FantasyPoints folder: only aggregate audit results are written to research/trend-intelligence.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import champion

PLAYER_TABLES = {'rr': 'receiving_routes_run_weekly', 'ra': 'receiving_advanced_weekly', 'rb': 'rushing_bell_cow_weekly',
                 'ru': 'rushing_advanced_weekly', 'ef': 'efficiency_weekly'}
TEAM_TABLES = {'rp': 'run_pass_report_weekly'}
SEASONS = (2021, 2022, 2023, 2024, 2025, 2026)


def _manifest(root):
    from fp_ingest.store import Manifest
    return Manifest(root)


def _entries(manifest, table_id, include_superseded=False):
    from fp_ingest.store import game_entries
    out = {}
    for season in SEASONS:
        found = game_entries(manifest, season, table_id, include_superseded=include_superseded)
        if found:
            out[season] = found[0]
    return out


def load_table(root, table_id, seasons=None):
    """Tidy frame for one by-game table: season, week, player_id (null when unmatched), name, team, position, opponent, known_at plus every metric
    as ``Group.COL``. Always the current (non-superseded) file of each season."""
    root = Path(root)
    manifest = _manifest(root)
    from fp_ingest.store import game_row_known_at
    frames = []
    for season, entry in _entries(manifest, table_id).items():
        if seasons and season not in seasons:
            continue
        doc = json.loads((root / entry['normalized_path']).read_text(encoding='utf-8'))
        known = {w: game_row_known_at(manifest, season, table_id, w) for w in entry['weeks']}
        rows = []
        for r in doc['rows']:
            e, c = r['entity'], r['context']
            rows.append({'season': season, 'week': c['week'], 'player_id': e.get('player_id'), 'name': e['name'], 'team': e.get('team'),
                         'position': e.get('position'), 'opponent': c.get('opponent'), 'known_at': known.get(c['week']), **r['metrics']})
        frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def features_through(frame, week, season):
    """Rows of one season that were played before ``week``. The only sanctioned way to build same-season features for a target week."""
    return frame[(frame.season == season) & (frame.week < week)]


def game_panel(root, cache=True):
    """Player-game panel merging the five player tables on (season, week, player_id, team). Cached under research/cache."""
    root = Path(root)
    path = champion.cache(root) / 'fp_weekly_panel.parquet'
    manifest = _manifest(root)
    stamp = json.dumps(sorted((t, s, e['sha256']) for t, mapping in ((t, _entries(manifest, t)) for t in PLAYER_TABLES.values()) for s, e in mapping.items()))
    stamp_path = path.with_suffix('.stamp')
    if cache and path.exists() and stamp_path.exists() and stamp_path.read_text() == stamp:
        return pd.read_parquet(path)
    panel = None
    for code, table in PLAYER_TABLES.items():
        frame = load_table(root, table)
        frame = frame.dropna(subset=['player_id'])
        meta = frame[['season', 'week', 'player_id', 'team', 'name', 'position', 'opponent', 'known_at']]
        metrics = frame.drop(columns=['name', 'position', 'opponent', 'known_at', 'team'])
        metrics = metrics.rename(columns={c: f'{code}.{c}' for c in metrics.columns if c not in ('season', 'week', 'player_id')})
        metrics = metrics.drop_duplicates(['season', 'week', 'player_id'], keep=False)  # an ambiguous duplicate is dropped, never guessed
        if panel is None:
            panel = meta.drop_duplicates(['season', 'week', 'player_id'], keep=False).merge(metrics, on=['season', 'week', 'player_id'], how='left')
        else:
            extra = meta.drop_duplicates(['season', 'week', 'player_id'], keep=False)
            panel = panel.merge(extra, on=['season', 'week', 'player_id'], how='outer', suffixes=('', '_y'))
            for c in ('team', 'name', 'position', 'opponent', 'known_at'):
                panel[c] = panel[c].fillna(panel[c + '_y'])
                panel = panel.drop(columns=[c + '_y'])
            panel = panel.merge(metrics, on=['season', 'week', 'player_id'], how='left')
    panel.to_parquet(path)
    stamp_path.write_text(stamp)
    return panel


def audit(root):
    """Availability matrix, identity rates, chronology and a content check of every by-game table against nflverse box scores."""
    root = Path(root)
    manifest = _manifest(root)
    weekly = champion.load_weekly(root, list(SEASONS))
    weekly = weekly[(weekly.season_type == 'REG')]
    out = {'tables': {}, 'checks': {}}
    for table in list(PLAYER_TABLES.values()) + list(TEAM_TABLES.values()):
        cells = {}
        entries = _entries(manifest, table)
        for season in SEASONS:
            e = entries.get(season)
            if not e:
                cells[str(season)] = {'status': 'NOT_IMPORTED'}
                continue
            cells[str(season)] = {'status': e['status'].upper(), 'rows': e['row_count'], 'weeks': [min(e['weeks']), max(e['weeks'])],
                                  'missing_weeks': [w for w in range(1, max(e['weeks']) + 1) if w not in e['weeks']], 'identity': e.get('identity'),
                                  'warnings': e.get('warnings')}
        out['tables'][table] = cells

    def compare(table, fp_col, nfl_col, label):
        frame = load_table(root, table).dropna(subset=['player_id'])
        frame = frame[frame[fp_col].notna()]
        res = {}
        merged = frame.merge(weekly[['season', 'week', 'player_id', 'team', nfl_col]], on=['season', 'week', 'player_id'], how='left', suffixes=('', '_nfl'))
        found = merged[nfl_col].notna()
        res['rows'] = int(len(merged))
        res['found_in_nflverse_same_week'] = float(found.mean())
        sub = merged[found]
        res['stat_equal_same_week'] = float((sub[fp_col].astype(float).round(0) == sub[nfl_col].astype(float).round(0)).mean())
        res['team_equal'] = float((sub['team'] == sub['team_nfl']).mean())
        shifted = {}
        for off in (-1, 1):
            alt = frame.assign(week=frame.week + off).merge(weekly[['season', 'week', 'player_id', nfl_col]], on=['season', 'week', 'player_id'], how='inner', suffixes=('', '_nfl'))
            shifted[str(off)] = float((alt[fp_col].astype(float).round(0) == alt[nfl_col].astype(float).round(0)).mean()) if len(alt) else None
        res['stat_equal_if_week_shifted'] = shifted
        out['checks'][label] = res
    compare('receiving_routes_run_weekly', 'Overall.TGT', 'targets', 'routes.TGT vs nflverse targets')
    compare('receiving_advanced_weekly', 'Receiving.REC', 'receptions', 'receiving_advanced.REC vs nflverse receptions')
    compare('receiving_advanced_weekly', 'Receiving.YDS', 'receiving_yards', 'receiving_advanced.YDS vs nflverse receiving yards')
    compare('efficiency_weekly', 'Rushing.ATT', 'carries', 'efficiency.rush ATT vs nflverse carries')
    compare('rushing_advanced_weekly', 'Rushing.YDS', 'rushing_yards', 'rushing_advanced.YDS vs nflverse rushing yards')
    compare('rushing_bell_cow_weekly', 'Rushing.ATT', 'carries', 'bell_cow.ATT vs nflverse carries')
    # coverage: nflverse players with real volume that a table lacks
    tgt = weekly[weekly.targets >= 3][['season', 'week', 'player_id']]
    for table, label in (('receiving_routes_run_weekly', 'routes'), ('receiving_advanced_weekly', 'receiving_advanced')):
        frame = load_table(root, table).dropna(subset=['player_id'])
        m = tgt.merge(frame[['season', 'week', 'player_id']].assign(have=1), how='left', on=['season', 'week', 'player_id'])
        seasons_have = set(frame.season)
        m = m[m.season.isin(seasons_have)]
        out['checks'][f'{label}: share of nflverse player-games with >=3 targets present'] = float(m.have.notna().mean())
    # team table vs nflverse team totals
    rp = load_table(root, 'run_pass_report_weekly')
    team_totals = weekly.groupby(['season', 'week', 'team'], as_index=False).agg(att=('attempts', 'sum'), carries=('carries', 'sum'), sacks=('sacks_suffered', 'sum'))
    rp = rp.merge(team_totals, on=['season', 'week', 'team'], how='left')
    rp['nfl_pass'] = rp.att + rp.sacks
    out['checks']['run_pass: Overall.RUSH vs nflverse team carries, share within 3'] = float(((rp['Overall.RUSH'] - rp.carries).abs() <= 3)[rp.carries.notna()].mean())
    out['checks']['run_pass: Overall.PASS vs nflverse attempts+sacks, share within 3'] = float(((rp['Overall.PASS'] - rp.nfl_pass).abs() <= 3)[rp.nfl_pass.notna()].mean())
    return out
