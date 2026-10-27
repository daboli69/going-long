"""Raw archive receipts, exact-ID box reconciliation and strict pregame field."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from hashlib import sha256
import math

from .common import EASTERN, TEAMS, digest, seal, team, utc

PLAYER_FIELDS = {'pts': 'points', 'reb': 'rebounds', 'ast': 'assists',
                 'fgm': 'field_goals_made', 'fga': 'field_goals_attempted',
                 'tpm': 'three_point_field_goals_made', 'tpa': 'three_point_field_goals_attempted',
                 'ftm': 'free_throws_made', 'fta': 'free_throws_attempted',
                 'oreb': 'offensive_rebounds', 'dreb': 'defensive_rebounds'}


def fetch_archives(seasons, cache, kinds=('schedule', 'player', 'team')):
    import requests
    templates = {'schedule': ('espn_nba_schedules', 'nba_schedule'),
                 'player': ('espn_nba_player_boxscores', 'player_box'),
                 'team': ('espn_nba_team_boxscores', 'team_box'),
                 'pbp': ('espn_nba_pbp', 'play_by_play')}
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    sources = []
    for season in sorted(set(seasons)):
        for kind in kinds:
            tag, stem = templates[kind]
            url = f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{tag}/{stem}_{season}.parquet'
            result = requests.get(url, timeout=45)
            result.raise_for_status()
            hashed = sha256(result.content).hexdigest()
            path = cache / f'{stem}_{season}_{hashed}.parquet'
            if path.exists() and sha256(path.read_bytes()).hexdigest() != hashed:
                raise ValueError('Corrupt raw cache')
            if not path.exists():
                with path.open('xb') as out:
                    out.write(result.content)
            sources.append(dict(kind=kind, season=season, path=str(path), url=url,
                                sha256=hashed, retrieved_at=datetime.now(timezone.utc).isoformat(),
                                upstream_publication_at=None, underlying_feed='ESPN'))
    return seal({'sources': sources, 'created_at': datetime.now(timezone.utc).isoformat()})


def _stats(row, mapping):
    result = {}
    for key, field in mapping.items():
        value = row.get(field)
        if type(value) is not int or value < 0:
            raise ValueError(f'Missing/noninteger {field}')
        result[key] = value
    if not (result['tpm'] <= result['tpa'] <= result['fga'] and result['tpm'] <= result['fgm'] <= result['fga']
            and result['ftm'] <= result['fta'] and result['fgm'] - result['tpm'] <= result['fga'] - result['tpa']):
        raise ValueError('Invalid shot accounting')
    if result['pts'] != 2 * result['fgm'] + result['tpm'] + result['ftm'] or result['reb'] != result['oreb'] + result['dreb']:
        raise ValueError('PRA/shot or rebound accounting conflict')
    if result['ast']>result['fgm'] and mapping.get('pts')=='team_score':
        raise ValueError('More team assists than field goals')
    return result


def normalize(schedules, players, teams, known_at, debut_seasons=None):
    """Never use archive active flags as a historical pregame availability feed."""
    utc(known_at)
    debut_seasons = debut_seasons or {}
    accepted, exclusions, pending = {}, Counter(), []
    for r in schedules:
        gid = f'espn:{r["game_id"]}'
        note = str(r.get('notes_headline') or '').lower()
        if r.get('season_type') != 2 or team(r.get('home_abbreviation')) not in TEAMS or team(r.get('away_abbreviation')) not in TEAMS:
            exclusions['outside_regular_NBA_field'] += 1
            continue
        if 'championship' in note and ('cup' in note or 'in-season tournament' in note):
            exclusions['cup_final'] += 1
            continue
        if r.get('time_valid') is not True:
            exclusions['unverified_tipoff'] += 1
            continue
        g = dict(game_id=gid, season=int(r['season']), tipoff=utc(r['date']).isoformat(),
                 home=team(r['home_abbreviation']), away=team(r['away_abbreviation']),
                 known_at=known_at, regular_season=True)
        if r.get('status_type_name') == 'STATUS_SCHEDULED':
            pending.append(g)
            continue
        if r.get('status_type_name') != 'STATUS_FINAL' or r.get('status_type_completed') is not True:
            exclusions['not_final_or_scheduled'] += 1
            continue
        g.update(scores={g['home']: r['home_score'], g['away']: r['away_score']})
        if gid in accepted and accepted[gid] != g:
            raise ValueError(f'Conflicting schedule {gid}')
        accepted[gid] = g
    by_player, by_team = defaultdict(dict), defaultdict(dict)
    player_issues=defaultdict(list)
    for r in players:
        gid, pid = f'espn:{r["game_id"]}', f'espn:{r["athlete_id"]}'
        if gid not in accepted:
            continue
        code = team(r.get('team_abbreviation'))
        if r.get('did_not_play') is True:
            exclusions['explicit_DNP_rows'] += 1
            dnp = dict(player_id=pid, name=r['athlete_display_name'], team=code,
                                      minutes=0., position=str(r.get('athlete_position_abbreviation') or 'UNKNOWN'),
                                      **{key: 0 for key in PLAYER_FIELDS})
            if pid in by_player[gid] and by_player[gid][pid]!=dnp:
                raise ValueError(f'Conflicting played/DNP record {pid}/{gid}')
            by_player[gid][pid]=dnp
            continue
        minutes = r.get('minutes')
        if not isinstance(minutes, (int, float)) or not math.isfinite(minutes) or minutes < 0:
            exclusions['unknown_player_minutes'] += 1
            player_issues[gid].append('unknown_minutes:'+pid)
            continue
        try:
            stats = _stats(r, PLAYER_FIELDS)
        except ValueError:
            exclusions['invalid_player_stats'] += 1
            player_issues[gid].append('invalid_stats:'+pid)
            continue
        player = dict(player_id=pid, name=r['athlete_display_name'], team=code, minutes=float(minutes),
                      position=str(r.get('athlete_position_abbreviation') or 'UNKNOWN'), **stats)
        if pid in by_player[gid] and by_player[gid][pid] != player:
            raise ValueError(f'Conflicting player/game {pid}/{gid}')
        by_player[gid][pid] = player
    for r in teams:
        gid, code = f'espn:{r["game_id"]}', team(r.get('team_abbreviation'))
        if gid not in accepted:
            continue
        mapping = dict(PLAYER_FIELDS, pts='team_score', reb='total_rebounds')
        try:
            values = _stats(r, mapping)
            turnovers = r.get('total_turnovers')
            if type(turnovers) is not int or turnovers < 0:
                raise ValueError('Missing turnovers')
            values['tov'] = turnovers
        except ValueError:
            exclusions['invalid_team_stats'] += 1
            continue
        if code in by_team[gid] and by_team[gid][code] != values:
            raise ValueError(f'Conflicting team/game {gid}/{code}')
        by_team[gid][code] = values
    games, failures = [], []
    for gid, g in accepted.items():
        rosters, boxes = list(by_player[gid].values()), by_team[gid]
        reasons = list(player_issues[gid])
        if utc(g['tipoff'])>=utc(known_at):
            reasons.append('provider_final_is_in_future_of_retrieval')
        if set(boxes) != {g['home'], g['away']} or any(p['team'] not in boxes for p in rosters):
            reasons.append('missing_or_wrong_team_boxes')
        else:
            lengths = []
            for code, box in boxes.items():
                selected = [p for p in rosters if p['team'] == code]
                for key in PLAYER_FIELDS:
                    if sum(p[key] for p in selected) != box[key]:
                        reasons.append(f'{code}_player_team_{key}_mismatch')
                if box['pts'] != g['scores'][code]:
                    reasons.append(f'{code}_schedule_score_mismatch')
                total_minutes = sum(p['minutes'] for p in selected)
                length = 48 + 5 * max(0, round((total_minutes / 5 - 48) / 5))
                if abs(total_minutes - length * 5) > 5:
                    reasons.append(f'{code}_rounded_minutes_incomplete')
                lengths.append(length)
            if len(set(lengths)) != 1:
                reasons.append('team_game_length_mismatch')
        if reasons:
            failures.append(dict(game_id=gid, reasons=reasons))
            continue
        games.append(dict(g, players=rosters, teams=boxes, game_minutes=lengths[0],
                          event_reconciliation='unavailable', lineup_reconciliation='unavailable'))
    if not games:
        raise ValueError('No fully reconciled regular-season box games')
    return seal(dict(schema_version=1, games=sorted(games, key=lambda g: g['tipoff']),
                     scheduled=pending, debut_seasons=debut_seasons,
                     sources_known_at=known_at, exclusions=dict(exclusions), reconciliation_failures=failures,
                     historical_availability='retrieved_archive_not_historical_pregame_receipts'))


def eligible_history(snapshot, origin, season, mode='prospective'):
    if mode not in ('prospective', 'retrospective'):
        raise ValueError('Unknown history mode')
    selected = []
    for g in snapshot['games']:
        if not season - 3 <= g['season'] <= season:
            continue
        if utc(g['tipoff']) + timedelta(hours=36) >= origin:
            continue
        if mode == 'prospective' and utc(g['known_at']) > origin:
            continue
        selected.append(g)
    return selected


def validate_slate(slate, origin=None):
    origin = origin or utc(slate['origin'])
    if origin != utc(slate['origin']):
        raise ValueError('Origin mismatch')
    day = datetime.fromisoformat(slate['date']).date()
    if day.weekday() != 1 or slate.get('regular_season') is not True:
        raise ValueError('Only Tuesday NBA regular-season slates')
    if not slate.get('field_complete') or not slate.get('rosters_complete'):
        raise ValueError('Complete field and pregame rosters required; no candidate-only leader probabilities')
    if slate.get('evidence_kind') not in ('prospective', 'retrospective_fixture', 'synthetic'):
        raise ValueError('Explicit evidence kind required')
    if utc(slate['known_at']) > origin or not slate.get('source'):
        raise ValueError('Pregame source receipt required')
    if slate['evidence_kind']=='prospective' and origin-utc(slate['known_at'])>timedelta(hours=36):
        raise ValueError('Pregame slate evidence is stale')
    games = {g['game_id']: g for g in slate['games']}
    if len(games) != len(slate['games']) or set(games) != set(slate['eligible_game_ids']):
        raise ValueError('Exact complete eligible game IDs required')
    if not games or origin >= min(utc(g['tipoff']) for g in games.values()):
        raise ValueError('Freeze the full slate before its earliest tipoff')
    player_ids, team_ids = set(), set()
    for gid, g in games.items():
        if utc(g['tipoff']).astimezone(EASTERN).date() != day or g.get('status') != 'scheduled':
            raise ValueError('Wrong Eastern date, postponed or started game')
        if g['home'] not in TEAMS or g['away'] not in TEAMS or g['home'] == g['away']:
            raise ValueError('Invalid NBA teams')
        if team_ids & {g['home'], g['away']}:
            raise ValueError('A team cannot appear twice on the slate')
        team_ids.update((g['home'], g['away']))
        for code in (g['home'], g['away']):
            roster = [p for p in slate['players'] if p['game_id'] == gid and p['team'] == code]
            if len([p for p in roster if p['availability'] == 'available']) < 5:
                raise ValueError('Fewer than five available players; use an explicit rotation scenario')
    for p in slate['players']:
        if p['player_id'] in player_ids or p['game_id'] not in games:
            raise ValueError('Duplicate player or wrong game')
        player_ids.add(p['player_id'])
        g = games[p['game_id']]
        if p['team'] not in (g['home'], g['away']) or p['availability'] not in ('available', 'out'):
            raise ValueError('Unknown availability; provide separate conditional scenarios')
        debut = p.get('debut_season')
        if type(debut) is not int or debut > slate['season']:
            raise ValueError('Verified NBA debut season required; missing history is not rookie status')
        if utc(p['known_at']) > origin or not p.get('source'):
            raise ValueError('Timestamped pregame player evidence required')
        if slate['evidence_kind']=='prospective' and origin-utc(p['known_at'])>timedelta(hours=36):
            raise ValueError('Player availability evidence is stale')
        if 'expected_minutes' in p:
            m = p['expected_minutes']
            if not 0 <= m['mean'] <= 48 or not 0 <= m['sd'] <= 48 or not m.get('source') or utc(m['known_at']) > origin:
                raise ValueError('Invalid/untimestamped minutes scenario')
    if set(slate['eligible_player_ids']) != player_ids:
        raise ValueError('Complete player field mismatch')
    if slate['evidence_kind']=='prospective':
        receipt=slate.get('field_source_receipt')
        if not receipt or not receipt.get('source') or utc(receipt['known_at'])>origin:
            raise ValueError('Independent full-field source receipt required')
        raw=Path(receipt['path']).read_bytes()
        if sha256(raw).hexdigest()!=receipt['sha256']:
            raise ValueError('Full-field source bytes changed')
        field=json.loads(raw)
        if (field['date']!=slate['date'] or set(field['eligible_game_ids'])!=set(games)
                or set(field['eligible_player_ids'])!=player_ids):
            raise ValueError('Field manifest differs from preserved full-field source')
    return origin
