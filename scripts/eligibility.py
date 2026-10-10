"""Python mirror of shared/going-eligibility.js for the data builders (GOING Score, Jackpot/King Endzone, Slate Breaker, first-TD). Same rules, same freshness limits.

confirmed_unavailable(): reserve/IR/PUP/NFI, suspended, retired, exempt, released, practice squad, a current-week Out/Inactive/Doubtful report, blank status.
freshness(): injury and roster snapshots must be at most 36 hours old; builders treat stale data as 'unverified' (callers decide how to fail closed).
bye_teams(): teams carried forward without a game this week.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INJURY_HOURS = ROSTER_HOURS = 36
NOT_ACTIVE = {'RES', 'INA', 'PUP', 'IR', 'NFI', 'SUS', 'RET', 'EXE', 'CUT', 'REL', 'WAIVED', 'DEV', 'PRA', 'PS', 'PSQ'}


def _load(name):
    try:
        return json.loads((REPO / 'data' / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _age_hours(stamp, now):
    try:
        t = datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (now - t).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def freshness(now=None, injury=None, roster=None):
    now = now or datetime.now(timezone.utc)
    injury = injury if injury is not None else _load('injury_context.json')
    roster = roster if roster is not None else _load('nfl_roster.json')
    reasons, ok = [], True
    for label, doc, limit in (('injury file', injury, INJURY_HOURS), ('roster snapshot', roster, ROSTER_HOURS)):
        if doc is None:
            ok = False
            reasons.append(label + ' missing')
            continue
        age = _age_hours(doc.get('generated_at'), now)
        if age is None or age > limit or age < -0.5:
            ok = False
            reasons.append(label + (' has no timestamp' if age is None else f' {age:.0f} hours old'))
    return {'ok': ok, 'reason': '; '.join(reasons), 'injury_as_of': (injury or {}).get('generated_at'), 'roster_as_of': (roster or {}).get('generated_at')}


def _severity_out(report):
    s = str((report or {}).get('report_status') or '').strip().lower()
    return s.startswith(('out', 'inactive', 'doubtful', 'injured reserve', 'suspend'))


def confirmed_unavailable(injury=None, roster=None):
    """gsis ids that must never be recommended, whatever the data age."""
    injury = injury if injury is not None else _load('injury_context.json')
    roster = roster if roster is not None else _load('nfl_roster.json')
    out = set()
    if injury:
        for v in (injury.get('current_players') or {}).values():
            gid, st = v.get('gsis_id'), str(v.get('roster_status') or '').upper()
            if gid and (st in NOT_ACTIVE or st == ''):
                out.add(gid)
        for v in (injury.get('current_reports') or {}).values():
            if v.get('gsis_id') and _severity_out(v):
                out.add(v['gsis_id'])
    for p in (roster or {}).get('players', []):
        if p.get('id') and _severity_out(p.get('injury')):
            out.add(p['id'])
    return out


def bye_teams(roster=None):
    roster = roster if roster is not None else _load('nfl_roster.json')
    return set((roster or {}).get('bye_carry_forward_teams') or [])
