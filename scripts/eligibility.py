"""Python mirror of shared/going-eligibility.js for the data builders (GOING Score, Jackpot/King Endzone, Slate Breaker, first-TD). Same rules, same freshness limits.

confirmed_unavailable(): unavailable/unknown statuses, contradictory teams and current-week Out/Inactive/Doubtful reports. This is not sufficient to clear a candidate.
blocked_ids(): same strict candidate exclusions as JS blockedIds(), including missing identities and stale/malformed feeds.
freshness(): structurally valid injury and roster snapshots must be at most 36 hours old.
bye_teams(): teams carried forward without a game this week.
"""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INJURY_HOURS = ROSTER_HOURS = 36
NOT_ACTIVE = {'RES', 'INA', 'PUP', 'IR', 'NFI', 'SUS', 'RET', 'EXE', 'CUT', 'REL', 'WAIVED', 'DEV', 'PRA', 'PS', 'PSQ'}
ACTIVE = {'ACT', 'ACTIVE'}
_DEFAULT = object()


def _documents(injury, roster):
    return (_load('injury_context.json') if injury is _DEFAULT else injury,
            _load('nfl_roster.json') if roster is _DEFAULT else roster)


def _valid_injury(doc):
    return isinstance(doc, dict) and all(isinstance(doc.get(key), dict) and all(
        (_valid_player(v) if key == 'current_players' else _valid_report(v)) and isinstance(v.get('gsis_id'), str) and v['gsis_id'].strip()
        for v in doc[key].values()) for key in ('current_players', 'current_reports'))


def _valid_roster(doc):
    return isinstance(doc, dict) and (doc.get('week') is None or _week(doc['week']) is not None) and isinstance(doc.get('players'), list) and all(
        _valid_player(v) and isinstance(v.get('id'), str) and v['id'].strip() and (v.get('injury') is None or _valid_report(v['injury']))
        for v in doc['players']) and (doc.get('bye_carry_forward_teams') is None or
                                    isinstance(doc['bye_carry_forward_teams'], list) and all(isinstance(v, str) for v in doc['bye_carry_forward_teams']))


def _valid_player(row):
    return isinstance(row, dict) and all(row.get(k) is None or isinstance(row[k], str) for k in ('roster_status', 'team')) and (row.get('roster_week') is None or _week(row['roster_week']) is not None)


def _valid_report(row):
    return isinstance(row, dict) and all(row.get(k) is None or isinstance(row[k], str) for k in ('report_status', 'practice_status')) and (row.get('week') is None or _week(row['week']) is not None)


def _load(name):
    try:
        return json.loads((REPO / 'data' / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _age_hours(stamp, now):
    try:
        if not isinstance(stamp, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})', stamp):
            return None
        if not stamp.endswith('Z') and (int(stamp[-5:-3]) > 23 or int(stamp[-2:]) > 59):
            return None
        t = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (now - t).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def freshness(now=None, injury=_DEFAULT, roster=_DEFAULT):
    now = now or datetime.now(timezone.utc)
    injury, roster = _documents(injury, roster)
    reasons, ok = [], True
    for label, doc, limit in (('injury file', injury, INJURY_HOURS), ('roster snapshot', roster, ROSTER_HOURS)):
        if doc is None:
            ok = False
            reasons.append(label + ' missing')
            continue
        if not (_valid_injury(doc) if label == 'injury file' else _valid_roster(doc)):
            ok = False
            reasons.append(label + ' malformed')
            continue
        age = _age_hours(doc.get('generated_at'), now)
        if age is None or age > limit or age < -0.5:
            ok = False
            reasons.append(label + (' has no timestamp' if age is None else f' {age:.0f} hours old'))
    rw = _week(roster.get('week')) if isinstance(roster, dict) else None
    if rw is not None and _valid_injury(injury) and any(v.get('roster_week') is not None and _week(v['roster_week']) != rw for v in injury['current_players'].values()):
        ok = False
        reasons.append('roster weeks disagree')
    return {'ok': ok, 'reason': '; '.join(reasons), 'injury_as_of': injury.get('generated_at') if isinstance(injury, dict) else None, 'roster_as_of': roster.get('generated_at') if isinstance(roster, dict) else None}


def _severity_out(report):
    if not isinstance(report, dict):
        return False
    s = str((report or {}).get('report_status') or '').strip().lower()
    return bool(re.search(r'^out|^inactive|injured reserve|suspend|doubtful', s))


def _week(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value) and 0 < value <= 22 and value == int(value):
        return int(value)
    if isinstance(value, str) and value.isascii() and value.isdigit() and 0 < int(value) <= 22:
        return int(value)
    return None


def _index(injury, roster, week=None):
    injury = injury if isinstance(injury, dict) else {}
    roster = roster if isinstance(roster, dict) else {}
    week = _week(roster.get('week')) or _week(week)
    players, out, reported = {}, set(), set()

    def merge(row, gid):
        if not isinstance(gid, str) or not gid.strip():
            return
        st = row.get('roster_status')
        st = st.strip().upper() if isinstance(st, str) else ''
        prior = players.get(gid)
        rank = lambda s: 2 if s in NOT_ACTIVE else 0 if s in ACTIVE else 1
        chosen = {'status': st, 'team': row.get('team') if isinstance(row.get('team'), str) else None, 'conflict': False}
        if prior:
            conflict = prior['conflict'] or bool(prior['team'] and chosen['team'] and prior['team'] != chosen['team'])
            chosen = chosen if rank(st) > rank(prior['status']) else dict(prior)
            chosen['conflict'] = conflict
        players[gid] = chosen

    def report(row, gid):
        if not isinstance(row, dict) or not isinstance(gid, str) or not gid.strip():
            return
        rw = _week(row.get('week'))
        if _week(week) is None or rw is None or rw >= _week(week):
            reported.add(gid)
            if _severity_out(row):
                out.add(gid)

    current = injury.get('current_players')
    for row in current.values() if isinstance(current, dict) else []:
        if isinstance(row, dict):
            merge(row, row.get('gsis_id'))
    reports = injury.get('current_reports')
    for row in reports.values() if isinstance(reports, dict) else []:
        if isinstance(row, dict):
            report(row, row.get('gsis_id'))
    for row in roster.get('players') if isinstance(roster.get('players'), list) else []:
        if isinstance(row, dict):
            merge(row, row.get('id'))
            report(row.get('injury'), row.get('id'))
    out.update(gid for gid, row in players.items() if row['status'] not in ACTIVE or row['conflict'])
    out.update(reported - players.keys())
    return players, out


def confirmed_unavailable(injury=_DEFAULT, roster=_DEFAULT, week=None):
    """Known IDs with unavailable/unknown status, contradictory teams or a current report.

    This set alone does not clear unknown IDs or stale feeds. Builders requiring
    actionable availability must use blocked_ids() with their complete candidate pool.
    """
    injury, roster = _documents(injury, roster)
    return _index(injury, roster, week)[1]


def blocked_ids(profiles, injury=_DEFAULT, roster=_DEFAULT, now=None, week=None):
    """Mirror of JS blockedIds(profiles): all candidates must have fresh active evidence."""
    injury, roster = _documents(injury, roster)
    players, out = _index(injury, roster, week)
    fresh = freshness(now, injury, roster)['ok']
    bye = bye_teams(roster)
    for gid, row in players.items():
        if not fresh or row['team'] in bye:
            out.add(gid)
    for gid, profile in profiles.items():
        row = players.get(gid)
        team = profile.get('team') if isinstance(profile, dict) and isinstance(profile.get('team'), str) else None
        if not fresh or row is None or (team and row['team'] and team != row['team']) or (team or (row or {}).get('team')) in bye:
            out.add(gid)
    return out


def bye_teams(roster=_DEFAULT):
    roster = _load('nfl_roster.json') if roster is _DEFAULT else roster
    values = roster.get('bye_carry_forward_teams') if isinstance(roster, dict) else None
    return {v for v in values if isinstance(v, str)} if isinstance(values, list) else set()
