"""Scan the Inbox, archive immutable raw copies, normalize, resolve identities, update manifests and freshness.

Safety rules enforced here (each has a test that fails when the rule is removed):
* the Inbox and the raw archive are never modified or deleted; raw copies are content-addressed (sha256)
* a bad file is preserved and reported, never imported, and never replaces a previously valid snapshot
* the manifest is written last, atomically, so an interrupted run leaves nothing half-imported and resumes cleanly
* an unknown/changed schema, wrong season, truncated file or ambiguous scope is held, not guessed
* blank is None, never 0; unmatched players keep player_id null and are listed, never fuzzy-matched
"""
import datetime
import hashlib
import json
from pathlib import Path

from . import fields as fieldmod
from . import identity as idmod
from . import registry as regmod
from .parse import ParseError, column_types, parse_export, sha256, to_number
from .store import (GOOD, Manifest, RunLock, atomic_write, clean_temporaries, find_inbox, freshness, public_status, scope_dir, write_json)

MIN_TEAMS_PLAYER = 24
MIN_TEAMS_TEAM = 28
FULL_SEASON_GAMES = 17  # every 2021+ season; a finished season's league-wide maximum is 17


def iso(moment):
    return moment.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def season_of(moment):
    """Same convention as the Validation ledger: July-December is that year's season, January-June the previous one."""
    return moment.year if moment.month >= 7 else moment.year - 1


def _find(columns, group_names, base):
    for key in columns:
        group, _, name = key.partition('.')
        if name.split('#')[0] == base and group in group_names:
            return key
    return None


def inspect_bytes(name, data, registry, mtime=None):
    """Read-only description of one file. Never raises; problems are returned as ``error``."""
    try:
        return _inspect(name, data, registry, mtime)
    except Exception as error:  # a surprise in one file is a rejected file, not a crashed refresh
        return {'original_filename': name, 'sha256': sha256(data), 'bytes': len(data), 'modified_at': mtime,
                'error': {'code': 'unreadable', 'message': f'{type(error).__name__}: {error}'}}, None


def _inspect(name, data, registry, mtime):
    info = {'original_filename': name, 'sha256': sha256(data), 'bytes': len(data), 'modified_at': mtime}
    try:
        parsed = parse_export(data)
    except ParseError as error:
        info.update(error={'code': error.code, 'message': str(error)})
        return info, None
    cls = regmod.classify(registry, name, parsed)
    columns = parsed['columns']
    table = registry['tables'].get(cls['table_id']) if cls['table_id'] else None
    group_names = {'Player Details', 'Team Details'}
    season_key, games_key = _find(columns, group_names, 'Season'), _find(columns, group_names, 'G')
    team_key = _find(columns, group_names, 'Team')
    name_key = _find(columns, group_names, 'Name')
    info.update(row_count=len(parsed['rows']), column_count=len(columns), table_id=cls['table_id'], schema_status=cls['status'],
                drift=cls['drift'], level=(table or {}).get('level'), notes=parsed['notes'])
    if season_key and games_key:
        seasons = sorted({row[columns.index(season_key)] for row in parsed['rows']})
        cells = [row[columns.index(games_key)] for row in parsed['rows'] if row[columns.index(games_key)] != '']
        numbers = [to_number(cell) for cell in cells]
        if any(n is None for n in numbers):
            info['error'] = {'code': 'games_not_numeric', 'message': f"G column holds non-numeric values such as {next(c for c, n in zip(cells, numbers) if n is None)!r}"}
            return info, None
        games = [int(n) for n in numbers]
        info.update(seasons=seasons, games_min=min(games) if games else None, games_max=max(games) if games else None)
    teams = set()
    for row in parsed['rows']:
        try:
            if team_key and (table or {}).get('level') == 'player':
                teams.add(idmod.canonical_team(row[columns.index(team_key)]))
            elif name_key and (table or {}).get('level') == 'team':
                teams.add(idmod.canonical_team(row[columns.index(name_key)]))
        except idmod.TeamError:
            info.setdefault('unknown_teams', set()).add(row[columns.index(team_key or name_key)])
    info['team_count'] = len(teams)
    if 'unknown_teams' in info:
        info['unknown_teams'] = sorted(info['unknown_teams'])
    by_class = {}
    for key in columns:
        by_class[fieldmod.classify_column(key)['class']] = by_class.get(fieldmod.classify_column(key)['class'], 0) + 1
    info['columns_by_class'] = by_class
    return info, {'parsed': parsed, 'cls': cls, 'table': table, 'keys': {'season': season_key, 'games': games_key, 'team': team_key, 'name': name_key}}


def decide_scope(info, current_season, max_possible_games, override=None, in_season=True):
    """Return (scope, through_games, scope_source, problem). problem is a (code, message) when the file cannot be imported."""
    seasons = info.get('seasons') or []
    if len(seasons) != 1 or not str(seasons[0]).isdigit():
        return None, None, None, ('season_unclear', f'Season column must hold exactly one year, found {seasons[:4]}')
    season = int(seasons[0])
    games = info.get('games_max')
    if games is None or games < 1 or games > 18:
        return None, None, None, ('games_implausible', f'games played looks wrong: {games}')
    if season > current_season:
        return None, None, None, ('future_season', f'Season {season} is after the current season {current_season}')
    live = season == current_season and in_season  # outside July-January the "current" season is finished: treat it like a past one
    if override is not None and live:
        if override < 1 or (max_possible_games is not None and override > max_possible_games):
            return None, None, None, ('override_invalid', f'--through-week {override} is outside 1..{max_possible_games}')
        return 'season_to_date', int(override), 'operator', None
    if live:
        if max_possible_games is not None and games > max_possible_games:
            return None, None, None, ('future_games', f'export has {games} games but only {max_possible_games} can have been played')
        return 'season_to_date', games, 'games_played', None
    if games >= FULL_SEASON_GAMES:
        return 'full_season', games, 'games_played', None
    return 'unclassified', games, 'games_played', ('scope_unclear', f'{season} export has at most {games} games: partial or week-range export, not a full season')


def normalize(entry, ctx, index):
    """Build the GOING-facing rows. Returns (document, identity_report)."""
    parsed, table, keys = ctx['parsed'], ctx['table'], ctx['keys']
    columns = parsed['columns']
    types = ctx['cls']['types']
    level = table['level']
    groups = {'Player Details', 'Team Details'}
    special = {key for key in (_find(columns, {'Defense Stats'}, 'Name'), _find(columns, {'Offense Stats'}, 'Team')) if key} if table['id'] == 'line_matchups' else set()
    ident = {base: _find(columns, groups, base) for base in ('Rank', 'Name', 'Team', 'POS', 'G', 'OPP', 'Location', 'Team Name')}
    metric_keys = [key for key in columns if key not in ident.values() and key not in special and key != keys['season']]
    position = {key: columns.index(key) for key in columns}
    rows, review, unresolved = [], [], []
    tally = {}
    for raw in parsed['rows']:
        def cell(key):
            return raw[position[key]] if key else ''
        context = {'games': to_number(cell(ident['G'])), 'source_rank': to_number(cell(ident['Rank']))}
        if ident['OPP'] and cell(ident['OPP']):
            try:
                context['opponent'] = idmod.canonical_team(cell(ident['OPP']))
            except idmod.TeamError:
                context['opponent'] = None
                context['opponent_raw'] = cell(ident['OPP'])
        if level == 'player':
            entity = {'type': 'player', 'name': cell(ident['Name']), 'fp_team': cell(ident['Team']), 'position': cell(ident['POS'])}
            try:
                entity['team'] = idmod.canonical_team(entity['fp_team'])
            except idmod.TeamError:
                entity['team'] = None
            if index is None:
                match = {'status': 'no_roster', 'player_id': None, 'method': None, 'candidates': [], 'note': 'no roster available for this season'}
            else:
                match = index.resolve(entity['name'], entity['fp_team'], entity['position'])
            entity['player_id'] = match['player_id']
            entity['match'] = {k: match[k] for k in ('status', 'method', 'note')}
            entity['match']['review'] = match['status'] == 'matched' and match['method'] not in ('name_team_position', 'alias')
            tally[match['status']] = tally.get(match['status'], 0) + 1
            if match['status'] != 'matched' or entity['match']['review']:
                (unresolved if match['status'] != 'matched' else review).append(
                    {'name': entity['name'], 'team': entity['fp_team'], 'position': entity['position'], 'status': match['status'],
                     'method': match['method'], 'candidates': match['candidates'], 'note': match['note'], 'player_id': match['player_id']})
        else:
            label = cell(ident['Name'])
            try:
                code = idmod.canonical_team(label)
            except idmod.TeamError:
                code = None
            entity = {'type': 'team', 'name': label, 'team': code, 'location': cell(ident['Location']), 'nickname': cell(ident['Team Name'])}
            tally['matched' if code else 'team_unknown'] = tally.get('matched' if code else 'team_unknown', 0) + 1
            if code is None:
                unresolved.append({'name': label, 'status': 'team_unknown'})
            if special:
                try:
                    context['opponent'] = idmod.canonical_team(cell(_find(columns, {'Defense Stats'}, 'Name')))
                    offense = idmod.canonical_team(cell(_find(columns, {'Offense Stats'}, 'Team')))
                    if code and offense != code:
                        entity['team_conflict'] = offense
                except idmod.TeamError:
                    context['opponent'] = None
        metrics = {}
        for key in metric_keys:
            value = cell(key)
            metrics[key] = None if value == '' else (to_number(value) if types[key] != 'text' else value)
        rows.append({'entity': entity, 'context': context, 'metrics': metrics})
    document = {
        'schema': 'fp-normalized-v1', 'source': 'Fantasy Points Data Suite', 'licensed': True, 'table_id': table['id'], 'level': level,
        'season': entry['season'], 'scope': entry['scope'], 'through_games': entry['through_games'], 'forward_looking': table['forward_looking'],
        'target_game_hint': entry['through_games'] + 1 if table['forward_looking'] else None,
        'known_at': entry['first_imported_at'], 'known_live': entry['known_live'], 'raw_sha256': entry['sha256'],
        'columns': [{'key': key, 'type': types[key], 'unit': fieldmod.unit_hint(key), **fieldmod.classify_column(key)} for key in metric_keys],
        'leakage_note': fieldmod.LEAKAGE_NOTE, 'rows': rows,
    }
    return document, {'tally': tally, 'review': review, 'unresolved': unresolved}


class Importer:
    def __init__(self, root, registry, now=None, rosters=None, current_season=None, max_possible_games=None, expected_games=None,
                 through_override=None, hooks=None):
        self.root = Path(root)
        self.registry = registry
        self.now = now or datetime.datetime.now(datetime.timezone.utc)
        self.rosters = rosters or (lambda season: None)
        self.current_season = current_season or season_of(self.now)
        self.max_possible_games = max_possible_games
        self.expected_games = expected_games
        self.through_override = through_override
        self.in_season = self.now.month >= 7 or self.now.month == 1
        self.hooks = hooks or {}
        self.manifest = Manifest(self.root)
        self._indexes = {}

    def index(self, season):
        if season not in self._indexes:
            self._indexes[season] = self.rosters(season)
        return self._indexes[season]

    # -- helpers --
    def _raw_path(self, folder, name, sha):
        return self.root / 'raw' / folder / f'{name}__{sha[:12]}.csv'

    def _store_raw(self, path, data, sha):
        """Write once; if a same-named file exists it must already be byte-identical. A damaged copy is repaired from the Inbox bytes."""
        if path.exists():
            if sha256(path.read_bytes()) == sha:
                return False
        atomic_write(path, data)
        return True

    def _hook(self, name):
        if name in self.hooks:
            self.hooks[name]()

    # -- one file --
    def import_file(self, name, data, mtime=None):
        sha = sha256(data)
        existing = self.manifest.files.get(sha)
        if existing and existing.get('status') in GOOD and existing.get('normalized_path') and (self.root / existing['normalized_path']).exists() \
                and (self.root / existing['raw_path']).exists() and sha256((self.root / existing['raw_path']).read_bytes()) == sha:
            return {'file': name, 'outcome': 'duplicate', 'table_id': existing.get('table_id'), 'sha256': sha}
        # anything else (never imported, previously held, or a damaged copy) is evaluated again
        carry = existing if existing and existing.get('status') in GOOD else None  # a repair must not change the revision chain or known_at
        info, ctx = inspect_bytes(name, data, self.registry, mtime)
        now = iso(self.now)
        base = {'sha256': sha, 'original_filename': name, 'bytes': len(data), 'first_seen_at': (existing or {}).get('first_seen_at', now),
                'captured_at': mtime, 'captured_at_source': 'file_modified_time' if mtime else None, 'source': 'Fantasy Points Data Suite'}

        seasons = info.get('seasons') or []
        season_guess = int(seasons[0]) if len(seasons) == 1 and str(seasons[0]).isdigit() else None

        def hold(status, folder, code, message, extra=None):
            path = self.root / 'raw' / folder / f'{sha[:12]}__{Path(name).name}'
            self._store_raw(path, data, sha)
            entry = {**base, 'status': status, 'reason': {'code': code, 'message': message}, 'raw_path': str(path.relative_to(self.root)).replace('\\', '/'),
                     'table_id': info.get('table_id'), 'season': season_guess, **(extra or {})}
            self.manifest.files[sha] = entry
            return {'file': name, 'outcome': status, 'table_id': info.get('table_id'), 'sha256': sha, 'reason': entry['reason']}

        if 'error' in info:
            return hold('rejected', '_rejected', info['error']['code'], info['error']['message'])
        if ctx['cls']['status'] == 'unknown':
            return hold('unrecognized', '_unrecognized', 'unknown_table', f"{info['column_count']} columns do not match any known Fantasy Points table")
        if info.get('unknown_teams'):
            return hold('rejected', '_rejected', 'unknown_team', f"team codes not recognised: {info['unknown_teams'][:5]}")
        drift = info['drift']
        if regmod.blocking(drift):
            return hold('quarantined_schema', '_quarantine', 'schema_drift',
                        f"{ctx['cls']['table_id']}: missing {drift['missing'][:6]}, renamed {drift['possible_renames'][:3]}, type changes {drift['type_changes'][:3]}",
                        {'drift': drift})
        scope, games, scope_source, problem = decide_scope(info, self.current_season, self.max_possible_games, self.through_override, self.in_season)
        if problem and scope is None:
            return hold('rejected', '_rejected', problem[0], problem[1])
        season = int(info['seasons'][0])
        if problem:
            return hold('held_scope', '_quarantine', problem[0], problem[1], {'season': season, 'table_id': info['table_id'], 'through_games': games})
        table = ctx['table']
        warnings = [note for note in info['notes'] if note != 'no_trailing_newline']  # real exports end without a newline: normal
        teams_needed = MIN_TEAMS_PLAYER if table['level'] == 'player' else MIN_TEAMS_TEAM
        status = 'imported'
        if info['team_count'] < teams_needed:
            status = 'partial'
            warnings.append(f"only {info['team_count']} teams present (expected at least {teams_needed}): filtered or partial download, absence means unknown")
        if 'no_glossary_footer' in info['notes']:
            status = 'partial'
        if drift and drift['new']:
            status = 'imported_review' if status == 'imported' else status
            warnings.append(f"new columns need review: {drift['new'][:8]}")
        folder = f"{season}/{scope_dir(scope, games)}"
        raw_path = self._raw_path(folder, table['id'], sha)
        self._store_raw(raw_path, data, sha)
        self._hook('after_raw')
        entry = {**base, 'status': status, 'table_id': table['id'], 'season': season, 'scope': scope, 'scope_source': scope_source,
                 # known_at: when GOING first accepted this data, not when it first saw the file
                 'first_imported_at': carry['first_imported_at'] if carry else now,
                 'through_games': games, 'through_week': games if games < 14 else None, 'known_live': scope == 'season_to_date',
                 'forward_looking': table['forward_looking'], 'row_count': info['row_count'], 'column_count': info['column_count'],
                 'team_count': info['team_count'], 'schema_signature': regmod.signature(ctx['parsed']['columns']),
                 'warnings': warnings, 'raw_path': str(raw_path.relative_to(self.root)).replace('\\', '/'), 'drift': drift if drift and drift['new'] else None}
        document, identity = normalize(entry, ctx, self.index(season) if table['level'] == 'player' else None)
        document['identity'] = {'tally': identity['tally'], 'review': identity['review'], 'unresolved': identity['unresolved']}
        entry['identity'] = {'tally': identity['tally'], 'review': len(identity['review']), 'unresolved': len(identity['unresolved'])}
        normalized_path = self.root / 'normalized' / str(season) / table['id'] / f"{scope_dir(scope, games)}__{sha[:12]}.json"
        write_json(normalized_path, document)
        entry['normalized_path'] = str(normalized_path.relative_to(self.root)).replace('\\', '/')
        self._hook('after_normalized')
        outcome = 'imported'
        previous = [e for e in self.manifest.entries(season, table['id'], statuses=GOOD)
                    if e['sha256'] != sha and e.get('scope') == scope and e.get('through_games') == games and not e.get('superseded_by')]
        if carry:
            for key in ('superseded_by', 'revision_of'):
                if carry.get(key):
                    entry[key] = carry[key]
            outcome = 'repaired'
            previous = []
        for old in previous:
            if status == 'partial' and old.get('status') != 'partial':
                warnings.append('a partial re-export does not replace the complete snapshot for the same week')
                outcome = 'partial_revision_kept_old_current'
            elif (mtime or '') >= (old.get('captured_at') or ''):  # the newer download wins, whatever order the files are processed in
                old['superseded_by'] = sha
                entry['revision_of'] = old['sha256']
                outcome = 'revision'
            else:
                entry['superseded_by'] = old['sha256']
                warnings.append('an older download of this week arrived after a newer one; the newer stays current')
                outcome = 'older_revision_ignored'
        if outcome == 'imported':
            newest = max((e.get('through_games') or 0 for e in self.manifest.entries(season, table['id'], statuses=GOOD)), default=0)
            if games < newest:
                outcome = 'older_snapshot'
        if status == 'partial' and outcome == 'imported':
            outcome = 'partial'
        self.manifest.files[sha] = entry
        return {'file': name, 'outcome': outcome, 'table_id': table['id'], 'season': season, 'through_games': games, 'sha256': sha,
                'rows': info['row_count'], 'identity': identity['tally'], 'identity_details': identity, 'warnings': warnings, 'status': status}

    # -- whole inbox --
    def run(self, inbox=None):
        inbox = Path(inbox) if inbox else find_inbox(self.root)
        with RunLock(self.root):
            return self._run(inbox)

    def _run(self, inbox):
        cleaned, cleanup_failures = clean_temporaries(self.root)
        results = []
        files = sorted((p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() == '.csv'), key=lambda p: (p.stat().st_mtime, p.name))
        for path in files:
            try:
                data = path.read_bytes()
                mtime = iso(datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc))
                results.append(self.import_file(path.name, data, mtime))
            except Exception as error:  # one dataset failing must not stop the others or the rest of the refresh
                results.append({'file': path.name, 'outcome': 'error', 'reason': {'code': type(error).__name__, 'message': str(error)}})
                if self.hooks.get('raise_errors'):
                    raise
        self.manifest.save()  # last: a crash before this line leaves only content-addressed files that the next run reuses
        fresh = freshness(self.registry, self.manifest, self.current_season, self.expected_games, iso(self.now))
        write_json(self.root / 'manifests' / 'freshness.json', fresh)
        report = self.report(results, fresh, cleaned)
        report['temporary_files_failed'] = cleanup_failures
        for result in report['results']:
            result.pop('identity_details', None)  # per-player detail lives in the normalized file; the report keeps counts
        write_json(self.root / 'manifests' / 'last_run.json', report)
        return report

    def report(self, results, fresh, cleaned=0):
        counts = {}
        for result in results:
            counts[result['outcome']] = counts.get(result['outcome'], 0) + 1
        problems = [r for r in results if r['outcome'] in ('rejected', 'unrecognized', 'quarantined_schema', 'held_scope', 'error')]
        review = [{'file': r['file'], 'table': r.get('table_id'), 'warnings': r['warnings']} for r in results if r.get('warnings')]
        unresolved, check = [], []
        for result in results:
            details = result.get('identity_details') or {}
            for row in details.get('unresolved', []):
                unresolved.append({'table': result.get('table_id'), **row})
            for row in details.get('review', []):
                check.append({'table': result.get('table_id'), **row})
        return {'generated_at': iso(self.now), 'current_season': self.current_season, 'files_scanned': len(results), 'outcomes': counts,
                'results': results, 'problems': problems, 'warnings': review, 'identity_unresolved': unresolved, 'identity_review': check,
                'freshness': [t['line'] for t in fresh['tables']], 'temporary_files_removed': cleaned}
