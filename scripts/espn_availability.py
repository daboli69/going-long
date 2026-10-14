"""Free, dated, explicit-player fallback. A capped injury list cannot clear absences."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from eligibility import _age_hours
from nflmeta_source import name_key, team_code

URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'
CACHE = Path(__file__).resolve().parents[1] / '.cache/espn-availability'
STATUSES = {'Active': 'active', 'Questionable': 'Questionable', 'Out': 'Out',
            'Doubtful': 'Doubtful', 'Injured Reserve': 'Injured Reserve',
            'Suspension': 'suspended', 'Reserve-Ret': 'Out'}


def report_clock(value):
    # ESPN publishes minute-resolution UTC clocks. Normalize explicitly, without
    # substituting the endpoint's request timestamp or our download time.
    if isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z', value):
        value = value[:-1] + ':00Z'
    return value if _age_hours(value, datetime.now(timezone.utc)) is not None else None


def espn_id(athlete):
    ids = set()
    for link in athlete.get('links') or []:
        parsed = urlparse(str(link.get('href') or ''))
        if parsed.hostname not in ('www.espn.com', 'espn.com'):
            continue
        match = re.match(r'^/nfl/player/(?:[^/]+/)*_?/id/(\d+)(?:/|$)', parsed.path)
        if match:
            ids.add(match[1])
    return next(iter(ids)) if len(ids) == 1 else None


def merge_explicit(doc, roster, season, week, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(doc, dict) or doc.get('status') != 'success' or doc.get('season', {}).get('year') != season or doc.get('season', {}).get('type') != 2 or not isinstance(doc.get('injuries'), list):
        raise RuntimeError('ESPN current injury response malformed or wrong season')
    current = [r for r in roster if r.get('season') == season and r.get('game_type') == 'REG' and r.get('week') == week]
    identities = {}
    for r in current:
        key = str(r.get('espn_id') or '')
        if key:
            identities.setdefault(key, []).append(r)
    selected, conflicts = {}, set()
    for group in doc['injuries']:
        if not isinstance(group, dict) or not isinstance(group.get('injuries'), list):
            raise RuntimeError('ESPN team injury response malformed')
        for row in group['injuries']:
            if not isinstance(row, dict) or not isinstance(row.get('athlete'), dict):
                raise RuntimeError('ESPN player injury response malformed')
            athlete = row['athlete']; key = espn_id(athlete)
            candidates = identities.get(key, [])
            if len(candidates) != 1:
                continue
            player = candidates[0]; gid = player.get('gsis_id')
            team = athlete.get('team') or {}
            if not gid or str(team.get('id')) != str(group.get('id')) or team_code(team.get('abbreviation')) != team_code(player.get('team')) or name_key(athlete.get('displayName')) != name_key(player.get('full_name')):
                if gid:
                    conflicts.add(gid)
                continue
            stamp = report_clock(row.get('date'))
            status = STATUSES.get(row.get('status'))
            if not stamp or not status:
                conflicts.add(gid)
                continue
            age = _age_hours(stamp, now)
            if age is None or age < -.5:
                conflicts.add(gid)
                continue
            previous = selected.get(gid)
            if previous and previous['date_modified'] == stamp and previous['report_status'] != status:
                conflicts.add(gid)
            if previous and _age_hours(previous['date_modified'], now) < age:
                continue
            selected[gid] = {'season': season, 'season_type': 'REG', 'week': week,
                             'gsis_id': gid, 'full_name': player['full_name'], 'team': player['team'],
                             'position': player.get('position'), 'report_status': status,
                             'date_modified': stamp, 'source': 'ESPN explicit player injury report'}
    # Keep dated severe reports as exclusions, even if too old to clear anyone.
    rows = list(selected.values())
    verified = {gid: {'team': row['team'], 'reported_at': row['date_modified']}
                for gid, row in selected.items() if gid not in conflicts and 0 <= _age_hours(row['date_modified'], now) <= 36}
    if not verified:
        raise RuntimeError('ESPN has no fresh exact-identity player reports; previous availability retained')
    latest = min((r['reported_at'] for r in verified.values()), key=lambda t: _age_hours(t, now))
    scope = {'mode': 'explicit-player-reports', 'season': season, 'week': week, 'players': verified}
    fingerprint = hashlib.sha256(json.dumps({'rows': rows, 'scope': scope}, sort_keys=True).encode()).hexdigest()
    return rows, {'provider': 'ESPN public dated player injury reports', 'url': URL,
                  'report_content_at': latest, 'sha256': fingerprint, 'availability_verification': scope,
                  'timestamp_basis': 'Latest dated player report; each player expires independently; endpoint request timestamp ignored',
                  'note': 'Capped list: missing, stale, ambiguous and unmatched players are not cleared.'}


def fetch_explicit(roster, season, week, now=None):
    now = now or datetime.now(timezone.utc)
    cache = CACHE / f'{season}-w{week}.json'
    doc = None
    try:
        saved = json.loads(cache.read_text(encoding='utf-8'))
        age = _age_hours(saved.get('fetched_at'), now)
        if age is not None and 0 <= age <= .5:
            doc = saved['data']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    if doc is None:
        response = requests.get(URL, timeout=30)
        response.raise_for_status()
        doc = response.json()
        # Validate before caching; cache time never clears a player.
        merge_explicit(doc, roster, season, week, now)
        CACHE.mkdir(parents=True, exist_ok=True)
        temp = cache.with_suffix('.tmp')
        temp.write_text(json.dumps({'fetched_at': now.isoformat(), 'data': doc}), encoding='utf-8')
        temp.replace(cache)
    return merge_explicit(doc, roster, season, week, now)
