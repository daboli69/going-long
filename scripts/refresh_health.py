"""Read-only public snapshot health audit and refresh-job summary. No provider calls."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import eligibility as E

ROOT = Path(__file__).resolve().parents[1]
FILES = ('nfl_betting.json', 'ncaa_lines.json', 'injury_context.json', 'nfl_roster.json',
         'history.json', 'results.json', 'public_tracker/manifest.json', 'savant_context.json')
NFL_TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())


def mapping(value):
    return value if isinstance(value, dict) else {}


def audit(root=ROOT, now=None, outcomes=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Health audit requires an aware decision time')
    issues, warnings, artifacts, docs = [], [], {}, {}
    for name in FILES:
        try:
            raw = (Path(root) / 'data' / name).read_bytes()
            doc = json.loads(raw)
            if not isinstance(doc, dict):
                raise ValueError('object required')
        except (OSError, ValueError):
            issues.append(f'{name}: missing or malformed JSON object')
            continue
        docs[name] = doc
        timestamp = doc.get('observed_at') if name == 'savant_context.json' else doc.get('generated_at')
        age = E._age_hours(timestamp, now)
        artifacts[name] = {'sha256': hashlib.sha256(raw).hexdigest(),
                           'generated_at': timestamp, 'age_hours': age}
        if age is None or age < -.5 or age > 36:
            issues.append(f'{name}: missing, future or older-than-36h generation timestamp')
    fresh = E.freshness(now, docs.get('injury_context.json'), docs.get('nfl_roster.json'))
    if not fresh['ok']:
        issues.append('availability: ' + fresh['reason'])
    roster = docs.get('nfl_roster.json', {})
    players = roster.get('players')
    clubs = {row.get('team') for row in players if isinstance(row, dict) and isinstance(row.get('team'), str)} if isinstance(players, list) else set()
    if clubs != NFL_TEAMS:
        issues.append('nfl_roster.json: all 32 NFL teams must be represented, including explicitly carried bye teams')
    for sport, name in (('nfl', 'nfl_betting.json'), ('ncaa', 'ncaa_lines.json')):
        doc = docs.get(name, {})
        states = doc.get('source_states')
        states = states if isinstance(states, dict) else {}
        required = ('odds', 'props', 'derivatives') if sport == 'nfl' else ('odds',)
        artifacts.setdefault(name, {}).update(feed_status=doc.get('feed_status'), source_states=states,
                                               last_attempt_at=doc.get('last_attempt_at'),
                                               last_fresh_at=doc.get('last_fresh_at'))
        if doc.get('feed_status') != 'FRESH' or doc.get('refresh_status') != 'FRESH':
            issues.append(f'{name}: provider refresh is not FRESH; saved prices retain original timestamps')
        for source in required:
            if states.get(source) != 'FRESH':
                issues.append(f'{name}: {source} is {states.get(source, "UNKNOWN")}')
        if mapping(doc.get('coverage')).get('possibly_truncated'):
            issues.append(f'{name}: incomplete provider coverage')
    history = docs.get('history.json', {}).get('betting')
    if not isinstance(history, dict) or history.get('schema_version') != 1 or not isinstance(history.get('profiles'), dict):
        issues.append('history.json: invalid public model profile contract')
    age = E._age_hours(mapping(history).get('generated_at'), now)
    artifacts.setdefault('history.json', {})['model_generated_at'] = mapping(history).get('generated_at')
    if age is None or age < -.5 or age > 36:
        issues.append('history.json: nested model generation timestamp missing, future or stale')
    results = docs.get('results.json', {})
    if results.get('schema_version') != 1 or not isinstance(results.get('games'), dict) or not isinstance(results.get('players'), dict):
        issues.append('results.json: invalid public settlement contract')
    age = E._age_hours(results.get('player_source_at'), now)
    artifacts.setdefault('results.json', {})['player_source_at'] = results.get('player_source_at')
    if age is None or age < -.5 or age > 36:
        issues.append('results.json: player source timestamp missing, future or stale')
    for sport in ('nfl', 'ncaa'):
        source = mapping(mapping(results.get('sources')).get(sport))
        if source.get('status') != 'loaded':
            issues.append(f'results.json: {sport} outcomes not freshly loaded')
        age = E._age_hours(source.get('checked_at'), now)
        if age is None or age < -.5 or age > 36:
            issues.append(f'results.json: {sport} source check missing, future or stale')
    manifest = docs.get('public_tracker/manifest.json', {})
    if manifest.get('schema_version') != 1 or manifest.get('layout') != 'public-tracker-segments-v1' or not isinstance(manifest.get('segments'), list):
        issues.append('public_tracker/manifest.json: invalid tracker manifest')
    savant = mapping(docs.get('savant_context.json'))
    sources = mapping(savant.get('sources'))
    loaded = [name for name, source in sources.items() if mapping(source).get('status') == 'loaded']
    artifacts.setdefault('savant_context.json', {})['source_states'] = {name: mapping(source).get('status') for name, source in sources.items()}
    if not loaded:
        issues.append('savant_context.json: no descriptive context source loaded')
    elif any(mapping(source).get('status') != 'loaded' for source in sources.values()):
        warnings.append('savant_context.json: partial descriptive context; loaded sources: ' + ', '.join(loaded))
    steps = {name: detail.get('outcome') if isinstance(detail, dict) else detail
             for name, detail in (outcomes or {}).items()}
    for name, outcome in steps.items():
        if outcome in ('failure', 'cancelled'):
            issues.append(f'workflow step {name}: {outcome}')
    if outcomes is not None and steps.get('validate_models') != 'success':
        issues.append('workflow model validation did not succeed')
    return {'schema_version': 1, 'checked_at': now.isoformat(), 'healthy': not issues,
            'issues': issues, 'warnings': warnings, 'artifacts': artifacts, 'workflow_outcomes': steps,
            'limitations': 'Offline artifact and job-status checks; not a live provider probe or official game-day actives certification.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--as-of', help='Explicit aware ISO timestamp for isolated audit')
    p.add_argument('--report', type=Path, help='Write diagnostics only, never replace input snapshots')
    p.add_argument('--summary', type=Path, help='Append concise GitHub job summary')
    args = p.parse_args()
    now = datetime.fromisoformat(args.as_of.replace('Z', '+00:00')) if args.as_of else None
    outcomes = json.loads(os.environ['REFRESH_OUTCOMES']) if 'REFRESH_OUTCOMES' in os.environ else None
    report = audit(args.root, now, outcomes)
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + '\n', encoding='utf-8')
    if args.summary:
        with args.summary.open('a', encoding='utf-8') as f:
            f.write('\n## Public refresh health\n\n' + ('Healthy' if report['healthy'] else 'Degraded / failed') + '\n\n')
            for issue in report['issues']:
                f.write('- ' + issue + '\n')
            for warning in report['warnings']:
                f.write('- Warning: ' + warning + '\n')
            f.write('\nSuccessful snapshots may be retained; no failed source is marked fresh.\n')
    print(text)
    return 0 if report['healthy'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
