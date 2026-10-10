#!/usr/bin/env python3
"""Pregame freeze manifest for a slate day (write-once). Records exactly which code, model policy, data snapshots and shadow predictions were in place BEFORE kickoff, so the
slate can later be scored against what GOING said and nothing can be edited after the fact.

    python scripts/sunday_freeze.py 2026-10-11

It does not snapshot licensed or private material (ownership models, user salary files, lineups: those are frozen on the user's device with "Freeze this lineup").
The tracker (data/public_tracker) separately freezes every GOING pick, price and rating; role_shadow / td_shadow freeze the Challenger predictions.
"""
import datetime
import hashlib
import json
import os
import subprocess
import tempfile
from zoneinfo import ZoneInfo
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import eligibility  # noqa: E402
from refresh_health import NFL_TEAMS  # noqa: E402
FILES = ['history.json', 'nfl_betting.json', 'football_context.json', 'injury_context.json', 'nfl_roster.json', 'season_learning.json', 'dfs_correlations.json', 'king-endzone.json', 'slate-breaker.json']


def write_once(path, doc):
    """Publish complete bytes atomically without replacing an existing freeze."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as tmp:
        pending = Path(tmp.name)
        try:
            tmp.write(json.dumps(doc, indent=1, allow_nan=False) + '\n')
            tmp.flush()
            os.fsync(tmp.fileno())
        except BaseException:
            tmp.close()
            pending.unlink(missing_ok=True)
            raise
    try:
        os.link(pending, path)  # Exclusive creation; same-filesystem atomic visibility.
        return True
    except FileExistsError:
        return False
    finally:
        pending.unlink(missing_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generated(path):
    d = json.loads(path.read_text(encoding='utf-8'))
    return d.get('generated_at') or d.get('generatedAt') or (d.get('betting') or {}).get('generated_at')


def scheduled_day(now):
    """Earliest existing Sunday job is 04:20 Eastern; Saturday pushes never freeze."""
    if now.tzinfo is None:
        raise ValueError('Freeze requires an aware clock')
    local = now.astimezone(ZoneInfo('America/New_York'))
    return local.date().isoformat() if local.weekday() == 6 and local.time() >= datetime.time(4, 20) else None


def freeze_inputs_ok(root, now):
    """A write-once freeze must wait for valid current inputs, never lock degraded data."""
    try:
        docs = {name: json.loads((root / 'data' / name).read_text(encoding='utf-8'),
                                parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
                for name in ('history.json', 'nfl_betting.json', 'football_context.json', 'injury_context.json', 'nfl_roster.json')}
        for name, doc in docs.items():
            if not isinstance(doc, dict):
                return False
            stamp = (doc.get('betting') or {}).get('generated_at') if name == 'history.json' else doc.get('generated_at')
            age = eligibility._age_hours(stamp, now)
            if age is None or not -.5 <= age <= 36:
                return False
        if not eligibility.freshness(now, docs['injury_context.json'], docs['nfl_roster.json'])['ok']:
            return False
        if {p.get('team') for p in docs['nfl_roster.json']['players']} != NFL_TEAMS:
            return False
        odds = docs['nfl_betting.json']
        return odds.get('feed_status') == 'FRESH' and odds.get('refresh_status') == 'FRESH' and all(
            (odds.get('source_states') or {}).get(source) == 'FRESH' for source in ('odds', 'props', 'derivatives'))
    except (OSError, TypeError, ValueError):
        return False


def main(day=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    due = scheduled_day(now)
    if due is None or (day is not None and day != due):
        print('not due: Sunday freeze starts at 04:20 America/New_York')
        return
    day = due
    out = REPO / 'data' / 'freezes' / f'{day}.json'
    if out.exists():
        print('already frozen (write-once):', out)
        return
    games = json.loads((REPO / 'data/nfl_betting.json').read_text(encoding='utf-8')).get('games_raw', [])
    # A football day is the Eastern calendar day: the Sunday-night game (00:20Z Monday) belongs to Sunday's slate, not to a later UTC date.
    eastern = ZoneInfo('America/New_York')
    def et_day(stamp):
        return datetime.datetime.fromisoformat(str(stamp).replace('Z', '+00:00')).astimezone(eastern).date().isoformat()
    kickoffs = sorted((g['commence_time'] for g in games if g.get('commence_time') and et_day(g['commence_time']) == day),
                      key=lambda stamp: datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00')))
    if not kickoffs:
        print('no NFL games on', day, '- nothing to freeze')
        return
    if now >= datetime.datetime.fromisoformat(kickoffs[0].replace('Z', '+00:00')):
        print(f'first kickoff {kickoffs[0]} has passed: not a pregame freeze, nothing written')
        return
    if not freeze_inputs_ok(REPO, now):
        print('inputs invalid, stale or source availability unverified: nothing frozen')
        return
    history = json.loads((REPO / 'data/history.json').read_text(encoding='utf-8'))['betting']
    policies, scoring, calibration_versions = {}, 0, {}
    for p in history['profiles'].values():
        for market, model in (p.get('stats') or {}).items():
            policies[f"{market}:{model.get('policy', 'v1')}"] = policies.get(f"{market}:{model.get('policy', 'v1')}", 0) + 1
            cal = model.get('calibration')
            if cal:
                key = f"{market}:{cal.get('method')}:{cal.get('version')}"
                calibration_versions[key] = calibration_versions.get(key, 0) + 1
        scoring += 1 if p.get('scoring_role') else 0
    champion = json.loads((REPO / 'config/champion_policy.json').read_text(encoding='utf-8'))
    shadows = {}
    for folder in ('role_shadow', 'td_shadow', 'nb_shadow'):
        for path in sorted((REPO / 'data' / folder).glob('*-week-??.json')):
            doc = json.loads(path.read_text(encoding='utf-8'))
            rows = len(doc.get('rows', [])) or sum(len(g.get('candidates', [])) for g in doc.get('games', []) if isinstance(g, dict))
            shadows[f'{folder}/{path.name}'] = {'sha256': sha(path), 'recorded_at': doc.get('recorded_at'), 'rows': rows}
    doc = {'schema': 'going-pregame-freeze-v1', 'slate_date': day, 'frozen_at': now.isoformat(timespec='seconds'), 'first_kickoff': kickoffs[0] if kickoffs else None,
           'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO).decode().strip(),
           'champion_policy': {'active': champion.get('active'), 'sha256': sha(REPO / 'config/champion_policy.json')},
           'today_ranking_experiment': json.loads((REPO / 'research/today-ranking/experiment-v3.json').read_text(encoding='utf-8')).get('id'),
           'calibration_policy': {'version': json.loads((REPO / 'config/calibration_policy.json').read_text(encoding='utf-8')).get('version'), 'sha256': sha(REPO / 'config/calibration_policy.json')},
           'calibration_versions_in_models': calibration_versions,
           'availability': eligibility.freshness(now,
               json.loads((REPO / 'data/injury_context.json').read_text(encoding='utf-8')),
               json.loads((REPO / 'data/nfl_roster.json').read_text(encoding='utf-8'))),
           'dfs_team_touchdowns': ({'sha256': sha(REPO / 'data/dfs_team_touchdowns.json'), 'generated_at': generated(REPO / 'data/dfs_team_touchdowns.json')} if (REPO / 'data/dfs_team_touchdowns.json').exists() else None),
           'profile_policy_counts': policies, 'profiles_with_scoring_role': scoring, 'scoring_role_ok': scoring >= 0.5 * max(1, len(history['profiles'])),
           'data': {f: {'sha256': sha(REPO / 'data' / f), 'generated_at': generated(REPO / 'data' / f)} for f in FILES if (REPO / 'data' / f).exists()},
           'shadow_files': shadows,
           'note': 'Do not edit. Picks, prices and ratings are frozen by the tracker; ownership models, salary files and lineups stay private on the user device.'}
    print('frozen' if write_once(out, doc) else 'already frozen (write-once):', out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
