"""NFLMeta weekly game-status reports: dated designations for the current week.

nflverse injury rows carry no timezone-aware report clock, so the availability
gate could never verify their content time. NFLMeta re-checks each club's
official weekly report and publishes aware verification clocks. This module
fetches the current week once per refresh (shared through the git-ignored
.cache/), verifies every club report was checked recently, and merges NFLMeta
designations into the nflverse rows by exact roster identity.

Private, non-commercial use under the owner's key. The key is read only from the
NFLMETA_API_KEY environment variable and is never written, logged or published.
Raw NFLMeta responses stay in .cache/; published snapshots receive only the
designations GOING already shows plus provenance clocks and counts.
"""
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

from eligibility import _age_hours

BASE = 'https://nflmeta.org'
ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / '.cache' / 'nflmeta'
CACHE_MINUTES = 30
MAX_AGE_HOURS = 36
MIN_CLUB_REPORTS = 24
TEAM_ALIASES = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS', 'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
_SUFFIX = re.compile(r'\b(jr|sr|ii|iii|iv|v)\b')


def team_code(value):
    code = str(value or '').strip().upper()
    return TEAM_ALIASES.get(code, code) or None


def name_key(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    text = re.sub(r"[.'`]", '', text)
    return re.sub(r'[^a-z0-9]', '', _SUFFIX.sub(' ', text))


def surname_key(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    parts = [t for t in re.sub(r"[.'`]", '', _SUFFIX.sub(' ', text)).split() if t]
    return re.sub(r'[^a-z0-9]', '', parts[-1]) if parts else ''


def severity(status):
    s = str(status or '').strip().lower()
    if re.match(r'^(out|inactive)', s) or 'injured reserve' in s or 'suspend' in s:
        return 4
    if 'doubtful' in s:
        return 3
    if 'questionable' in s or re.match(r'^(game.?time|gtd)', s):
        return 2
    return 0


def _get(session, key, path, params):
    response = session.get(BASE + path, params=params, timeout=40,
                           headers={'X-NFLMeta-Key': key, 'Accept': 'application/json', 'User-Agent': 'going-long-refresh/1'})
    if response.status_code != 200:
        # Never echo request headers; the status code is enough to diagnose.
        raise RuntimeError(f'NFLMeta {path} returned HTTP {response.status_code}')
    return response.json()


def fetch_week(season, week, now=None, session=None, cache_dir=None):
    """All current-week report rows plus club report metadata, or None without a key."""
    key = os.environ.get('NFLMETA_API_KEY', '').strip()
    if not key:
        return None
    now = now or datetime.now(timezone.utc)
    cache_dir = Path(cache_dir or CACHE_DIR)
    cache = cache_dir / f'injuries-{season}-w{week}.json'
    try:
        cached = json.loads(cache.read_text(encoding='utf-8'))
        age = _age_hours(cached.get('fetched_at'), now)
        if age is not None and 0 <= age * 60 <= CACHE_MINUTES and cached.get('season') == season and cached.get('week') == week:
            return cached
    except (OSError, ValueError, AttributeError):
        pass
    session = session or requests
    rows, offset, meta = [], 0, None
    for _ in range(40):
        body = _get(session, key, '/api/v1/injuries', {'season': season, 'week': week, 'limit': 100, 'offset': offset})
        page, meta = body.get('data'), body.get('meta')
        if not isinstance(page, list) or not isinstance(meta, dict):
            raise RuntimeError('NFLMeta injuries response malformed')
        rows += page
        if not meta.get('has_more'):
            break
        if not page:
            raise RuntimeError('NFLMeta pagination returned an empty page')
        offset += len(page)
    else:
        raise RuntimeError('NFLMeta pagination did not finish')
    if meta.get('season_year') != season or meta.get('week') != week:
        raise RuntimeError('NFLMeta returned a different season/week')
    if isinstance(meta.get('total'), int) and meta['total'] != len(rows):
        raise RuntimeError('NFLMeta injuries incomplete')
    doc = {'fetched_at': now.isoformat(), 'season': season, 'week': week, 'rows': rows,
           'availability_reports': meta.get('availability_reports') or []}
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=cache_dir, delete=False) as tmp:
        json.dump(doc, tmp)
    os.replace(tmp.name, cache)
    return doc


def verify(doc, week, now=None):
    """Every club's weekly game-status report must have been checked successfully and recently."""
    now = now or datetime.now(timezone.utc)
    clubs = {}
    for report in doc.get('availability_reports') or []:
        if report.get('report_kind') != 'game_status' or report.get('week') != week:
            continue
        team = team_code(report.get('team_abbr'))
        if report.get('last_check_status') != 'succeeded' or report.get('coverage_status') not in ('complete', 'partial'):
            raise RuntimeError(f'NFLMeta {team} game-status report not verified')
        checked = report.get('last_checked_at')
        if _age_hours(checked, now) is None:
            raise RuntimeError(f'NFLMeta {team} report check time missing')
        if team not in clubs or _age_hours(checked, now) < _age_hours(clubs[team], now):
            clubs[team] = checked
    if len(clubs) < MIN_CLUB_REPORTS:
        raise RuntimeError(f'NFLMeta covers only {len(clubs)} club reports this week')
    oldest = max(clubs.values(), key=lambda t: _age_hours(t, now))
    if not -.5 <= _age_hours(oldest, now) <= MAX_AGE_HOURS:
        raise RuntimeError('NFLMeta club reports stale/future')
    verified_at = datetime.fromisoformat(oldest.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    return {'verified_at': verified_at, 'clubs': len(clubs)}


def merge(injury_rows, roster_rows, doc, season, week, verified_at):
    """Append dated NFLMeta designations to nflverse rows by unique team/name(/position) identity.

    Ambiguous names apply the designation to every matching player (fail closed). A
    less severe NFLMeta status never replaces a more severe nflverse one for the same week.
    """
    identities, surnames, names = {}, {}, {}
    for r in list(roster_rows) + list(injury_rows):
        if r.get('season') not in (None, season) or not r.get('gsis_id'):
            continue
        key = (team_code(r.get('team')), name_key(r.get('full_name')))
        identities.setdefault(key, {}).setdefault(r['gsis_id'], r.get('position'))
        surnames.setdefault((key[0], surname_key(r.get('full_name'))), {}).setdefault(r['gsis_id'], r.get('position'))
        names.setdefault(r['gsis_id'], (r.get('full_name'), team_code(r.get('team')), r.get('position')))
    existing = {}
    for r in injury_rows:
        if r.get('season') == season and r.get('season_type') == 'REG' and int(r.get('week') or 0) == week and r.get('gsis_id'):
            existing[r['gsis_id']] = max(existing.get(r['gsis_id'], 0), severity(r.get('report_status')))
    added, stats = [], {'designations': 0, 'matched': 0, 'ambiguous': 0, 'surname_fallback': 0, 'unresolved': 0, 'kept_more_severe': 0}
    for row in doc.get('rows') or []:
        if row.get('week') != week or row.get('season_year') != season or row.get('season_type', 'REG') != 'REG':
            continue
        status = 'Inactive' if row.get('game_status') == 'Inactive' else (row.get('game_status') or row.get('report_status'))
        if not status:
            continue
        stats['designations'] += 1
        team = team_code(row.get('team_abbr'))
        candidates = identities.get((team, name_key(row.get('display_name'))), {})
        if len(candidates) > 1 and row.get('position'):
            narrowed = {g: p for g, p in candidates.items() if p == row['position']}
            candidates = narrowed or candidates
        if not candidates:
            # Nicknames ("Josh"/"Joshua", "Hollywood"/"Marquise"): fall back to the same club and
            # surname (position-narrowed when possible). Over-matching only withholds players.
            candidates = surnames.get((team, surname_key(row.get('display_name'))), {})
            narrowed = {g: p for g, p in candidates.items() if p == row.get('position')}
            candidates = narrowed or candidates
            if not candidates:
                stats['unresolved'] += 1
                continue
            stats['surname_fallback'] += 1
        else:
            stats['ambiguous' if len(candidates) > 1 else 'matched'] += 1
        for gsis in candidates:
            if existing.get(gsis, 0) > severity(status):
                stats['kept_more_severe'] += 1
                continue
            full_name, roster_team, position = names[gsis]
            added.append({'season': season, 'season_type': 'REG', 'week': week, 'gsis_id': gsis, 'team': roster_team or team,
                          'full_name': full_name, 'position': position, 'report_status': status,
                          'practice_status': row.get('practice_status'),
                          'report_primary_injury': row.get('report_primary_injury'), 'report_secondary_injury': row.get('report_secondary_injury'),
                          'practice_primary_injury': row.get('practice_primary_injury'), 'practice_secondary_injury': row.get('practice_secondary_injury'),
                          'date_modified': verified_at, 'source': 'nflmeta'})
    digest = hashlib.sha256(json.dumps(sorted((r['gsis_id'], r['report_status']) for r in added)).encode()).hexdigest()
    return list(injury_rows) + added, {**stats, 'appended': len(added), 'designation_sha256': digest}
