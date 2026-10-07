"""On-disk layout, manifest, freshness and point-in-time access for imported Fantasy Points data.

FantasyPoints/
  Inbox/                          you drop exports here (never modified, never deleted by this code)
  raw/<season>/<scope>/<table>__<sha12>.csv   immutable copies, content-addressed; scope = through-week-NN | full-season
  raw/_unrecognized | _rejected | _quarantine/ preserved bytes of files that could not be imported
  normalized/<season>/<table>/<scope>__<sha12>.json
  identity/roster_<season>.csv    public nflverse roster cache used for player identity
  manifests/index.json            one entry per distinct file (sha256); written last so a crash never leaves a half-import
  manifests/freshness.json, last_run.json
"""
import datetime
import json
import os
import re
from pathlib import Path

GOOD = ('imported', 'imported_review', 'partial')
EXPECTED_BASE_WEEK = 14  # byes run through week 14, so max-games == week only up to here


def find_root(explicit=None, repo_root=None):
    """Locate the FantasyPoints folder: --root, GOING_FP_ROOT, <repo>/FantasyPoints, then a sibling GOING/FantasyPoints."""
    candidates = [explicit, os.environ.get('GOING_FP_ROOT')]
    if repo_root:
        repo_root = Path(repo_root)
        candidates += [repo_root / 'FantasyPoints', repo_root.parent / 'GOING' / 'FantasyPoints']
    for candidate in candidates:
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise FileNotFoundError('FantasyPoints folder not found; pass --root or set GOING_FP_ROOT')


def find_inbox(root):
    for child in Path(root).iterdir():
        if child.is_dir() and child.name.lower() == 'inbox':
            return child
    raise FileNotFoundError(f'no Inbox folder inside {root}')


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    if isinstance(data, str):
        data = data.encode('utf-8')
    with open(temporary, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def write_json(path, value):
    atomic_write(path, json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + '\n')


def clean_temporaries(root):
    """Remove leftover *.tmp files from an interrupted run. A locked file is reported, never fatal. Returns (removed, failed)."""
    removed, failed = 0, []
    for path in Path(root).rglob('*.tmp'):
        if 'Inbox' in path.parts or 'inbox' in path.parts:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError as error:
            failed.append(f'{path.name}: {error}')
    return removed, failed


class RunLock:
    """One import at a time. A lock older than two hours is treated as left behind by a crash."""

    def __init__(self, root, max_age_seconds=7200):
        self.path = Path(root) / 'manifests' / '.import.lock'
        self.max_age = max_age_seconds

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            age = datetime.datetime.now().timestamp() - self.path.stat().st_mtime
            if age < self.max_age:
                raise RuntimeError(f'another import is running (lock {self.path}); delete it only if you are sure none is')
            self.path.unlink()
        self.path.write_text(str(os.getpid()), encoding='utf-8')
        return self

    def __exit__(self, *exc):
        try:
            self.path.unlink()
        except OSError:
            pass
        return False


class Manifest:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'manifests' / 'index.json'
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding='utf-8'))
            except json.JSONDecodeError as error:
                raise RuntimeError(f'{self.path} is corrupt ({error}); restore it before importing (raw files are the source of truth)')
            if not isinstance(self.data, dict) or not isinstance(self.data.get('files'), dict):
                raise RuntimeError(f'{self.path} has an unexpected shape; restore it before importing')
        else:
            self.data = {'version': 1, 'source': 'Fantasy Points Data Suite', 'files': {}}

    @property
    def files(self):
        return self.data['files']

    def save(self):
        write_json(self.path, self.data)

    def entries(self, season=None, table_id=None, statuses=GOOD):
        return [e for e in self.files.values()
                if (season is None or e.get('season') == season) and (table_id is None or e.get('table_id') == table_id)
                and (statuses is None or e.get('status') in statuses)]


def scope_dir(scope, through_games, week=None):
    if scope == 'season_to_date':
        return f'through-week-{int(through_games):02d}'
    if scope == 'historical_cumulative':
        return f'cumulative-through-game-{int(through_games):02d}'
    if scope == 'single_week':
        return f'week-{int(week):02d}'
    return {'full_season': 'full-season'}.get(scope, 'unclassified')


def snapshot_key(entry):
    """Same key = same observation (a re-export/correction of it): scope plus games for cumulative scopes, the week for single weeks."""
    return (entry.get('scope'), entry.get('week') if entry.get('scope') == 'single_week' else entry.get('through_games'))


def weekly_entries(manifest, season, table_id):
    """Declared single-week exports for one table, oldest week first, corrections applied. These are NOT cumulative and are never
    summed or served by point_in_time; they are stored so research can use true weekly observations."""
    found = [e for e in manifest.entries(season, table_id) if e.get('scope') == 'single_week' and not e.get('superseded_by')]
    return sorted(found, key=lambda e: e['week'])


def _order(entry):
    return (entry.get('through_games') or 0, entry.get('status') != 'partial', entry.get('first_imported_at') or '', entry.get('sha256'))


def current_entry(manifest, season, table_id):
    """The snapshot GOING should treat as current: most games, then the latest correction. Superseded revisions never win."""
    live = [e for e in manifest.entries(season, table_id) if e.get('scope') == 'season_to_date' and not e.get('superseded_by')]
    if live:
        return max(live, key=_order)
    full = [e for e in manifest.entries(season, table_id) if e.get('scope') == 'full_season' and not e.get('superseded_by')]
    return max(full, key=_order) if full else None


def point_in_time(manifest, season, table_id, for_season, for_week, known_by=None):
    """Return the manifest entry GOING could legitimately have used to predict ``for_season`` week ``for_week``, or None.

    * same season: ``known_by`` (ISO timestamp of the prediction) is REQUIRED. Only a live season-to-date capture that GOING
      had imported by then, with every game before the target week, qualifies. After every team's bye (14+ games) one more
      week is held back because the games and the week number no longer line up. A later correction is invisible before it was
      imported, a partial re-export never replaces a complete snapshot, and a retrospective export is never eligible.
    * forward-looking matchup tables are valid only for the week they were exported for (games + 1).
    * an earlier season: its full-season snapshot, complete before this season began. It was downloaded later, so it may
      carry Fantasy Points corrections made after that season; that is the one accepted look-back imprecision.
    None means missing, never zero.
    """
    pool = manifest.entries(season, table_id)
    if season == for_season:
        if not known_by:
            raise ValueError('known_by is required for same-season lookups: without it later corrections leak into the past')
        latest = {}
        for entry in pool:
            # a declared historical cumulative export is point-in-time by its CONTENT (games through N), not by when it was
            # downloaded; live captures are point-in-time by when GOING imported them
            if entry.get('scope') != 'historical_cumulative' and (entry.get('first_imported_at') or '9999') > known_by:
                continue
            if entry.get('scope') == 'single_week':
                continue
            key = snapshot_key(entry)
            rank = (entry.get('status') != 'partial', entry.get('captured_at') or '', entry.get('first_imported_at') or '')
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank, entry)

        def usable(entry):
            games = entry.get('through_games') or 0
            live_ok = entry.get('scope') == 'season_to_date' and entry.get('known_live')
            historical_ok = entry.get('scope') == 'historical_cumulative' and entry.get('declared_by') == 'operator'
            return (live_ok or historical_ok) and games <= for_week - (2 if games >= EXPECTED_BASE_WEEK else 1)
        live = [entry for _, entry in latest.values() if usable(entry)]
        if any(e.get('forward_looking') for e in live):
            live = [e for e in live if e.get('through_games') == for_week - 1]
        return max(live, key=_order) if live else None
    if season < for_season:
        prior = [e for e in pool if not e.get('superseded_by') and not e.get('forward_looking')
                 and (e.get('scope') == 'full_season' or (e.get('scope') == 'season_to_date' and (e.get('through_games') or 0) >= 17))]
        return max(prior, key=_order) if prior else None
    return None


def short_name(table_id):
    return {
        'receiving_routes_run': 'Routes', 'receiving_advanced': 'Receiving', 'receiving_man_vs_zone': 'Man vs Zone',
        'receiving_separation_by_alignment': 'Separation: alignment', 'receiving_separation_by_breaks': 'Separation: breaks',
        'receiving_separation_by_coverage': 'Separation: coverage', 'receiving_separation_by_routes': 'Separation: routes',
        'rushing_advanced': 'Rushing', 'rushing_bell_cow': 'Bell cow', 'passing_advanced': 'Passing', 'passing_depth': 'Passing depth',
        'qb_coverage_matchup': 'QB coverage matchup', 'wr_coverage_matchup': 'WR coverage matchup', 'line_matchups': 'OL/DL matchups',
        'run_pass_report': 'Run/pass', 'offense_snaps': 'Snaps', 'efficiency': 'Efficiency', 'coverage_matrix': 'Defensive coverage matrix',
        'passing_basic': 'Passing basic', 'receiving_basic': 'Receiving basic', 'rushing_basic': 'Rushing basic',
    }.get(table_id, table_id)


def freshness(registry, manifest, season, expected_games, now_iso):
    """Compact per-table status. Missing or stale is its own state, never evidence about a player."""
    tables = []
    for table_id, table in sorted(registry['tables'].items()):
        entry = current_entry(manifest, season, table_id)
        if entry is None and not table.get('weekly_expected', True):
            continue  # an optional table nobody has imported for this season is not "missing"
        item = {'table': table_id, 'label': short_name(table_id)}
        if entry is None:
            quarantined = [e for e in manifest.files.values() if e.get('table_id') == table_id and e.get('season') == season
                           and e.get('status') in ('quarantined_schema', 'held_scope')]
            item.update(state='quarantined' if quarantined else 'missing', through_games=None)
        else:
            games = entry.get('through_games')
            if entry.get('status') == 'partial':
                state = 'partial'
            elif expected_games is None:
                state = 'unknown_expectation'
            elif games is None:
                state = 'unknown_scope'
            elif games < expected_games:
                state = 'stale'
            else:
                state = 'current'
            item.update(state=state, through_games=games, rows=entry.get('row_count'), sha256=entry.get('sha256')[:12],
                        imported_at=entry.get('first_imported_at'), forward_looking=bool(table.get('forward_looking')))
            if entry.get('warnings'):
                item['warnings'] = entry['warnings']
        item['line'] = freshness_line(item, expected_games)
        tables.append(item)
    return {'season': season, 'expected_games_through': expected_games, 'generated_at': now_iso, 'tables': tables}


def freshness_line(item, expected):
    through = item.get('through_games')
    week = f'Week {through}' if through is not None else 'no data'
    mark = {'current': '✓', 'stale': '⚠ STALE', 'partial': '⚠ PARTIAL', 'missing': '✗ MISSING', 'quarantined': '✗ QUARANTINED',
            'unknown_expectation': '?', 'unknown_scope': '? scope'}[item['state']]
    if item['state'] in ('missing', 'quarantined'):
        return f"{item['label']}: {mark}"
    return f"{item['label']}: {week} {mark}"


def public_status(fresh):
    """Metadata-only view that is safe to publish: table names, weeks and states, no licensed values."""
    return {'season': fresh['season'], 'expected_games_through': fresh['expected_games_through'], 'generated_at': fresh['generated_at'],
            'tables': [{'table': t['table'], 'label': t['label'], 'state': t['state'], 'through_games': t.get('through_games')} for t in fresh['tables']]}
