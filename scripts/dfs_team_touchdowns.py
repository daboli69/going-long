"""Refresh data/dfs_team_touchdowns.json (Touchdown Throne team evidence) from the public NFLverse team-stat release.

Why this exists: research/dfs/build-team-budgets.py is an offline reproducer that needs a saved CSV, a SHA receipt and explicit timestamps. Nothing ever called it on a
schedule, so the committed snapshot froze at its 2026-10-03 build and the 36-hour freshness gate in shared/dfs-team-evidence.js then refused every Throne build. This script
is the scheduled caller. It only reads two public sources (the release asset and its release metadata) and the repository's own data/results.json.

Safety rules kept from the reproducer: the snapshot is built only from completed games that appear in BOTH the downloaded CSV and data/results.json, every game must have two
team rows, TD counts are bounded by final scores, and the output is written atomically only if the build succeeds. On ANY failure the existing file is left untouched and the
exit code is non-zero (the workflow should treat that as a warning, not delete the old snapshot). Rows for games the results snapshot does not yet list (or that finished after the
release was last updated) are dropped before the build and counted in `droppedRows`; `downloadedSourceSha256` is the hash of the unmodified download.

Usage (CI):  python scripts/dfs_team_touchdowns.py [--results data/results.json] [--output data/dfs_team_touchdowns.json] [--season 2026]
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
RELEASE_API = 'https://api.github.com/repos/nflverse/nflverse-data/releases/tags/stats_team'
ASSET_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{season}.csv'


def _builder():
    spec = importlib.util.spec_from_file_location('dfs_team_budget_export', ROOT / 'research' / 'dfs' / 'build-team-budgets.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iso(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def select_games(csv_bytes, results, release_updated_at):
    """Return (filtered_csv_bytes, filtered_results_bytes, dropped_rows, kept_games).

    Keeps games that are final in results.json, kicked off before the release asset was last updated, and present in the CSV; drops CSV rows for anything else.
    """
    stamp = lambda text: datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    released = stamp(release_updated_at)
    final = {}
    for key, game in (results.get('games') or {}).items():
        if not isinstance(game, dict) or game.get('sport') != 'nfl':
            continue
        if not (isinstance(game.get('homeScore'), int) and isinstance(game.get('awayScore'), int)):
            continue
        try:
            if stamp(game['kickoff']) >= released:
                continue
        except (KeyError, ValueError):
            continue
        final[game.get('id')] = (key, game)
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig')), strict=True)
    kept_rows, dropped, in_csv = [], 0, set()
    for row in reader:
        if row.get('game_id') in final:
            kept_rows.append(row)
            in_csv.add(row['game_id'])
        else:
            dropped += 1
    # a final game with no CSV rows cannot be built (the reproducer demands every completed game): drop it from results instead of failing the whole refresh
    games = {key: game for gid, (key, game) in final.items() if gid in in_csv}
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames, lineterminator='\n')
    writer.writeheader()
    writer.writerows(kept_rows)
    filtered_results = dict(results)
    filtered_results['games'] = games
    return out.getvalue().encode('utf-8'), json.dumps(filtered_results).encode('utf-8'), dropped, len(games)


def refresh(csv_bytes, results, *, season, now, retrieved_at, release_updated_at, source_url=None):
    builder = _builder()
    csv_filtered, results_filtered, dropped, kept = select_games(csv_bytes, results, release_updated_at)
    if not kept:
        raise ValueError('No final games overlap between the downloaded team CSV and results.json')
    output = builder.build(csv_filtered, results_filtered, season=season, generated_at=_iso(now), retrieved_at=_iso(retrieved_at),
                           release_updated_at=release_updated_at, source_url=source_url or ASSET_URL.format(season=season),
                           expected_source_sha256=hashlib.sha256(csv_filtered).hexdigest())
    output['downloadedSourceSha256'] = hashlib.sha256(csv_bytes).hexdigest()
    output['droppedRows'] = dropped
    return output


def _get(url, accept=None):
    request = urllib.request.Request(url, headers={'User-Agent': 'going-long-data-refresh', **({'Accept': accept} if accept else {})})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def release_updated_at(season):
    name = f'stats_team_week_{season}.csv'
    meta = json.loads(_get(RELEASE_API, 'application/vnd.github+json'))
    for asset in meta.get('assets', []):
        if asset.get('name') == name and asset.get('updated_at'):
            return asset['updated_at']
    raise ValueError(f'Release metadata has no updated_at for {name}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', type=pathlib.Path, default=ROOT / 'data' / 'results.json')
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'data' / 'dfs_team_touchdowns.json')
    parser.add_argument('--season', type=int, default=int(os.environ.get('SEASON', '2026')))
    args = parser.parse_args(argv)
    try:
        released = release_updated_at(args.season)
        retrieved = datetime.now(timezone.utc)
        csv_bytes = _get(ASSET_URL.format(season=args.season))
        results = json.loads(args.results.read_text(encoding='utf-8-sig'))
        output = refresh(csv_bytes, results, season=args.season, now=datetime.now(timezone.utc), retrieved_at=retrieved, release_updated_at=released)
    except Exception as error:  # fail closed: keep the previous snapshot
        print(f'Team TD refresh skipped; existing snapshot kept: {error}', file=sys.stderr)
        return 1
    text = json.dumps(output, separators=(',', ':'), ensure_ascii=False) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=args.output.parent, delete=False, suffix='.tmp') as handle:
        handle.write(text)
        temp = handle.name
    os.replace(temp, args.output)
    print(f"Refreshed {sum(len(rows) for rows in output['teams'].values())} team-game rows for {len(output['teams'])} teams (dropped {output['droppedRows']}).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
