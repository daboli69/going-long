"""Offline, immutable forward ATD comparisons. Never used by production models.

Consumes existing public snapshots only, no downloads, alerts or bets. Records all
RB/WR/TE exclusions alongside eligible predictions. Missing provenance blocks a
capture rather than creating an empty successful cohort. Outcomes are a separate
future operation; this recorder cannot settle or promote a model.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eligibility

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('Missing timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or eligibility._age_hours(value, parsed) is None:
        raise ValueError('Invalid timezone timestamp')
    return parsed.astimezone(timezone.utc)


def count(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 and int(value) == value


def fresh(doc, now, label):
    age = (now - stamp(doc.get('generated_at'))).total_seconds()/3600
    if not 0 <= age <= 36:
        raise ValueError(label + ': stale or future source')


def validate_config(config):
    if config != json.loads((ROOT/'config/opportunity_shadow.json').read_text()):
        raise ValueError('Frozen config differs from committed experiment')


def role(profile, season, week, now, schedule):
    rows = [r for r in profile.get('games', []) if r.get('season') == season]
    if not rows:
        raise ValueError('No current-season appearances')
    seen = set()
    for r in rows:
        w = r.get('week')
        if not count(w) or w < 1 or w >= week or not r.get('team') or not r.get('game_id'):
            raise ValueError('Missing or future appearance identity')
        if w in seen:
            raise ValueError('Duplicate appearance')
        seen.add(w)
        game = schedule.get(r['game_id'])
        if not game or game.get('season') != season or game.get('week') != w or r['team'] not in (game['home'], game['away']) or stamp(r.get('kickoff')) != stamp(game['kickoff']) or game.get('completed') is not True:
            raise ValueError('Appearance does not match completed schedule receipt')
        if r.get('completed') is not True or stamp(r.get('kickoff')) + timedelta(hours=12) > now:
            raise ValueError('Prior outcome not yet available')
        snaps = r.get('offense_snap_share')
        if not isinstance(snaps, (int, float)) or isinstance(snaps, bool) or not math.isfinite(snaps) or not 0 < snaps <= 100:
            raise ValueError('Offensive participation unverified')
        if not all(count(r.get(k)) for k in ('carries', 'targets', 'atd')):
            raise ValueError('Incomplete opportunity or TD counts')
    last_other = max((r['week'] for r in rows if r['team'] != profile['team']), default=0)
    current = sorted((r for r in rows if r['team'] == profile['team'] and r['week'] > last_other), key=lambda r:r['week'])
    if len(current) < 3:
        raise ValueError('Fewer than three current-team appearances')
    return current


def build(history, schedule, injury, roster, config, now):
    validate_config(config)
    if now.tzinfo is None:
        raise ValueError('Capture clock must have timezone')
    for label, doc in [('history', history), ('schedule', schedule)]:
        fresh(doc, now, label)
    health = eligibility.freshness(now, injury, roster)
    if not health['ok']:
        raise ValueError(health['reason'])
    betting = history['betting']
    fresh(betting, now, 'betting history')
    if betting.get('sources', {}).get('nflreadpy', {}).get(str(config['season'])) != 'loaded':
        raise ValueError('Current-season history source unavailable')
    games = [g for g in schedule['games'] if g.get('season') == config['season']]
    weeks = {}
    identities = set()
    for g in games:
        gid, week = g.get('game_id'), g.get('week')
        if not isinstance(gid, str) or not gid or gid in identities or not count(week) or not 1 <= week <= 18 or not g.get('home') or not g.get('away') or g['home'] == g['away']:
            raise ValueError('Malformed or duplicate schedule identity')
        identities.add(gid)
        stamp(g.get('kickoff'))
        weeks.setdefault(week, []).append(g)
    wanted = list(range(config['first_week'], config['last_week']+1))
    if any(w not in weeks for w in wanted):
        raise ValueError('Incomplete weekly schedule')
    week = next((w for w in wanted if min(stamp(g['kickoff']) for g in weeks[w]) > now), None)
    if week is None:
        raise ValueError('No entirely future experiment week; backfill refused')
    slate = sorted(weeks[week], key=lambda g:(g['kickoff'], g['game_id']))
    teams = {}
    for g in slate:
        for team in (g['home'], g['away']):
            if team in teams:
                raise ValueError('Duplicate weekly team')
            teams[team] = g
    profiles = betting['profiles']
    if any(not isinstance(key, str) or not key or not isinstance(p, dict) or p.get('id') != key for key,p in profiles.items()):
        raise ValueError('Profile dictionary and athlete identities disagree')
    roster_ids = [p.get('id') for p in roster['players']]
    if len(set(roster_ids)) != len(roster_ids):
        raise ValueError('Duplicate roster identity')
    if roster.get('season') != config['season'] or roster.get('week') != week:
        raise ValueError('Availability does not describe target week')
    blocked = eligibility.blocked_ids(profiles, injury, roster, now, week)
    rows, exclusions = [], []
    pool = sorted((p for p in profiles.values() if p.get('position') in {'RB', 'WR', 'TE'} and p.get('team') in teams), key=lambda p:p['id'])
    if len({p['id'] for p in pool}) != len(pool):
        raise ValueError('Duplicate athlete identity')
    for p in pool:
        try:
            if p['id'] in blocked:
                raise ValueError('Shared availability gate rejected player')
            if not any(r.get('id') == p['id'] and r.get('team') == p['team'] for r in roster['players']):
                raise ValueError('Roster team identity missing or contradictory')
            prior = role(p, config['season'], week, now, {g['game_id']:g for g in games})
            model = p.get('stats', {}).get('atd', {})
            lam = model.get('lambda')
            if model.get('family') != 'poisson' or model.get('status') != 'ready' or not isinstance(lam, (int, float)) or isinstance(lam, bool) or not math.isfinite(lam) or lam < 0:
                raise ValueError('Production ATD probability unsupported or unavailable')
            cal = model.get('calibration')
            policy = json.loads((ROOT/'config/calibration_policy.json').read_text())
            spec = policy.get('markets', {}).get('atd')
            expected = bool(policy.get('active') and spec and p['position'] in spec.get('positions', []))
            if expected and (not cal or cal.get('version') != policy['version'] or cal.get('method') != spec['method'] or cal.get('params') != spec['params']):
                raise ValueError('Production calibration receipt disagrees with frozen policy')
            if cal and (not expected or cal.get('method') != 'mean_scale' or not isinstance(model.get('lambda_raw'), (int,float)) or not math.isclose(lam,model['lambda_raw']*cal['params']['factor'],rel_tol=1e-12,abs_tol=1e-12)):
                raise ValueError('Unsupported production probability calibration')
            carries = sum(r['carries'] for r in prior)/len(prior)
            targets = sum(r['targets'] for r in prior)/len(prior)
            rates = config['coefficients']
            rows.append({'player_id':p['id'], 'name':p['name'], 'team':p['team'], 'position':p['position'], 'game_id':teams[p['team']]['game_id'], 'kickoff':teams[p['team']]['kickoff'],
                         'availability':'passed_shared_gate_at_capture', 'features':{'appearances':prior, 'carries_per_game':carries, 'targets_per_game':targets},
                         'production_model':model, 'probabilities':{'production':-math.expm1(-lam), 'opportunity':-math.expm1(-(rates['carry']*carries+rates['target']*targets)), 'frequency_beta11':(sum(r['atd']>0 for r in prior)+1)/(len(prior)+2)}})
        except ValueError as exc:
            exclusions.append({'player_id':p['id'], 'name':p.get('name'), 'team':p.get('team'), 'reason':str(exc)})
    # Preserve roster athletes with no history, too; never pretend the cohort is complete.
    known = {p['id'] for p in pool}
    for p in roster['players']:
        if p.get('position') in {'RB','WR','TE'} and p.get('team') in teams and p['id'] not in known:
            exclusions.append({'player_id':p['id'], 'name':p.get('name'), 'team':p.get('team'), 'reason':'No matching current history profile'})
            known.add(p['id'])
    if not rows:
        raise ValueError('No supported cohort; inspect per-game provenance, availability and production fits')
    return {'schema_version':1, 'status':'RESEARCH_ONLY', 'captured_at':now.isoformat(), 'season':config['season'], 'week':week, 'first_kickoff':min(stamp(g['kickoff']) for g in slate).isoformat(), 'games':[{k:g[k] for k in ('game_id','home','away','kickoff')} for g in slate], 'rows':rows, 'exclusions':exclusions, 'availability_receipt':health,
            'source_limits':{'history_sources':betting['sources'], 'latest_observed_appearance_week':max(r['week'] for p in rows for r in p['features']['appearances']), 'upstream_stat_publication_time':'Not provided by producer; build receipt is observation time, not upstream publication freshness'},
            'market_benchmark':'Not available in v1; no market advantage claim', 'missing_features':['goal-line carries','end-zone targets','dated coverage/alignment'], 'settlement':'Pending; never inferred by recorder'}


def sealed(path):
    envelope = json.loads(path.read_text())
    if digest(canonical(envelope['payload'])) != envelope['sha256']:
        raise ValueError('Corrupt immutable receipt: '+str(path))
    return envelope['payload']


def write_once(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {'sha256':digest(canonical(payload)), 'payload':payload}
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.capture-')
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(canonical(envelope)+b'\n')
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic exclusive publication: a racing process cannot replace an existing record.
        os.link(temp, path)
    finally:
        os.unlink(temp)


def capture(root, output, now):
    config = json.loads((ROOT/'config/opportunity_shadow.json').read_text())
    names = ['history.json','nfl_betting.json','injury_context.json','nfl_roster.json']
    raw = {name:(root/'data'/name).read_bytes() for name in names}
    inputs = [json.loads(raw[name]) for name in names]
    if not (output/'experiment.json').exists():
        opening = [stamp(g['kickoff']) for g in inputs[1]['games'] if g.get('season') == config['season'] and g.get('week') == config['first_week']]
        if not opening or now >= min(opening):
            raise ValueError('Initial experiment missed its first weekly kickoff; no late start or backfill')
    payload = build(*inputs, config, now)
    versions = {str(path.relative_to(ROOT)):digest(path.read_bytes().replace(b'\r\n',b'\n')) for path in [Path(__file__), ROOT/'scripts/build_pipeline.py', ROOT/'scripts/eligibility.py', ROOT/'config/champion_policy.json', ROOT/'config/calibration_policy.json', ROOT/'config/opportunity_shadow.json']}
    manifest = {'config':config, 'code_receipts':versions}
    experiment = output/'experiment.json'
    if experiment.exists():
        if sealed(experiment) != manifest:
            raise ValueError('Experiment definition changed; create a separately approved version')
    else:
        write_once(experiment, manifest)
    payload.update(input_sha256={name:digest(value) for name,value in raw.items()}, experiment_sha256=digest(canonical(manifest)))
    path = output/f"{payload['season']}-week-{payload['week']:02d}.json"
    if path.exists():
        old = sealed(path)
        if old.get('experiment_sha256') != payload['experiment_sha256']:
            raise ValueError('Existing record belongs to a different experiment')
        return path, False
    write_once(path, payload)
    return path, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT/'data/opportunity_shadow')
    args = parser.parse_args()
    try:
        path, created = capture(args.root, args.output, datetime.now(timezone.utc))
        print(('Captured: ' if created else 'Existing immutable capture retained: ')+str(path))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print('Capture blocked: '+str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
