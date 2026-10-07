"""Deterministic player/team identity for Fantasy Points rows. No fuzzy matching: ambiguous or unknown stays reported.

Canonical identity is the nflverse ``gsis_id`` already used across GOING (``data/nfl_roster.json``, opportunity evidence).
Team codes are nflverse abbreviations (LA, not LAR). This module is deliberately source-agnostic (a list of roster rows in,
decisions out) so the prop-name matching work can reuse it instead of growing a second resolver.
"""
import csv
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}
# Fantasy Points uses ARZ/BLT/CLV/HST; everything else already matches nflverse.
TEAM_ALIASES = {'ARZ': 'ARI', 'BLT': 'BAL', 'CLV': 'CLE', 'HST': 'HOU', 'LAR': 'LA', 'WSH': 'WAS', 'JAC': 'JAX', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
TEAMS = {'ARI', 'ATL', 'BAL', 'BUF', 'CAR', 'CHI', 'CIN', 'CLE', 'DAL', 'DEN', 'DET', 'GB', 'HOU', 'IND', 'JAX', 'KC', 'LA', 'LAC', 'LV', 'MIA',
         'MIN', 'NE', 'NO', 'NYG', 'NYJ', 'PHI', 'PIT', 'SEA', 'SF', 'TB', 'TEN', 'WAS'}
TEAM_NAMES = {
    'arizona cardinals': 'ARI', 'atlanta falcons': 'ATL', 'baltimore ravens': 'BAL', 'buffalo bills': 'BUF', 'carolina panthers': 'CAR',
    'chicago bears': 'CHI', 'cincinnati bengals': 'CIN', 'cleveland browns': 'CLE', 'dallas cowboys': 'DAL', 'denver broncos': 'DEN',
    'detroit lions': 'DET', 'green bay packers': 'GB', 'houston texans': 'HOU', 'indianapolis colts': 'IND', 'jacksonville jaguars': 'JAX',
    'kansas city chiefs': 'KC', 'los angeles rams': 'LA', 'los angeles chargers': 'LAC', 'las vegas raiders': 'LV', 'miami dolphins': 'MIA',
    'minnesota vikings': 'MIN', 'new england patriots': 'NE', 'new orleans saints': 'NO', 'new york giants': 'NYG', 'new york jets': 'NYJ',
    'philadelphia eagles': 'PHI', 'pittsburgh steelers': 'PIT', 'seattle seahawks': 'SEA', 'san francisco 49ers': 'SF', 'tampa bay buccaneers': 'TB',
    'tennessee titans': 'TEN', 'washington commanders': 'WAS',
}
POSITION_GROUP = {'QB': 'QB', 'RB': 'RB', 'HB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE'}


class TeamError(ValueError):
    pass


def canonical_team(value):
    code = str(value or '').strip()
    upper = code.upper()
    if upper in TEAMS:
        return upper
    if upper in TEAM_ALIASES:
        return TEAM_ALIASES[upper]
    named = TEAM_NAMES.get(re.sub(r'\s+', ' ', code.lower()))
    if named:
        return named
    raise TeamError(f'unknown team {value!r}')


def name_tokens(name):
    text = unicodedata.normalize('NFKD', str(name or '')).encode('ascii', 'ignore').decode().lower()
    text = re.sub(r"[.'’]", '', text).replace('-', ' ')
    tokens = [t for t in re.sub(r'[^a-z0-9 ]', ' ', text).split() if t]
    while len(tokens) > 1 and tokens[-1] in SUFFIXES:
        tokens.pop()
    return tokens


def norm_name(name):
    return ''.join(name_tokens(name))


def position_group(position):
    return POSITION_GROUP.get(str(position or '').strip().upper())


class RosterIndex:
    """Index of roster rows ``{gsis_id, full_name, team, position}`` for one season."""

    def __init__(self, rows, aliases=None):
        self.players = {}
        self.by_name_team, self.by_name, self.by_initial_team = {}, {}, {}
        self.aliases = {str(k): v for k, v in (aliases or {}).items()}
        for row in rows:
            pid, name = row.get('gsis_id') or row.get('id'), row.get('full_name') or row.get('name')
            team = row.get('team')
            if not pid or not name or not team:
                continue
            try:
                team = canonical_team(team)
            except TeamError:
                continue
            tokens = name_tokens(name)
            if not tokens:
                continue
            self.players.setdefault(pid, {'id': pid, 'name': name, 'teams': set(), 'position': row.get('position')})['teams'].add(team)
            key = ''.join(tokens)
            self.by_name_team.setdefault((key, team), set()).add(pid)
            self.by_name.setdefault(key, set()).add(pid)
            self.by_initial_team.setdefault((tokens[0][0], tokens[-1], team), set()).add(pid)

    def _compatible(self, pids, group):
        if not group:
            return sorted(pids)
        return sorted(p for p in pids if position_group(self.players[p]['position']) in (group, None))

    def resolve(self, name, team, position):
        """Return {status, player_id, method, candidates, note}. status: matched | ambiguous | unmatched | team_unknown."""
        try:
            code = canonical_team(team)
        except TeamError:
            return {'status': 'team_unknown', 'player_id': None, 'method': None, 'candidates': [], 'note': f'unknown team {team!r}'}
        group, key, tokens = position_group(position), norm_name(name), name_tokens(name)
        override = self.aliases.get(f'{key}|{code}')
        if override:
            return {'status': 'matched', 'player_id': override, 'method': 'alias', 'candidates': [override], 'note': None}

        def decide(pids, method, note=None):
            if len(pids) == 1:
                return {'status': 'matched', 'player_id': pids[0], 'method': method, 'candidates': pids, 'note': note}
            if len(pids) > 1:
                return {'status': 'ambiguous', 'player_id': None, 'method': method, 'candidates': pids, 'note': 'more than one roster player fits'}
            return None

        same_team = sorted(self.by_name_team.get((key, code), ()))
        found = decide(self._compatible(same_team, group), 'name_team_position') if same_team else None
        if found:
            return found
        found = decide(same_team, 'name_team', 'position differs from roster') if same_team else None
        if found:
            return found
        league = sorted(self.by_name.get(key, ()))
        if league:
            found = decide(self._compatible(league, group), 'name_position', 'team differs from roster (trade, release or stale roster)')
            if found:
                return found
        if len(tokens) >= 2 and len(tokens[0]) == 1:
            pids = sorted(self.by_initial_team.get((tokens[0][0], tokens[-1], code), ()))
            found = decide(self._compatible(pids, group), 'initial_last_team_position', 'first name abbreviated in source')
            if found:
                return found
        return {'status': 'unmatched', 'player_id': None, 'method': None, 'candidates': [], 'note': 'no roster player with this name'}


def read_roster_csv(path):
    with open(path, encoding='utf-8', newline='') as handle:
        return [{'gsis_id': r.get('gsis_id'), 'full_name': r.get('full_name'), 'team': r.get('team'), 'position': r.get('position'),
                 'season': r.get('season'), 'status': r.get('status')} for r in csv.DictReader(handle)]


def read_repo_roster(path, season):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if int(data.get('season') or 0) != int(season):
        return []
    return [{'gsis_id': p.get('id'), 'full_name': p.get('name'), 'team': p.get('team'), 'position': p.get('position')} for p in data.get('players', [])]


def download_roster(season, destination):
    """Public nflverse roster file (free, not licensed data). Raises on any network or format problem."""
    url = f'https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{int(season)}.csv'
    with urllib.request.urlopen(url, timeout=60) as response:
        body = response.read()
    if b'gsis_id' not in body[:2000]:
        raise ValueError('unexpected roster file format')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_bytes(body)
    temporary.replace(destination)
    return destination
