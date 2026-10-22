"""Opt-in, private NFL Meta injury fallback; never modifies frozen forecasts.

Public contract: https://nflmeta.org/openapi.yaml (2026-10-22).
No historical requests: observations become usable only after local retrieval.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import pandas as pd
import requests

from .config import RAW_DIR, DATA_DIR

ARCHIVE = RAW_DIR / 'archive' / 'nflmeta'
CREDENTIAL = DATA_DIR / 'private' / 'nflmeta_key'
BASE = 'https://nflmeta.org/api/v1'


def configure():
    if not sys.stdin.isatty():
        raise ValueError('Open an interactive PowerShell terminal for hidden credential entry')
    key = getpass.getpass('NFL Meta key (hidden; use a rotated key): ').strip()
    if not key or '\n' in key or '\r' in key:
        raise ValueError('No valid credential entered')
    CREDENTIAL.parent.mkdir(parents=True, exist_ok=True)
    CREDENTIAL.write_text(key, encoding='utf-8')
    print('Credential saved locally under ignored data/private. It is not encrypted; protect your Windows account. No API request made.')


def _key():
    value = os.environ.get('NFLMETA_KEY', '').strip()
    if not value and CREDENTIAL.exists():
        value = CREDENTIAL.read_text(encoding='utf-8').strip()
    return value


def latest(season, week, root=None, asof=None):
    root = Path(root) if root is not None else ARCHIVE
    asof = pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    for path in sorted(root.glob(f'{season}_w{week:02d}_*.json'), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
            retrieved = pd.Timestamp(payload['retrieved_at'])
            if retrieved <= asof:
                return payload
        except (ValueError, KeyError, OSError):
            continue
    return None


def refresh(season, week, *, root=None, now=None, client=None):
    """One usage check + one bounded week request; no retries/upgrades/redirects.

    Free-only guard enforces $0 without assuming a supplied key's billing plan.
    A partial page is labelled partial, never interpreted as full availability.
    """
    now = pd.Timestamp(now or pd.Timestamp.now(tz='UTC'))
    if int(season) != now.year or not 1 <= int(week) <= 22:
        return {'state': 'refused_noncurrent_season_or_week'}
    cached = latest(season, week, root, now)
    if cached and now - pd.Timestamp(cached['retrieved_at']) < pd.Timedelta(minutes=30):
        return {'state': 'cached', 'rows': len(cached['data']), 'possibly_truncated': cached['possibly_truncated']}
    key = _key()
    if not key:
        return {'state': 'not_configured'}
    client = client or requests
    headers = {'X-NFLMeta-Key': key}
    try:
        usage = client.get(BASE + '/usage', headers=headers, timeout=15, allow_redirects=False)
        if usage.status_code != 200:
            return {'state': 'usage_unavailable', 'http_status': usage.status_code}
        account = usage.json().get('data', {})
        if account.get('billing_plan') != 'free':
            return {'state': 'blocked_nonfree_plan'}
        if int(account.get('quota_remaining', 0)) < 1 or int(account.get('row_quota_remaining', 0)) < 100:
            return {'state': 'quota_insufficient'}
        response = client.get(BASE + '/injuries', params={'season': int(season), 'week': int(week), 'limit': 100, 'offset': 0},
                              headers=headers, timeout=20, allow_redirects=False)
        if response.status_code != 200:
            return {'state': 'injuries_unavailable', 'http_status': response.status_code}
        body = response.json()
        data = body.get('data')
        if not isinstance(data, list) or any(not isinstance(r, dict) or r.get('season_year') != int(season)
                                             or r.get('week') != int(week) for r in data):
            return {'state': 'invalid_schema_or_wrong_week'}
        # Whitelist fields: never archive headers, account data or unexpected echoed secrets.
        fields = ('season_year', 'week', 'team_abbr', 'display_name', 'report_status', 'game_status',
                  'source_observed_at', 'practice_only', 'no_game_designation')
        clean = [{k: r.get(k) for k in fields} for r in data]
        payload = {'source': 'NFL Meta', 'retrieved_at': now.isoformat(), 'season': int(season), 'week': int(week),
                   'possibly_truncated': len(data) >= 100, 'data': clean, 'model_input': False}
        raw = json.dumps(payload, sort_keys=True).encode()
        root = Path(root) if root is not None else ARCHIVE
        root.mkdir(parents=True, exist_ok=True)
        name = f'{season}_w{week:02d}_{now.strftime("%Y%m%dT%H%M%S%fZ")}_{hashlib.sha256(raw).hexdigest()[:12]}_{uuid.uuid4().hex[:6]}.json'
        with (root / name).open('xb') as stream:
            stream.write(raw)
        return {'state': 'archived', 'rows': len(clean), 'possibly_truncated': len(data) >= 100}
    except Exception:
        # Request exceptions may contain request headers/credentials: never print repr/traceback.
        return {'state': 'request_or_archive_failed'}


def source_rows(season, week, mapping, *, asof=None, root=None):
    """Exact team/name -> GSIS mapping only; absent/ambiguous never means healthy."""
    from .fpds_ingest import canonical_team
    from .props.lines import normalized_name
    from .fpds_injury_confirmation import normalize_status
    asof = pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    payload = latest(season, week, root, asof)
    if not payload:
        return []
    retrieved = pd.Timestamp(payload['retrieved_at'])
    if asof - retrieved > pd.Timedelta(hours=24):
        return []
    result = []
    for row in payload['data']:
        observed = pd.to_datetime(row.get('source_observed_at'), utc=True, errors='coerce')
        if pd.isna(observed) or observed > retrieved or asof - observed > pd.Timedelta(hours=24) or row.get('practice_only'):
            continue
        team = canonical_team(row.get('team_abbr'))
        pid = mapping.get((team, normalized_name(row.get('display_name') or '')))
        status = normalize_status(row.get('game_status') or row.get('report_status'))
        result.append({'team': team, 'pid': pid, 'status': status, 'available_at': retrieved,
                       'source': 'nflmeta', 'source_observed_at': observed.isoformat()})
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=['configure'])
    parser.parse_args()
    configure()
