"""Current-season DraftKings kicker evidence from public NFLverse weekly stats.

Only published final games matching the local results receipt are included.
Missing/malformed counts fail closed; no salary CSV average or prior-year fallback.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.request
from datetime import datetime, timezone, timedelta
if __package__:
    from .github_release_metadata import release_metadata
else:
    from github_release_metadata import release_metadata

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'
API = 'https://api.github.com/repos/nflverse/nflverse-data/releases/tags/stats_player'
FIELDS = ['fg_made_0_19', 'fg_made_20_29', 'fg_made_30_39', 'fg_made_40_49', 'fg_made_50_59', 'fg_made_60_', 'fg_made', 'fg_att', 'pat_made', 'pat_att']
TEAMS = set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())

def stamp(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)', value) or re.search(r'[+-]14:(?!00)', value):
        raise ValueError('Malformed source timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp must include offset')
    return parsed.astimezone(timezone.utc)

def iso(value):
    return stamp(value).isoformat().replace('+00:00', 'Z')

def count(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+', value):
        raise ValueError('Missing or malformed kicker count')
    result = int(value)
    if result > 100:
        raise ValueError('Impossible kicker count')
    return result

def score(counts):
    if sum(counts[k] for k in FIELDS[:6]) != counts['fg_made'] or counts['fg_made'] > counts['fg_att'] or counts['pat_made'] > counts['pat_att']:
        raise ValueError('Kicker count totals conflict')
    return 3 * sum(counts[k] for k in FIELDS[:3]) + 4 * counts['fg_made_40_49'] + 5 * (counts['fg_made_50_59'] + counts['fg_made_60_']) + counts['pat_made']

def build(csv_bytes, results_bytes, *, season, generated_at, retrieved_at, release_updated_at):
    generated, retrieved, released = map(stamp, [generated_at, retrieved_at, release_updated_at])
    if not released <= retrieved <= generated or generated - retrieved > timedelta(hours=36) or generated - released > timedelta(days=8):
        raise ValueError('Stale or contradictory kicker source timestamps')
    def bad_constant(value):
        raise ValueError('Nonfinite JSON values are not evidence')
    results = json.loads(results_bytes, parse_constant=bad_constant)
    results_generated = stamp(results.get('generated_at'))
    result_source = (results.get('sources') or {}).get('nfl') or {}
    results_checked = stamp(result_source.get('checked_at'))
    if result_source.get('status') != 'loaded' or not results_checked <= results_generated <= generated or generated - results_checked > timedelta(hours=36) or generated - results_generated > timedelta(hours=36):
        raise ValueError('Results source is stale or unavailable')
    games = {}
    for g in (results.get('games') or {}).values():
        if g.get('sport') != 'nfl' or not str(g.get('id', '')).startswith(str(season) + '_'):
            continue
        if g['id'] in games:
            raise ValueError('Duplicate result game identity')
        if all(type(g.get(k)) is int and g[k] >= 0 for k in ['homeScore', 'awayScore']) and stamp(g['kickoff']) < released:
            games[g['id']] = g
    players, seen, dropped = {}, set(), 0
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig')), strict=True)
    if not set(FIELDS + ['position', 'season', 'week', 'game_id', 'team', 'player_id', 'player_display_name']).issubset(reader.fieldnames or []):
        raise ValueError('Kicker source columns missing')
    for row in reader:
        if row['position'] != 'K' or row['season'] != str(season):
            continue
        gid, pid, team = row['game_id'], row['player_id'], row['team']
        if gid not in games:
            dropped += 1
            continue
        game = games[gid]
        match = re.fullmatch(r'(\d{4})_(\d{2})_([A-Z]{2,3})_([A-Z]{2,3})', gid)
        if not match or not 1 <= int(match[2]) <= 18 or str(int(match[2])) != row['week'] or not re.fullmatch(r'00-\d{7}', pid) or team not in TEAMS or team not in [game['home'], game['away']] or set(match.groups()[2:]) != {game['home'], game['away']}:
            raise ValueError('Kicker game/player/team identity conflicts')
        if (pid, gid) in seen:
            raise ValueError('Duplicate kicker player-game')
        seen.add((pid, gid))
        counts = {k: count(row[k]) for k in FIELDS}
        points = score(counts)
        team_score = game['homeScore' if team == game['home'] else 'awayScore']
        if 3 * counts['fg_made'] + counts['pat_made'] > team_score:
            raise ValueError('Kicking points exceed final team score')
        item = players.setdefault(pid, {'playerId': pid, 'name': row['player_display_name'], 'games': []})
        item['games'].append({'gameId': gid, 'team': team, 'opponent': game['away' if team == game['home'] else 'home'], 'kickoff': iso(game['kickoff']), 'teamFinalScore': team_score, 'counts': counts, 'points': points})
    if not players:
        raise ValueError('No verified current-season kicker games')
    for item in players.values():
        item['games'].sort(key=lambda g: g['kickoff'])
        if len({g['gameId'].split('_')[1] for g in item['games']}) != len(item['games']):
            raise ValueError('Duplicate kicker season-week')
    return {'schemaVersion': 1, 'season': season, 'status': 'current-season-kickers', 'generatedAt': iso(generated_at), 'retrievedAt': iso(retrieved_at), 'releaseUpdatedAt': iso(release_updated_at), 'resultsGeneratedAt': iso(results['generated_at']), 'resultsCheckedAt': iso(result_source['checked_at']), 'sourceURL': URL.format(season=season), 'sourceSha256': hashlib.sha256(csv_bytes).hexdigest(), 'resultsSHA256': hashlib.sha256(results_bytes).hexdigest(), 'players': players, 'droppedRows': dropped}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'going-long-kicker-refresh'}), timeout=60) as response:
        return response.read()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, default=int(os.environ.get('SEASON', '2026')))
    parser.add_argument('--results', type=Path, default=ROOT / 'data/results.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/dfs_kickers.json')
    args = parser.parse_args()
    try:
        name = f'stats_player_week_{args.season}.csv'
        assets = release_metadata('stats_player')['assets']
        matching = [a for a in assets if a.get('name') == name]
        if len(matching) != 1:
            raise ValueError('No unique official weekly player asset')
        released = matching[0]['updated_at']
        csv_bytes = get(URL.format(season=args.season))
        retrieved = datetime.now(timezone.utc).isoformat()
        output = build(csv_bytes, args.results.read_bytes(), season=args.season, generated_at=datetime.now(timezone.utc).isoformat(), retrieved_at=retrieved, release_updated_at=released)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=args.output.parent, delete=False) as handle:
            json.dump(output, handle, separators=(',', ':'))
            temporary = handle.name
        os.replace(temporary, args.output)
        print(f"Verified {len(output['players'])} kickers; {sum(len(p['games']) for p in output['players'].values())} current-season games")
        return 0
    except Exception as error:
        print(f'Kicker refresh failed; previous snapshot preserved: {error}', file=__import__('sys').stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
