#!/usr/bin/env python3
"""Offline NFL salary/availability/lineup audit; never fetches or enters contests.

Example (all inputs are explicit; keep salary files outside Git):
  python scripts/validate_dk_slate.py --csv <DKSalaries.csv> --format classic
    --date 2026-10-11 --roster data/nfl_roster.json
    --injury data/injury_context.json --schedule data/nfl_betting.json
    [--lineup <JSON array of official IDs, captain first for Showdown>]

CSV content cannot prove provider authenticity or association with a contest.
This audits rules and current availability, not projections, ownership or ROI.
"""
import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

import eligibility

ET = ZoneInfo('America/New_York')
HEADERS = ['Position', 'Name + ID', 'Name', 'ID', 'Roster Position', 'Salary',
           'Game Info', 'TeamAbbrev', 'AvgPointsPerGame']
CLASSIC = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST']
TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())
RULES = ['https://www.draftkings.com/help/rules/1/1',
         'https://help.draftkings.com/hc/en-us/articles/24808583978003-Game-Style-Showdowns-Overview-US']


def team(value):
    return {'JAC': 'JAX', 'LAR': 'LA', 'WSH': 'WAS'}.get(value, value)


def name_key(value):
    # Preserve suffixes: Jr./II are part of identity, never a fuzzy match.
    value = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'[^a-z0-9]', '', value.encode('ascii', 'ignore').decode().lower())


def stamp(value):
    if eligibility._age_hours(value, datetime.now(timezone.utc)) is None:
        raise ValueError('Kickoff/as-of timestamps require a valid ISO timestamp with explicit timezone')
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Kickoff/as-of timestamps require an explicit timezone')
    return parsed.astimezone(timezone.utc)


def validate(text, *, contest_format, slate_date, roster, injury, schedule, now, lineup=None):
    """Return structured evidence; invalid rows never become eligible candidates."""
    if contest_format not in ('classic', 'showdown'):
        raise ValueError('Only NFL classic and showdown are supported')
    date.fromisoformat(slate_date)
    if now.tzinfo is None:
        raise ValueError('now requires an explicit timezone')
    errors, players = [], []
    fresh = eligibility.freshness(now, injury, roster)
    report = {'schema': 'going-dk-slate-validation-v1', 'format': contest_format,
              'validation_scope': 'salary pool and availability; lineup legality only when supplied',
              'slate_date': slate_date, 'checked_at': now.isoformat(), 'availability': fresh,
              'salary_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
              'source_authenticity': 'unverified: obtain the official CSV from the selected contest',
              'contest_association': 'unverified: compare the exact game set with the selected contest',
              'rule_sources': RULES, 'errors': errors, 'players': players,
              'source_dates': {'schedule': schedule.get('generated_at') if isinstance(schedule, dict) else None,
                               'roster_week': roster.get('week') if isinstance(roster, dict) else None},
              'lineup': {'checked': False}, 'limitations': [
                  'No projection, ownership, duplication, optimizer or performance validation.',
                  'CSV has no authoritative retrieval timestamp; download again before lock.',
                  'Free injury feeds do not guarantee complete game-day inactive coverage.',
                  'This does not validate late swap for already entered contests.']}
    games = set()
    schedule_rows = schedule.get('games') if isinstance(schedule, dict) else None
    if not isinstance(schedule_rows, list):
        errors.append('Schedule requires a games array with home, away and timezone-aware kickoff')
    else:
        for game in schedule_rows:
            if not isinstance(game, dict):
                continue
            try:
                kickoff = stamp(game.get('kickoff'))
                home, away = team(game.get('home')), team(game.get('away'))
                if kickoff.astimezone(ET).date().isoformat() == slate_date and home in TEAMS and away in TEAMS and home != away:
                    games.add((away, home, kickoff))
            except (ValueError, TypeError):
                continue
    if not games:
        errors.append('No valid scheduled games for the supplied Eastern slate date')

    identities = {}
    for row in roster.get('players', []) if isinstance(roster, dict) and isinstance(roster.get('players'), list) else []:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not isinstance(row.get('team'), str) or not isinstance(row.get('position'), str):
            continue
        key = (name_key(row.get('name')), team(row.get('team')), row.get('position'))
        identities.setdefault(key, set()).add(row['id'])
    try:
        rows = list(csv.reader(io.StringIO(text.lstrip('\ufeff')), strict=True))
    except csv.Error as exc:
        rows = []
        errors.append('Malformed CSV: ' + str(exc))
    if not rows or len(rows[0]) != len(set(rows[0])) or not set(HEADERS).issubset(rows[0]):
        errors.append('Missing/duplicate official salary headers')
        rows = []
    ids, athletes, csv_games, team_games = set(), {}, set(), {}
    candidates = {}
    blocked = set()
    for number, cells in enumerate(rows[1:], 2):
        if not any(cells):
            continue
        if len(cells) != len(rows[0]):
            errors.append(f'Row {number}: incorrect column count')
            continue
        row = dict(zip(rows[0], (v.strip() for v in cells)))
        dk_id, name, pos, club, role = row['ID'], row['Name'], row['Position'], team(row['TeamAbbrev']), row['Roster Position']
        try:
            if not dk_id.isascii() or not dk_id.isdigit() or not name or row['Name + ID'] != f'{name} ({dk_id})' or dk_id in ids:
                raise ValueError('invalid/duplicate official ID or Name + ID')
            ids.add(dk_id)
            salary = int(row['Salary'])
            if not row['Salary'].isascii() or not row['Salary'].isdigit() or not 0 < salary <= 50000:
                raise ValueError('salary must be a positive integer at most 50000')
            if row['AvgPointsPerGame'] and not re.fullmatch(r'-?\d+(?:\.\d+)?', row['AvgPointsPerGame']):
                raise ValueError('invalid AvgPointsPerGame')
            if contest_format == 'classic':
                if pos not in CLASSIC or pos == 'FLEX' or role != (pos if pos in ('QB', 'DST') else pos + '/FLEX'):
                    raise ValueError('unsupported Classic position/roster role')
            elif pos not in ('QB', 'RB', 'WR', 'TE', 'K', 'DST') or role not in ('CPT', 'FLEX'):
                raise ValueError('unsupported Showdown position/roster role')
            match = re.fullmatch(r'([A-Z]{2,3})@([A-Z]{2,3}) (\d{2}/\d{2}/\d{4}) (\d{2}:\d{2})(AM|PM) ET', row['Game Info'])
            if not match:
                raise ValueError('invalid official Game Info')
            away, home = team(match[1]), team(match[2])
            kickoff = datetime.strptime(match[3] + ' ' + match[4] + match[5], '%m/%d/%Y %I:%M%p').replace(tzinfo=ET).astimezone(timezone.utc)
            game = (away, home, kickoff)
            if club not in (away, home) or game not in games:
                raise ValueError('game/team/kickoff differs from supplied date or schedule')
            for scheduled_team in (away, home):
                if scheduled_team in team_games and team_games[scheduled_team] != game:
                    raise ValueError('team appears in conflicting games')
                team_games[scheduled_team] = game
            csv_games.add(game)
            identity_key = (name_key(name), club, pos)
            matches = identities.get(identity_key, set())
            gid = next(iter(matches)) if len(matches) == 1 else None
            # Authoritative athlete identity survives display-name and position differences.
            athlete = ('dst', club) if pos == 'DST' else ('gsis', gid) if gid else ('unmatched', *identity_key)
            roles = athletes.setdefault(athlete, {})
            if role in roles or contest_format == 'classic' and roles:
                raise ValueError('duplicate athlete and roster role')
            roles[role] = salary
            reason = None
            if pos == 'DST':
                # Team defense is not a rostered player; verify the scheduled team.
                reason = None if fresh['ok'] and club not in eligibility.bye_teams(roster) else 'team availability unverified'
            elif gid is None:
                reason = 'player identity unmatched or ambiguous'
            else:
                candidates[gid] = {'team': club}
            if kickoff <= now:
                reason = 'game already started'
            csv_status = row.get('Status', '').strip().upper()
            if csv_status in eligibility.NOT_ACTIVE | {'O', 'OUT', 'D', 'DOUBTFUL', 'INACTIVE', 'RESERVE', 'SUSP', 'SUSPENDED', 'RETIRED', 'RELEASED', 'PRACTICE SQUAD'}:
                reason = 'CSV reports unavailable'
            elif csv_status not in {'', 'Q', 'QUESTIONABLE', 'GTD', 'P', 'PROBABLE', 'ACT', 'ACTIVE', 'AVAILABLE', 'HEALTHY', 'NONE', 'NOT LISTED', 'DNP', 'LP', 'FP'}:
                reason = 'CSV status unrecognized; availability unverified'
            players.append({'id': dk_id, 'name': name, 'position': pos, 'team': club, 'role': role,
                            'salary': salary, 'gsis_id': gid, 'athlete': '|'.join(athlete),
                            'away': away, 'home': home, 'kickoff': kickoff.isoformat(),
                            'eligible': reason is None, 'exclusion': reason})
        except ValueError as exc:
            errors.append(f'Row {number}: {exc}')
    blocked = eligibility.blocked_ids(candidates, injury, roster, now, week=roster.get('week') if isinstance(roster, dict) else None)
    for player in players:
        if player['gsis_id'] in blocked:
            player.update(eligible=False, exclusion=player['exclusion'] or 'shared eligibility blocks availability')
        if not fresh['ok']:
            player.update(eligible=False, exclusion=player['exclusion'] or 'availability feeds unverified')
    if contest_format == 'classic' and len(csv_games) < 2:
        errors.append('Classic pool must span at least two games')
    if contest_format == 'showdown':
        if len(csv_games) != 1:
            errors.append('Showdown pool must contain exactly one game')
        for key, roles in athletes.items():
            if set(roles) != {'CPT', 'FLEX'} or roles['CPT'] * 2 != roles['FLEX'] * 3:
                errors.append('Showdown athlete requires one CPT/FLEX pair at exact 1.5x salary: ' + '|'.join(key))
    report['games'] = [{'away': a, 'home': h, 'kickoff': k.isoformat()} for a, h, k in sorted(csv_games)]
    report['counts'] = {'salary_rows': len(players), 'eligible_rows': sum(p['eligible'] for p in players),
                        'excluded_rows': sum(not p['eligible'] for p in players)}
    if lineup is not None:
        lineup_errors, selected = [], []
        slots = CLASSIC if contest_format == 'classic' else ['CPT'] + ['FLEX'] * 5
        by_id = {p['id']: p for p in players}
        if not isinstance(lineup, list) or len(lineup) != len(slots) or any(not isinstance(v, str) for v in lineup):
            lineup_errors.append('Lineup must be an ordered JSON array of official ID strings with exact slot count')
        else:
            for slot, dk_id in zip(slots, lineup):
                p = by_id.get(dk_id)
                if p is None or not p['eligible']:
                    lineup_errors.append('Missing or unavailable lineup ID: ' + dk_id)
                    continue
                fits = p['role'] == slot if contest_format == 'showdown' else p['position'] == slot or slot == 'FLEX' and p['position'] in ('RB', 'WR', 'TE')
                if not fits:
                    lineup_errors.append('Wrong roster slot for ID: ' + dk_id)
                selected.append(p)
            if len({p['athlete'] for p in selected}) != len(selected):
                lineup_errors.append('Same athlete selected more than once')
            if sum(p['salary'] for p in selected) > 50000:
                lineup_errors.append('Lineup exceeds 50000 salary cap')
            if contest_format == 'classic' and len({(p['away'], p['home'], p['kickoff']) for p in selected}) < 2:
                lineup_errors.append('Classic lineup must use at least two games')
            if contest_format == 'showdown' and len({p['team'] for p in selected}) != 2:
                lineup_errors.append('Showdown lineup must include both teams')
        report['lineup'] = {'checked': True, 'legal': not errors and not lineup_errors,
                            'errors': lineup_errors, 'salary': sum(p['salary'] for p in selected),
                            'scoring_multipliers': [1.5] + [1] * 5 if contest_format == 'showdown' else [1] * 9}
    report['ok'] = not errors and fresh['ok'] and any(p['eligible'] for p in players) and (lineup is None or report['lineup']['legal'])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('csv', 'roster', 'injury', 'schedule', 'date'):
        parser.add_argument('--' + flag, required=True)
    parser.add_argument('--format', required=True, choices=('classic', 'showdown'))
    parser.add_argument('--now', help='Explicit timezone-aware decision time; defaults to current UTC')
    parser.add_argument('--lineup', help='JSON array of official ID strings in slot order')
    args = parser.parse_args(argv)
    paths = {key: Path(getattr(args, key)) for key in ('csv', 'roster', 'injury', 'schedule')}
    try:
        blobs = {key: path.read_bytes() for key, path in paths.items()}
        docs = {key: json.loads(blobs[key]) for key in ('roster', 'injury', 'schedule')}
        output = validate(blobs['csv'].decode('utf-8-sig'), contest_format=args.format, slate_date=args.date,
                          now=stamp(args.now) if args.now else datetime.now(timezone.utc),
                          lineup=json.loads(Path(args.lineup).read_text(encoding='utf-8')) if args.lineup else None, **docs)
        output['provenance'] = {key: {'file': path.name, 'sha256': hashlib.sha256(blobs[key]).hexdigest()} for key, path in paths.items()}
    except (OSError, ValueError, UnicodeError) as exc:
        output = {'schema': 'going-dk-slate-validation-v1', 'ok': False, 'errors': [str(exc)]}
    print(json.dumps(output, indent=2, allow_nan=False))
    return 0 if output['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
