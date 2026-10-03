"""Reproduce DFS empirical team TD evidence from saved NFLverse CSV + final results.

Offline only: no requests, dependencies, scraping, fitting, or live model promotion.
Explicit timestamps and hashes make an identical invocation reproducible.
"""
import argparse
import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())
ALIASES = {'LAR': 'LA', 'JAC': 'JAX', 'WSH': 'WAS'}
REQUIRED = {'season', 'season_type', 'week', 'team', 'game_id', 'opponent_team', 'rushing_tds', 'receiving_tds'}


def stamp(value, label):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f'{label}: invalid timestamp') from None
    if parsed.tzinfo is None:
        raise ValueError(f'{label}: timezone is required')
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat().replace('+00:00', 'Z')


def nfl_team(value):
    value = ALIASES.get(value, value)
    if value not in TEAMS:
        raise ValueError('Invalid NFL team identity')
    return value


def integer(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'\d+', value):
        raise ValueError(f'{label}: nonnegative integer required')
    return int(value)


def unique_object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('Duplicate JSON object key')
        output[key] = value
    return output


def build(csv_bytes, results_bytes, *, season, generated_at, retrieved_at,
          release_updated_at, source_url, expected_source_sha256):
    generated = stamp(generated_at, 'generatedAt')
    retrieved = stamp(retrieved_at, 'retrievedAt')
    released = stamp(release_updated_at, 'releaseUpdatedAt')
    if not isinstance(season, int) or isinstance(season, bool) or season < 2000:
        raise ValueError('Invalid season')
    if not released <= retrieved <= generated:
        raise ValueError('Source timestamps must precede generation and release must precede retrieval')
    official_url = f'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{season}.csv'
    if source_url != official_url:
        raise ValueError('Source URL must identify the official NFLverse team-stat release')
    digest = hashlib.sha256(csv_bytes).hexdigest()
    if not re.fullmatch(r'[a-fA-F0-9]{64}', expected_source_sha256 or '') or digest != expected_source_sha256.lower():
        raise ValueError('Saved source CSV SHA256 differs from the supplied receipt')
    results = json.loads(results_bytes.decode('utf-8-sig'), object_pairs_hook=unique_object)
    result_stamp = stamp(results.get('generated_at'), 'Results generated_at')
    if result_stamp > generated:
        raise ValueError('Results snapshot is future-dated')
    if not isinstance(results.get('games'), dict):
        raise ValueError('Results game map is missing')
    completed = {}
    for key, game in results['games'].items():
        if not isinstance(game, dict):
            raise ValueError('Malformed results game record')
        if game.get('sport') != 'nfl':
            continue  # NCAA is a separate product, explicitly outside this exporter.
        identity = game.get('id', '')
        if not identity.startswith(str(season) + '_'):
            continue  # Earlier seasons are explicitly outside this current-season file.
        match = re.fullmatch(r'(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})', identity)
        if not match or key != 'nfl|' + identity:
            raise ValueError('Results NFL game identity/key mismatch')
        year, week, away_raw, home_raw = match.groups()
        away, home = nfl_team(away_raw), nfl_team(home_raw)
        if int(year) != season or not 1 <= int(week) <= 18 or away == home:
            raise ValueError('Results game must be a regular-season NFL game')
        if nfl_team(game.get('away')) != away or nfl_team(game.get('home')) != home:
            raise ValueError('Results teams conflict with true game identity')
        kickoff = stamp(game.get('kickoff'), 'Results kickoff')
        if kickoff >= generated or kickoff >= result_stamp or kickoff >= released:
            raise ValueError('A game is future, unfinished at the results snapshot, or later than source release')
        for field in ('homeScore', 'awayScore'):
            score = game.get(field)
            if not isinstance(score, int) or isinstance(score, bool) or score < 0:
                raise ValueError('Final results require valid nonnegative integer scores')
        if identity in completed:
            raise ValueError('Duplicate results game identity')
        completed[identity] = {**game, 'away': away, 'home': home, 'week': int(week), 'kickoff': iso(kickoff)}
    if not completed:
        raise ValueError('No completed current-season regular NFL games in results')
    text = csv_bytes.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text), strict=True)
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or not REQUIRED.issubset(reader.fieldnames):
        raise ValueError('CSV requires unique official team-stat headers')
    pairs = defaultdict(dict)
    team_rows = defaultdict(list)
    for line, record in enumerate(reader, start=2):
        if None in record or any(value is None for value in record.values()):
            raise ValueError(f'CSV row {line}: incorrect column count')
        year = integer(record['season'], 'season')
        week = integer(record['week'], 'week')
        if year != season or record['season_type'] != 'REG' or not 1 <= week <= 18:
            raise ValueError(f'CSV row {line}: unexpected season/type/week; no rows are silently dropped')
        identity = record['game_id']
        if identity not in completed:
            raise ValueError(f'CSV row {line}: no matching completed true NFL game')
        game = completed[identity]
        own, opponent = nfl_team(record['team']), nfl_team(record['opponent_team'])
        if own == opponent or {own, opponent} != {game['away'], game['home']} or week != game['week']:
            raise ValueError(f'CSV row {line}: team/opponent/week conflicts with game identity')
        if own in pairs[identity]:
            raise ValueError(f'CSV row {line}: duplicate/conflicting team-game record')
        rush, receive = integer(record['rushing_tds'], 'rushing_tds'), integer(record['receiving_tds'], 'receiving_tds')
        count = rush + receive  # Includes all rushing/receiving scorers; passing/DST/returns are not added.
        final_score = game['awayScore'] if own == game['away'] else game['homeScore']
        if count * 6 > final_score:
            raise ValueError(f'CSV row {line}: rushing/receiving TD count exceeds final team score')
        row = {'team': own, 'gameId': identity, 'opponent': opponent, 'kickoff': game['kickoff'],
               'rushTDs': rush, 'recTDs': receive, 'qualifyingTDs': count}
        pairs[identity][own] = row
        team_rows[own].append(row)
    if set(pairs) != set(completed):
        raise ValueError('Source CSV omits one or more completed results games')
    for identity, game in completed.items():
        if set(pairs[identity]) != {game['away'], game['home']}:
            raise ValueError('Every completed game requires exactly two opposing team rows')
    return {
        'schemaVersion': 1, 'season': season, 'generatedAt': iso(generated),
        'retrievedAt': iso(retrieved), 'releaseUpdatedAt': iso(released), 'sourceURL': source_url,
        'sourceSha256': digest, 'resultsSHA256': hashlib.sha256(results_bytes).hexdigest(),
        'teams': {team: sorted(rows, key=lambda row: (row['kickoff'], row['gameId']))
                  for team, rows in sorted(team_rows.items())},
        'limitations': [
            'Observed completed regular-season team rushing/receiving TD counts, including all scorer positions and overtime.',
            'Passing, defensive and special-teams TDs are not added to the qualifying counts.',
            'Small current-season samples are descriptive evidence; no predictive calibration, profitability or model promotion is established.',
            'Final-game identities and score bounds are checked against the saved GOING results snapshot; source receipt hashes permit reproduction.'
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--season', type=int, required=True)
    for flag in ('generated-at', 'retrieved-at', 'release-updated-at', 'source-url', 'source-sha256'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args()
    try:
        output = build(args.csv.read_bytes(), args.results.read_bytes(), season=args.season,
                       generated_at=args.generated_at, retrieved_at=args.retrieved_at,
                       release_updated_at=args.release_updated_at, source_url=args.source_url,
                       expected_source_sha256=args.source_sha256)
    except (ValueError, OSError, UnicodeError, csv.Error) as error:
        parser.exit(1, f'Export refused: {error}\n')
    args.output.write_text(json.dumps(output, separators=(',', ':'), ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Exported {sum(len(rows) for rows in output['teams'].values())} team-game rows for {len(output['teams'])} teams.")


if __name__ == '__main__':
    main()
