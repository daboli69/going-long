"""Read exact free nflverse availability bytes with source upload provenance.

Request/cache/file-write time never substitutes for source-content time.
"""
import hashlib
import io
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from eligibility import _age_hours
import nflmeta_source


def source_stamp(value):
    """Normalize aware row clocks; never guess a timezone for source content."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else None
    if isinstance(value, str) and _age_hours(value, datetime.now(timezone.utc)) is not None:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    return None


def load_source(kind, season, now=None, roster=None):
    import polars as pl
    names = {'injuries': f'injuries/injuries_{season}',
             'rosters': f'weekly_rosters/roster_weekly_{season}'}
    url = 'https://github.com/nflverse/nflverse-data/releases/download/' + names[kind] + '.parquet'
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    try:
        uploaded = parsedate_to_datetime(response.headers['Last-Modified'])
        if uploaded.tzinfo is None:
            raise ValueError('source upload clock must include timezone')
        stamp = uploaded.astimezone(timezone.utc).isoformat()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f'{kind}: source upload timestamp unavailable; previous snapshot retained') from exc
    now = now or datetime.now(timezone.utc)
    age = _age_hours(stamp, now)
    if age is None or age < -.5 or age > 36:
        raise RuntimeError(f'{kind}: source content stale/future; previous snapshot retained')
    rows = pl.read_parquet(io.BytesIO(response.content)).to_dicts()
    metadata = {
        'content_at': stamp, 'sha256': hashlib.sha256(response.content).hexdigest(),
        'url': url, 'timestamp_basis': 'HTTP Last-Modified for the exact downloaded parquet bytes'}
    if kind == 'injuries':
        week = max((int(r.get('week') or 0) for r in rows if r.get('season_type') == 'REG'), default=0)
        # nflverse report rows carry no aware report clock. NFLMeta's verified weekly
        # club reports supply dated designations; without them the gate stays closed.
        try:
            verified = None
            weekly = nflmeta_source.fetch_week(season, week, now)
            if weekly is not None:
                playing = {nflmeta_source.team_code(r.get('team')) for r in roster or []
                           if r.get('season') == season and r.get('game_type') == 'REG' and r.get('week') == week and r.get('team')}
                verified = nflmeta_source.verify(weekly, week, now, required_teams=playing)
        except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as exc:
            print(f'[availability] NFLMeta verification unavailable: {exc}')
            verified = None
        if verified:
            # Date merged designations no later than the nflverse bytes they join, so a
            # report is never newer than the snapshot's own content clock on the next run.
            as_of = min((stamp, verified['verified_at']), key=lambda t: datetime.fromisoformat(t.replace('Z', '+00:00')))
            rows, merged = nflmeta_source.merge(rows, roster or [], weekly, season, week, as_of)
            metadata['nflmeta'] = {'provider': 'NFLMeta weekly club game-status reports', 'verified_at': verified['verified_at'],
                                   'club_reports': verified['clubs'], **merged}
            # Unchanged nflverse bytes with changed verified designations are new content.
            metadata['sha256'] = hashlib.sha256((metadata['sha256'] + merged['designation_sha256']).encode()).hexdigest()
        report_stamps = [source_stamp(r.get('date_modified')) for r in rows
                         if r.get('season_type') == 'REG' and int(r.get('week') or 0) == week]
        dated = [t for t in report_stamps if _age_hours(t, now) is not None]
        latest = min(dated, key=lambda t: _age_hours(t, now)) if dated else None
        if not verified or not latest or not -.5 <= _age_hours(latest, now) <= 36:
            # Midweek final game-status reports can be incomplete. A public dated
            # player report can verify that player only, never an unlisted teammate.
            from espn_availability import fetch_explicit
            try:
                explicit, fallback = fetch_explicit(roster or [], season, week, now)
            except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as exc:
                raise RuntimeError('injuries: current report content stale or unavailable; explicit-player fallback unavailable; previous snapshot retained') from exc
            rows += explicit
            metadata['nflverse'] = {'url': metadata['url'], 'sha256': metadata['sha256'], 'uploaded_at': stamp}
            metadata.update(fallback)
            metadata['sha256'] = hashlib.sha256((metadata['nflverse']['sha256'] + fallback['sha256']).encode()).hexdigest()
            metadata['uploaded_at'] = stamp
            metadata['content_at'] = min((stamp, fallback['report_content_at']), key=lambda t: datetime.fromisoformat(t.replace('Z', '+00:00')))
            return rows, metadata
        metadata['uploaded_at'] = stamp
        metadata['report_content_at'] = latest
        metadata['content_at'] = max((stamp, latest), key=lambda t: _age_hours(t, now))
        metadata['timestamp_basis'] = 'Earlier of exact-byte HTTP Last-Modified and latest dated current-week report' + (' (NFLMeta club-report verification)' if 'nflmeta' in metadata else '')
    return rows, metadata


def scoped_snapshot(payload, source):
    if 'availability_verification' not in source:
        return
    payload['availability_verification'] = source['availability_verification']
    payload['schema_version'] = 2
    payload['status'] = 'PARTIAL'
    key = 'source_content_at' if 'current_players' in payload else 'source_injury_at'
    payload['restricted_' + key] = payload[key]
    # Old/open browser engines do not understand restricted scopes. Missing the
    # legacy clock forces them to remain paused instead of clearing everyone.
    payload[key] = None


def content_clock(doc, key):
    if key in ('source_content_at', 'source_injury_at') and (doc.get('availability_verification') or {}).get('mode') == 'explicit-player-reports':
        return doc.get('restricted_' + key)
    return doc.get(key)


def preserve_newer(path, payload):
    """Do not replace a source version newer than the downloaded availability."""
    if not path.exists():
        return
    old = json.loads(path.read_text(encoding='utf-8'))
    now = datetime.now(timezone.utc)
    old_sources, new_sources = old.get('sources') or {}, payload.get('sources') or {}
    # Re-uploading identical bytes is not new information. Keep their original
    # observed upload clock, and let stale unchanged content fail closed.
    for key, source_name in (('source_content_at', 'injuries'), ('source_injury_at', 'injuries'),
                             ('source_roster_at', 'weekly_rosters' if 'source_content_at' in payload else 'rosters')):
        if key not in payload:
            continue
        prior_source, source = old_sources.get(source_name), new_sources.get(source_name)
        if isinstance(prior_source, dict) and isinstance(source, dict) and prior_source.get('sha256') and prior_source['sha256'] == source.get('sha256'):
            target = 'restricted_' + key if key in ('source_content_at', 'source_injury_at') and 'availability_verification' in payload else key
            payload[target] = content_clock(old, key) or prior_source.get('content_at')
            source['content_at'] = payload[target]
    for key in ('source_content_at', 'source_roster_at', 'source_injury_at'):
        prior, new = content_clock(old, key), content_clock(payload, key)
        if key in payload and (_age_hours(new, now) is None or not -.5 <= _age_hours(new, now) <= 36):
            raise RuntimeError('Source content stale/future; previous snapshot retained')
        if prior and (not new or _age_hours(new, now) is None or
                      datetime.fromisoformat(prior.replace('Z', '+00:00')) > datetime.fromisoformat(new.replace('Z', '+00:00'))):
            raise RuntimeError('Newer production availability exists; previous snapshot retained')
    reports = [(r.get('gsis_id'), r) for r in (old.get('current_reports') or {}).values() if isinstance(r, dict)] + [(p.get('id'), p.get('injury')) for p in old.get('players', []) if isinstance(p, dict)]
    new_injury = content_clock(payload, 'source_content_at') or content_clock(payload, 'source_injury_at')
    incoming = {r.get('gsis_id'): r for r in (payload.get('current_reports') or {}).values() if isinstance(r, dict)}
    incoming.update({p.get('id'): p.get('injury') for p in payload.get('players', []) if isinstance(p, dict) and isinstance(p.get('injury'), dict)})
    restricted = (payload.get('availability_verification') or {}).get('mode') == 'explicit-player-reports'
    for gid, report in reports:
        if not new_injury or not isinstance(report, dict) or _age_hours(report.get('reported_at'), now) is None or _age_hours(report['reported_at'], now) >= _age_hours(new_injury, now):
            continue
        # In restricted mode the dated report may be newer than the paired roster
        # file. Compare that player's actual incoming report, not the lower bound.
        replacement = incoming.get(gid) if gid else None
        replacement_age = _age_hours(replacement.get('reported_at'), now) if isinstance(replacement, dict) else None
        if not restricted or replacement_age is None or replacement_age > _age_hours(report['reported_at'], now):
            raise RuntimeError('Newer production injury reports exist; previous snapshot retained')
