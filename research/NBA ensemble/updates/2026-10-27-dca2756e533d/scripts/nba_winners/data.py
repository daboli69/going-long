"""Allowlisted schedule intake. Provider statistics/odds never enter predictors."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

TEAMS = set('ATL BOS BKN CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS'.split())
ALIASES = {'GS': 'GSW', 'SA': 'SAS', 'NY': 'NYK', 'NO': 'NOP', 'UTAH': 'UTA', 'WSH': 'WAS'}


def utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required; date-only inputs cannot establish tipoff')
    return result.astimezone(timezone.utc)


def stamp(value):
    return utc(value).isoformat().replace('+00:00', 'Z')


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def team(value):
    code = str(value).upper()
    return ALIASES.get(code, code)


def validate_games(rows):
    """Strict canonical boundary; identical repeats deduplicate, conflicts fail."""
    games = {}
    for row in rows:
        g = {key: row[key] for key in ('game_id', 'season', 'tipoff', 'home', 'away', 'neutral', 'completed', 'home_score', 'away_score')}
        g['game_id'] = str(g['game_id'])
        if not g['game_id'] or type(g['season']) is not int or not 2002 <= g['season'] <= 2100:
            raise ValueError('Invalid game ID / ending-year season')
        g['home'], g['away'] = team(g['home']), team(g['away'])
        if g['home'] not in TEAMS or g['away'] not in TEAMS or g['home'] == g['away']:
            raise ValueError(f'Invalid NBA teams: {g["game_id"]}')
        g['tipoff'] = stamp(g['tipoff'])
        if type(g['neutral']) is not bool or type(g['completed']) is not bool:
            raise ValueError('Explicit Boolean neutral and completed flags required')
        if g['completed']:
            scores = [g['home_score'], g['away_score']]
            if any(type(s) is not int or s < 0 for s in scores) or scores[0] == scores[1]:
                raise ValueError(f'Invalid final NBA scores: {g["game_id"]}')
        else:
            # Discard in-progress scores and unplayed zero placeholders.
            g['home_score'] = g['away_score'] = None
        if g['game_id'] in games and games[g['game_id']] != g:
            raise ValueError(f'Conflicting duplicate game: {g["game_id"]}')
        games[g['game_id']] = g
    if not games:
        raise ValueError('No eligible NBA regular-season games')
    return sorted(games.values(), key=lambda g: (g['tipoff'], g['game_id']))


def normalize_sdv(rows):
    """Shared ESPN schedule schema from hoopR / sportsdataverse loaders."""
    accepted, excluded = [], Counter()
    for row in rows:
        if row.get('season_type') != 2:
            excluded['outside_regular_season'] += 1
            continue
        if team(row.get('home_abbreviation')) not in TEAMS or team(row.get('away_abbreviation')) not in TEAMS:
            excluded['exhibition_or_unknown_team'] += 1
            continue
        note = str(row.get('notes_headline') or '').lower()
        if 'championship' in note and ('cup' in note or 'in-season tournament' in note):
            excluded['cup_final_not_regular_season'] += 1
            continue
        if row.get('status_type_name') not in ('STATUS_FINAL', 'STATUS_SCHEDULED'):
            excluded['postponed_cancelled_or_in_progress'] += 1
            continue
        if row.get('time_valid') is not True or type(row.get('neutral_site')) is not bool:
            excluded['unverified_time_or_venue'] += 1
            continue
        final = row['status_type_name'] == 'STATUS_FINAL'
        if row.get('status_type_completed') is not final:
            raise ValueError('Conflicting provider final/completed flags')
        accepted.append(dict(game_id=f'espn:{row["game_id"]}', season=row['season'],
                             tipoff=row['date'], home=row['home_abbreviation'], away=row['away_abbreviation'],
                             neutral=row['neutral_site'], completed=final,
                             home_score=row.get('home_score'), away_score=row.get('away_score')))
    return validate_games(accepted), dict(excluded)


def snapshot(games, sources, excluded=None):
    games = validate_games(games)
    body = {'schema_version': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'games': games, 'sources': sources, 'excluded': excluded or {},
            'freshness_verified': bool(sources) and all(s.get('retrieved_at') for s in sources)}
    body['sha256'] = digest(body)
    return body


def load_snapshot(path):
    body = json.loads(Path(path).read_text())
    expected = body.pop('sha256')
    if digest(body) != expected:
        raise ValueError('Snapshot hash mismatch')
    body['sha256'] = expected
    utc(body['observed_at'])
    body['games'] = validate_games(body['games'])
    return body


def write_new(path, body):
    """Never overwrite an experiment or source receipt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as out:
        json.dump(body, out, indent=2, allow_nan=False)
        out.write('\n')
