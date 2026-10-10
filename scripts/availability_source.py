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


def source_stamp(value):
    """Normalize aware row clocks; never guess a timezone for source content."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else None
    if isinstance(value, str) and _age_hours(value, datetime.now(timezone.utc)) is not None:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
    return None


def load_source(kind, season, now=None):
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
        report_stamps = [source_stamp(r.get('date_modified')) for r in rows
                         if r.get('season_type') == 'REG' and int(r.get('week') or 0) == week]
        dated = [t for t in report_stamps if _age_hours(t, now) is not None]
        if not dated:
            raise RuntimeError('injuries: current report-content timestamps unavailable; previous snapshot retained')
        latest = min(dated, key=lambda t: _age_hours(t, now))
        if not -.5 <= _age_hours(latest, now) <= 36:
            raise RuntimeError('injuries: current report content stale/future; previous snapshot retained')
        metadata['uploaded_at'] = stamp
        metadata['report_content_at'] = latest
        metadata['content_at'] = max((stamp, latest), key=lambda t: _age_hours(t, now))
        metadata['timestamp_basis'] = 'Earlier of exact-byte HTTP Last-Modified and latest dated current-week report'
    return rows, metadata


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
            payload[key] = old.get(key) or prior_source.get('content_at')
            source['content_at'] = payload[key]
    for key in ('source_content_at', 'source_roster_at', 'source_injury_at'):
        prior, new = old.get(key), payload.get(key)
        if key in payload and (_age_hours(new, now) is None or not -.5 <= _age_hours(new, now) <= 36):
            raise RuntimeError('Source content stale/future; previous snapshot retained')
        if prior and (not new or _age_hours(new, now) is None or
                      datetime.fromisoformat(prior.replace('Z', '+00:00')) > datetime.fromisoformat(new.replace('Z', '+00:00'))):
            raise RuntimeError('Newer production availability exists; previous snapshot retained')
    reports = list((old.get('current_reports') or {}).values()) + [p.get('injury') for p in old.get('players', []) if isinstance(p, dict)]
    new_injury = payload.get('source_content_at') or payload.get('source_injury_at')
    if new_injury and any(isinstance(r, dict) and _age_hours(r.get('reported_at'), now) is not None and
                         _age_hours(r['reported_at'], now) < _age_hours(new_injury, now) for r in reports):
        raise RuntimeError('Newer production injury reports exist; previous snapshot retained')
