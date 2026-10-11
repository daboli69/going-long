"""Read-only public snapshot health audit and refresh-job summary. No provider calls."""
import argparse
import hashlib
import gzip
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import eligibility as E

ROOT = Path(__file__).resolve().parents[1]
FILES = ('nfl_betting.json', 'ncaa_lines.json', 'injury_context.json', 'nfl_roster.json',
         'history.json', 'results.json', 'public_tracker/manifest.json', 'savant_context.json')
NFL_TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())
OUTPUT_OWNERS = {
    'validate_projection_logic': ('data/history.json', 'data/going_score.json', 'data/king-endzone.json',
        'data/slate-breaker.json', 'data/jackpot/', 'data/opportunities.json', 'data/signal_tracker.json',
        'data/signal_archive/', 'data/freezes/', 'data/td_shadow/', 'data/nb_shadow/', 'data/charts/', 'data/dfs_team_touchdowns.json',
        'data/public_tracker.json', 'data/public_tracker/', 'data/derived/'),
    'nfl': ('data/nfl_betting.json',), 'ncaa': ('data/ncaa_lines.json',),
    'pool': ('data/players.json', 'data/formats/', 'data/data.json'),
    'projections': ('data/history.json',), 'context': ('data/football_context.json', 'data/football_role_validation.json'),
    'injury_context': ('data/injury_context.json',), 'roster_public': ('data/nfl_roster.json',),
    'going_score': ('data/going_score.json',), 'results': ('data/results.json',),
    'tracker': ('data/public_tracker.json', 'data/public_tracker/'), 'charts': ('data/charts/',),
    'validation_ledger': ('data/derived/',), 'consumer_data': ('data/opportunities.json', 'data/signal_tracker.json', 'data/signal_archive/'),
    'freeze': ('data/freezes/', 'data/td_shadow/', 'data/nb_shadow/'), 'abbeys_board': ('data/abbeys-board.json',),
    'dfs_team_td': ('data/dfs_team_touchdowns.json',), 'season_learning': ('data/season_learning.json',),
    'savant': ('data/savant_context.json',), 'jackpot': ('data/king-endzone.json', 'data/jackpot/'),
    'slate_breaker': ('data/slate-breaker.json', 'data/jackpot/'), 'game_validation': ('data/football_game_validation.json',),
}


def mapping(value):
    return value if isinstance(value, dict) else {}


def _finite_json_number(token, integer=False):
    value = int(token) if integer else float(token)
    try:
        if math.isfinite(value):
            return value
    except OverflowError:
        pass
    raise ValueError('JSON number overflows a finite browser number')


def strict_json(raw):
    """Reject nonstandard constants and overflow in otherwise valid JSON numbers."""
    return json.loads(raw, parse_float=_finite_json_number,
                      parse_int=lambda token: _finite_json_number(token, integer=True),
                      parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))


def audit(root=ROOT, now=None, outcomes=None, changed=None):
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
    def source_problem(issue):
        return any(text in issue for text in (
        'provider refresh is not FRESH', ' is STALE', ' is UNKNOWN', ' is ERROR', ' is FAILED',
        ' is FALLBACK', 'outcomes not freshly loaded', 'source check missing', 'no descriptive context source loaded'))
    integrity = [issue for issue in issues if not source_problem(issue)]
    source_issues = [issue for issue in issues if source_problem(issue)]
    # Stale retained files remain health failures. Only changed invalid snapshots
    # block publication, so unrelated valid updates can recover independently.
    if changed is not None:
        changed = set(changed)
        integrity = [issue for issue in integrity if any(
            issue.startswith(name + ':') and 'data/' + name in changed for name in FILES) or
            (issue.startswith('availability:') and bool(changed & {'data/injury_context.json', 'data/nfl_roster.json'}))]
    publication_paths, excluded_paths = [], []
    def owns(path, prefixes):
        return any(path.startswith(prefix) if prefix.endswith('/') else path == prefix for prefix in prefixes)
    for path in sorted(changed or []):
        # Validate all changed JSON, including consumer/ledger/journal artifacts
        # outside the small health contract. Non-finite values are invalid JSON.
        problem = None
        try:
            raw = (Path(root) / path).read_bytes()
            if path.endswith('.json.gz'):
                raw = gzip.decompress(raw)
            doc = strict_json(raw.decode('utf-8'))
            if not isinstance(doc, (dict, list)):
                raise ValueError('object/array required')
        except (OSError, ValueError, TypeError, UnicodeError, EOFError):
            problem = f'{path}: changed output is missing or not finite JSON object/array'
        if not problem and any(steps.get(owner) in ('failure', 'cancelled', 'skipped') and owns(path, prefixes)
                for owner, prefixes in OUTPUT_OWNERS.items()):
            problem = f'{path}: changed output belongs to a failed/skipped source step'
        if not problem and any(issue.startswith(path.removeprefix('data/') + ':') or
                               (issue.startswith('availability:') and path in ('data/injury_context.json', 'data/nfl_roster.json')) for issue in integrity):
            problem = f'{path}: changed snapshot failed its integrity contract'
        if problem:
            excluded_paths.append(path)
            if problem not in integrity: integrity.append(problem)
            if problem not in issues: issues.append(problem)
        else:
            publication_paths.append(path)
    # A manifest and its content-addressed shards are one publication unit.
    # Never publish its index while one sibling failed validation/source building.
    unsafe_owners = {owner for owner, prefixes in OUTPUT_OWNERS.items() if owner != 'validate_projection_logic' and
                     any(owns(path, prefixes) for path in excluded_paths)}
    if 'tracker' in unsafe_owners:
        unsafe_owners.update(('validation_ledger', 'consumer_data', 'charts'))
    for path in publication_paths[:]:
        if any(owns(path, OUTPUT_OWNERS[owner]) for owner in unsafe_owners):
            publication_paths.remove(path)
            excluded_paths.append(path)
            problem = f'{path}: companion output from the same publication group is invalid'
            integrity.append(problem); issues.append(problem)
    tests, sources, publication = [], source_issues, []
    for name, outcome in steps.items():
        if outcome in ('failure', 'cancelled'):
            issue = f'workflow step {name}: {outcome}'
            issues.append(issue)
            (tests if name in ('validate_models', 'validate_projection_logic') else publication if name in ('publish', 'data_integrity') else sources).append(issue)
    if outcomes is not None and steps.get('validate_models') != 'success':
        issues.append('workflow model validation did not succeed')
    return {'schema_version': 1, 'checked_at': now.isoformat(), 'healthy': not issues,
            'publication_ready': not integrity, 'data_integrity_issues': integrity,
            'publication_paths': publication_paths, 'excluded_publication_paths': excluded_paths,
            'test_failures': tests, 'source_failures': sources, 'publication_failures': publication,
            'issues': issues, 'warnings': warnings, 'artifacts': artifacts, 'workflow_outcomes': steps,
            'limitations': 'Offline artifact and job-status checks; not a live provider probe or official game-day actives certification.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--as-of', help='Explicit aware ISO timestamp for isolated audit')
    p.add_argument('--report', type=Path, help='Write diagnostics only, never replace input snapshots')
    p.add_argument('--summary', type=Path, help='Append concise GitHub job summary')
    p.add_argument('--publication-check', action='store_true', help='Fail closed for changed invalid snapshots, independent of tests/source outages')
    args = p.parse_args()
    now = datetime.fromisoformat(args.as_of.replace('Z', '+00:00')) if args.as_of else None
    outcomes = json.loads(os.environ['REFRESH_OUTCOMES']) if 'REFRESH_OUTCOMES' in os.environ else None
    changed = None
    if args.publication_check:
        changed = subprocess.check_output(['git', 'diff', '--name-only', '--', 'data'], cwd=args.root, text=True).splitlines()
        changed += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '--', 'data'], cwd=args.root, text=True).splitlines()
    report = audit(args.root, now, outcomes, changed)
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
    if args.publication_check:
        return 0 if report['publication_ready'] or report['publication_paths'] else 1
    return 0 if report['healthy'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
