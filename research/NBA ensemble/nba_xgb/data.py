"""Canonical, immutable historical game table rebuilt from the raw source archive.

Sources: SportsDataverse/ESPN schedule and team box-score parquet files already archived
under data/raw/archive. Nothing here uses power rankings, odds or season leaderboards.
"""
from __future__ import annotations
import glob
import hashlib
import json
import re
import stat
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'data' / 'raw' / 'archive'
OUT = ROOT / 'research_nba_xgb'
CANON = OUT / 'canonical'
FIRST_SEASON, LAST_SEASON = 2015, 2027
BOX_COLS = {'team_score': 'points', 'field_goals_made': 'fgm', 'field_goals_attempted': 'fga',
            'three_point_field_goals_made': 'fg3m', 'three_point_field_goals_attempted': 'fg3a',
            'free_throws_made': 'ftm', 'free_throws_attempted': 'fta', 'offensive_rebounds': 'oreb',
            'defensive_rebounds': 'dreb', 'turnovers': 'tov', 'team_turnovers': 'team_tov',
            'assists': 'ast', 'steals': 'stl', 'blocks': 'blk'}


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshots(kind: str, season: int) -> list[dict]:
    """All archived snapshots for one source, oldest first, with retrieval time from the file name."""
    out = []
    for f in sorted(glob.glob(str(ARCHIVE / f'{kind}_{season}' / '*.parquet'))):
        m = re.match(r'(\d{8}T\d{6})\d*Z_', Path(f).name)
        out.append({'path': f, 'retrieved_utc': pd.Timestamp(m.group(1), tz='UTC').isoformat(), 'sha256': sha256(f)})
    return out


def load_team_ids() -> set[str]:
    f = sorted(glob.glob(str(ARCHIVE / 'nba_team_directory' / '*.json')))[-1]
    d = json.loads(Path(f).read_text(encoding='utf-8'))
    return {str(r['team']['id']) for r in d['sports'][0]['leagues'][0]['teams']}


def normalize_schedule(raw: pd.DataFrame, team_ids: set[str]) -> pd.DataFrame:
    d = raw[raw.season_type.eq(2)].copy()
    d = d[~d.status_type_name.fillna('').str.contains('POSTPONED|CANCELED|CANCELLED', case=False)]
    d = d[~d.notes_headline.fillna('').str.contains(r'(?:Cup|Tournament).*Championship', case=False, regex=True)]
    tip = pd.to_datetime(d.date, utc=True, errors='coerce')
    out = pd.DataFrame({
        'game_id': d.game_id.astype(str), 'season': d.season.astype(int), 'tipoff_utc': tip,
        'game_date': tip.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d'),
        'time_valid': d.time_valid.fillna(False).astype(bool),
        'home_id': d.home_id.astype(str), 'away_id': d.away_id.astype(str),
        'home': d.home_abbreviation, 'away': d.away_abbreviation,
        'neutral': d.neutral_site.fillna(False).astype(bool),
        'completed': d.status_type_completed.eq(True),
        'went_to_ot': pd.to_numeric(d.status_period, errors='coerce').fillna(4).gt(4),
        'home_score': pd.to_numeric(d.home_score, errors='coerce'),
        'away_score': pd.to_numeric(d.away_score, errors='coerce')})
    out = out.dropna(subset=['tipoff_utc', 'home', 'away'])
    out = out[out.home_id.isin(team_ids) & out.away_id.isin(team_ids) & out.home_id.ne(out.away_id)]
    return out


def normalize_box(raw: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({'game_id': raw.game_id.astype(str), 'team_id': raw.team_id.astype(str)})
    for src, dst in BOX_COLS.items():
        out[dst] = pd.to_numeric(raw[src], errors='coerce')
    return out.drop_duplicates()


def build(write: bool = True) -> dict:
    team_ids = load_team_ids()
    games, boxes, sources, issues = [], [], [], []
    for season in range(FIRST_SEASON, LAST_SEASON + 1):
        for kind, bucket, norm in (('schedule', games, lambda r: normalize_schedule(r, team_ids)),
                                   ('team_box', boxes, normalize_box)):
            snaps = snapshots(kind, season)
            if not snaps:
                issues.append({'season': season, 'source': kind, 'issue': 'no archived snapshot'})
                continue
            frame = norm(pd.read_parquet(snaps[-1]['path']))
            bucket.append(frame)
            sources.append({'kind': kind, 'season': season, 'n_snapshots': len(snaps), 'used': snaps[-1],
                            'rows_normalized': len(frame)})
    g = pd.concat(games, ignore_index=True)
    b = pd.concat(boxes, ignore_index=True)
    if g.game_id.duplicated().any():
        raise ValueError('duplicate canonical game ids')
    if b.duplicated(['game_id', 'team_id']).any():
        raise ValueError('conflicting duplicate team boxes')
    b = b[b.game_id.isin(g.game_id)]

    # Per-game verification of the final result against independent box components.
    h = b.add_prefix('h_').rename(columns={'h_game_id': 'game_id', 'h_team_id': 'home_id'})
    a = b.add_prefix('a_').rename(columns={'a_game_id': 'game_id', 'a_team_id': 'away_id'})
    v = g.merge(h, on=['game_id', 'home_id'], how='left').merge(a, on=['game_id', 'away_id'], how='left')
    v['has_box'] = v.h_points.notna() & v.a_points.notna()
    v['score_matches_box'] = (v.h_points == v.home_score) & (v.a_points == v.away_score)
    v['h_identity'] = v.h_points == 2 * v.h_fgm + v.h_fg3m + v.h_ftm
    v['a_identity'] = v.a_points == 2 * v.a_fgm + v.a_fg3m + v.a_ftm
    v['verified'] = (v.completed & v.has_box & v.score_matches_box & v.h_identity & v.a_identity
                     & v.home_score.ne(v.away_score))
    g = g.merge(v[['game_id', 'has_box', 'score_matches_box', 'h_identity', 'a_identity', 'verified']], on='game_id')
    g['home_win'] = (g.home_score > g.away_score).where(g.completed).astype('float')
    src_ret = {s['season']: s['used']['retrieved_utc'] for s in sources if s['kind'] == 'schedule'}
    g['source_retrieved_utc'] = g.season.map(src_ret)
    g = g.sort_values(['tipoff_utc', 'game_id']).reset_index(drop=True)

    cov = g.groupby('season').agg(games=('game_id', 'size'), completed=('completed', 'sum'),
                                  verified=('verified', 'sum'), with_box=('has_box', 'sum'),
                                  neutral=('neutral', 'sum'), overtime=('went_to_ot', 'sum'),
                                  first_date=('game_date', 'min'), last_date=('game_date', 'max'),
                                  home_win_rate=('home_win', 'mean')).reset_index()
    summary = {'sources': sources, 'issues': issues, 'coverage': json.loads(cov.to_json(orient='records')),
               'team_ids': len(team_ids)}
    if write:
        CANON.mkdir(parents=True, exist_ok=True)
        manifest = {}
        for name, frame in {'games.parquet': g, 'team_boxes.parquet': b}.items():
            p = CANON / name
            if p.exists():
                p.chmod(stat.S_IWRITE | stat.S_IREAD)
            frame.to_parquet(p, index=False)
            p.chmod(stat.S_IREAD)
            manifest[name] = {'sha256': sha256(p), 'rows': len(frame)}
        summary['manifest'] = manifest
        (CANON / 'MANIFEST.json').write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')
    return summary


def load(verify: bool = True):
    """Read the canonical tables, optionally re-checking their frozen hashes."""
    if verify:
        man = json.loads((CANON / 'MANIFEST.json').read_text(encoding='utf-8'))['manifest']
        for name, meta in man.items():
            if sha256(CANON / name) != meta['sha256']:
                raise RuntimeError(f'canonical file {name} changed after freezing')
    return pd.read_parquet(CANON / 'games.parquet'), pd.read_parquet(CANON / 'team_boxes.parquet')


if __name__ == '__main__':
    s = build()
    print(pd.DataFrame(s['coverage']).to_string())
    print(s['issues'])
