#!/usr/bin/env python
"""Fantasy Points Data Suite ingestion. Tuesday: drop the CSV exports in FantasyPoints/Inbox, then run

    python scripts/fantasy_points.py import

Other commands: inventory (read-only look at the Inbox), status, verify, seed-registry, rosters.
The FantasyPoints folder holds licensed data and is gitignored; this repo only contains the code, the table registry and docs.
"""
import argparse
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_ingest import fields as fieldmod  # noqa: E402
from fp_ingest import identity as idmod  # noqa: E402
from fp_ingest import registry as regmod  # noqa: E402
from fp_ingest.pipeline import Importer, inspect_bytes, iso, season_of  # noqa: E402
from fp_ingest.store import Manifest, find_inbox, find_root, freshness, public_status, write_json  # noqa: E402
from fp_ingest.parse import sha256  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ROSTER_MAX_AGE_HOURS = 12


def repo_week(season):
    path = REPO / 'data' / 'nfl_roster.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    return int(data['week']) if int(data.get('season') or 0) == int(season) and data.get('week') else None


def roster_provider(root, current_season, allow_network=True):
    cache = Path(root) / 'identity'
    notes = []

    def provide(season):
        path = cache / f'roster_{season}.csv'
        stale = not path.exists() or (season == current_season and time.time() - path.stat().st_mtime > ROSTER_MAX_AGE_HOURS * 3600)
        if stale and allow_network:
            try:
                idmod.download_roster(season, path)
            except Exception as error:  # offline or nflverse hiccup: use what we have
                notes.append(f'roster {season}: download failed ({error}); using cached/repo roster')
        rows = idmod.read_roster_csv(path) if path.exists() else []
        if not rows:
            rows = idmod.read_repo_roster(REPO / 'data' / 'nfl_roster.json', season)
        aliases = {}
        alias_path = REPO / 'config' / 'fantasy_points_aliases.json'
        if alias_path.exists():
            aliases = json.loads(alias_path.read_text(encoding='utf-8')).get('aliases', {})
        return idmod.RosterIndex(rows, aliases) if rows else None

    provide.notes = notes
    return provide


def make_importer(args):
    root = find_root(args.root, REPO)
    now = datetime.datetime.now(datetime.timezone.utc)
    season = args.current_season or season_of(now)
    week = repo_week(season)
    return Importer(root, regmod.load(), now=now, rosters=roster_provider(root, season, not args.offline), current_season=season,
                    max_possible_games=week, expected_games=args.expected_through if args.expected_through is not None else (week - 1 if week else None),
                    through_override=args.through_week, declare=getattr(args, 'declare', None), only=getattr(args, 'only', None))


def cmd_import(args):
    importer = make_importer(args)
    report = importer.run()
    print(f"Fantasy Points import - season {report['current_season']} - {report['files_scanned']} files in Inbox")
    print('Outcomes:', ', '.join(f'{k}={v}' for k, v in sorted(report['outcomes'].items())) or 'none')
    for result in report['results']:
        extra = ''
        if result.get('through_games') is not None:
            extra = f" thru G{result['through_games']}"
        if result.get('reason'):
            extra += f" [{result['reason']['code']}: {result['reason']['message']}]"
        print(f"  {result['outcome']:<22} {result['file']} -> {result.get('table_id') or '-'}{extra}")
    print('\nFreshness:')
    for line in report['freshness']:
        print('  ' + line)
    if report['problems']:
        print(f"\nPROBLEMS ({len(report['problems'])}): those files were preserved but NOT imported; the previous valid data is unchanged.")
    for item in report['warnings']:
        print(f"WARNING {item['file']}: {'; '.join(item['warnings'])}")
    if report['identity_unresolved']:
        print(f"\nUnmatched players: {len(report['identity_unresolved'])} (see manifests/last_run.json)")
        for row in report['identity_unresolved'][:15]:
            print(f"  {row.get('table')}: {row.get('name')} {row.get('team', '')} {row.get('position', '')} -> {row['status']}")
    if report['identity_review']:
        print(f"Matches to eyeball: {len(report['identity_review'])} (matched by a rule weaker than name+team+position)")
    notes = getattr(importer.rosters, 'notes', [])
    for note in notes:
        print('NOTE', note)
    if args.publish_status:
        fresh = json.loads((importer.root / 'manifests' / 'freshness.json').read_text(encoding='utf-8'))
        write_json(args.publish_status, public_status(fresh))
        print('metadata-only status written to', args.publish_status)
    return 1 if (args.strict and report['problems']) else 0


def cmd_inventory(args):
    root = find_root(args.root, REPO)
    registry = regmod.load()
    inbox = find_inbox(root)
    rows = []
    for path in sorted(inbox.glob('*.csv')):
        info, _ = inspect_bytes(path.name, path.read_bytes(), registry, iso(datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc)))
        rows.append(info)
    if args.json:
        print(json.dumps(rows, indent=1, default=list))
        return 0
    for info in rows:
        if 'error' in info:
            print(f"{info['original_filename']}: ERROR {info['error']['code']}: {info['error']['message']}")
            continue
        print(f"{info['original_filename']}: table={info['table_id']} ({info['schema_status']}) level={info['level']} rows={info['row_count']} cols={info['column_count']} "
              f"season={','.join(info.get('seasons', []))} games={info.get('games_min')}-{info.get('games_max')} teams={info['team_count']} classes={info['columns_by_class']}")
    return 0


def cmd_status(args):
    root = find_root(args.root, REPO)
    now = datetime.datetime.now(datetime.timezone.utc)
    season = args.current_season or season_of(now)
    week = repo_week(season)
    expected = args.expected_through if args.expected_through is not None else (week - 1 if week else None)
    fresh = freshness(regmod.load(), Manifest(root), season, expected, iso(now))
    print(f"Fantasy Points - season {season}, expecting data through week {expected}")
    for table in fresh['tables']:
        print('  ' + table['line'])
    return 0


def cmd_verify(args):
    root = find_root(args.root, REPO)
    manifest = Manifest(root)
    bad = []
    for sha, entry in manifest.files.items():
        raw = root / entry['raw_path']
        if not raw.exists():
            bad.append((entry['original_filename'], 'raw file missing'))
        elif sha256(raw.read_bytes()) != sha:
            bad.append((entry['original_filename'], 'raw file checksum mismatch'))
        if entry.get('normalized_path') and not (root / entry['normalized_path']).exists():
            bad.append((entry['original_filename'], 'normalized file missing (re-run import)'))
    print(f'{len(manifest.files)} manifest entries checked, {len(bad)} problems')
    for name, why in bad:
        print(f'  {name}: {why}')
    return 1 if bad else 0


def cmd_seed(args):
    root = find_root(args.root, REPO)
    inbox = find_inbox(root)
    files = {}
    for path in sorted(inbox.glob('*.csv')):
        stem = regmod.filename_stem(path.name)
        for table_id, meta in __import__('fp_ingest.table_meta', fromlist=['TABLES']).TABLES.items():
            if stem in meta['hints']:
                files[table_id] = path
    seeded = regmod.seed(files)
    write_json(regmod.REGISTRY_PATH, seeded)
    print(f'wrote {regmod.REGISTRY_PATH} with {len(seeded["tables"])} tables')
    return 0


def cmd_rosters(args):
    root = find_root(args.root, REPO)
    for season in args.seasons:
        path = idmod.download_roster(season, root / 'identity' / f'roster_{season}.csv')
        print('saved', path)
    return 0


def cmd_fields(args):
    registry = regmod.load()
    for table in registry['tables'].values():
        counts = {}
        for column in table['columns']:
            klass = fieldmod.classify_column(column['key'])['class']
            counts[klass] = counts.get(klass, 0) + 1
        print(f"{table['id']}: {counts}")
    return 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')  # Windows consoles default to cp1252; status lines use check marks
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', help='FantasyPoints folder (default: GOING_FP_ROOT, ./FantasyPoints, or ../GOING/FantasyPoints)')
    parser.add_argument('--current-season', type=int)
    parser.add_argument('--expected-through', type=int, help='games every team should have played (default: roster week - 1)')
    sub = parser.add_subparsers(dest='command')
    p = sub.add_parser('import', help='scan Inbox, archive, normalize, update freshness (default)')
    p.add_argument('--strict', action='store_true', help='exit 1 if any file was held or rejected (default exit 0 so GOING refresh continues)')
    p.add_argument('--offline', action='store_true', help='do not download nflverse rosters')
    p.add_argument('--through-week', type=int, help='operator override of games played for every file in this run')
    p.add_argument('--declare', help="historical batch only: 'cumulative' (Fantasy Points weeks 1-N) or 'week:N' (a single week), applied to every file in this run")
    p.add_argument('--only', action='append', help="only process Inbox files matching this name pattern (repeatable); required with --declare, e.g. --only '2023_*'")
    p.add_argument('--publish-status', help='write a metadata-only freshness JSON (no licensed values) to this path')
    p.set_defaults(func=cmd_import)
    p = sub.add_parser('inventory', help='read-only look at every file in the Inbox')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_inventory)
    sub.add_parser('status', help='freshness per table').set_defaults(func=cmd_status)
    sub.add_parser('verify', help='re-checksum every archived file').set_defaults(func=cmd_verify)
    sub.add_parser('seed-registry', help='rebuild config/fantasy_points_tables.json from the files in the Inbox').set_defaults(func=cmd_seed)
    sub.add_parser('fields', help='column use classes per table').set_defaults(func=cmd_fields)
    p = sub.add_parser('rosters', help='download nflverse rosters used for identity')
    p.add_argument('seasons', nargs='+', type=int)
    p.set_defaults(func=cmd_rosters)
    args = parser.parse_args(argv)
    if not args.command:
        args = parser.parse_args((argv or sys.argv[1:]) + ['import'])
    try:
        return args.func(args)
    except (ValueError, RuntimeError, FileNotFoundError) as error:  # usage problems get a message, not a traceback
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
