"""Multi-season bookkeeping: what exists for which season, whether a table means the same thing across seasons, data quality, and what is
ready for research.

Every output is metadata (table and column names, statuses, counts, hashes of definition text). None contains a licensed value or vendor
definition text, but all are written under FantasyPoints/manifests like everything else. Nothing here feeds a model.
"""
import hashlib
import json
import statistics
from pathlib import Path

from .parse import column_types, parse_export, to_number
from .store import current_entry

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
AVAILABILITY_CONFIG = Path(__file__).resolve().parents[2] / 'config' / 'fantasy_points_availability.json'

STATUS_MEANING = {
    'AVAILABLE': 'archived, normalized and complete',
    'PARTIAL': 'archived but incomplete (filtered or partial download): absence of a player means unknown',
    'NOT_OBTAINED': 'no file was obtained for a season that was downloaded; whether Fantasy Points offers it is UNCONFIRMED. Not zero, not proof of unavailability',
    'AVAILABILITY_UNCONFIRMED': 'that season was not downloaded or checked at all',
    'PROVIDER_UNAVAILABLE_CONFIRMED': 'CONFIRMED in Fantasy Points that it does not offer this table for that season',
    'SCHEMA_UNSUPPORTED': 'a file exists but its columns match no registered table (or a blocking schema change); preserved, not normalized',
    'IMPORT_PROBLEM': 'a file exists but was rejected or held (see the import report); fix it, do not read it as unavailable',
}


def load_config(path=AVAILABILITY_CONFIG):
    if not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_declarations(path=AVAILABILITY_CONFIG):
    return load_config(path).get('declarations', {})


def availability(registry, manifest, declarations=None, seasons=SEASONS, downloaded=None):
    """table x season status matrix. Absence of a file never proves the provider lacks the table."""
    config = load_config() if declarations is None else {}
    declarations = config.get('declarations', {}) if declarations is None else declarations
    downloaded = set(config.get('downloaded_seasons', [])) if downloaded is None else set(downloaded)
    matrix = {}
    for table_id in sorted(registry['tables']):
        row = {}
        for season in seasons:
            entry = current_entry(manifest, season, table_id)
            declared = (declarations.get(str(season)) or {}).get(table_id)
            problems = [e for e in manifest.files.values() if e.get('table_id') == table_id and e.get('season') == season
                        and e.get('status') in ('rejected', 'quarantined_schema', 'held_scope', 'unrecognized')]
            if entry:
                cell = {'status': 'PARTIAL' if entry.get('status') == 'partial' else 'AVAILABLE', 'scope': entry['scope'],
                        'through_games': entry.get('through_games'), 'rows': entry.get('row_count'),
                        'season_scope': entry.get('season_scope'), 'same_season_point_in_time': entry.get('same_season_point_in_time')}
            elif problems:
                blocked = any(p['status'] in ('quarantined_schema', 'unrecognized') for p in problems)
                cell = {'status': 'SCHEMA_UNSUPPORTED' if blocked else 'IMPORT_PROBLEM', 'detail': problems[0].get('reason', {}).get('code')}
            elif declared and declared.get('status') == 'provider_unavailable':
                cell = {'status': 'PROVIDER_UNAVAILABLE_CONFIRMED', 'evidence': declared.get('evidence')}
            elif declared or season in downloaded:
                cell = {'status': 'NOT_OBTAINED', 'evidence': (declared or {}).get('evidence') or 'absent from the downloaded batch for this season'}
            else:
                cell = {'status': 'AVAILABILITY_UNCONFIRMED'}
            row[str(season)] = cell
        matrix[table_id] = row
    return {'version': 2, 'seasons': seasons, 'status_meaning': STATUS_MEANING, 'tables': matrix}


# ---------------------------------------------------------------- schema comparison
SEVERITY = ['CONSISTENT', 'SEASON_LIMITED', 'NEEDS_REVIEW', 'DEFINITION_CHANGED', 'UNIT_CHANGED', 'SCHEMA_CHANGED']


def _scale(values):
    numbers = [abs(v) for v in values if isinstance(v, (int, float))]
    return statistics.median(numbers) if len(numbers) >= 20 else None


def _definition_hash(text):
    return hashlib.sha256(' '.join((text or '').split()).lower().encode('utf-8')).hexdigest()[:12] if text else None


def compare_exports(older_bytes, newer_bytes):
    """Column-by-column comparison of two exports of one table. Each column gets a class and the reasons behind it."""
    old, new = parse_export(older_bytes), parse_export(newer_bytes)
    old_types, new_types = column_types(old), column_types(new)
    old_index, new_index = {k: i for i, k in enumerate(old['columns'])}, {k: i for i, k in enumerate(new['columns'])}
    old_header = dict(zip(old['columns'], old['headers']))
    new_header = dict(zip(new['columns'], new['headers']))
    result = {}
    only_old = [k for k in old['columns'] if k not in new_index]
    only_new = [k for k in new['columns'] if k not in old_index]
    for key in only_old:
        result[key] = {'class': 'SEASON_LIMITED', 'side': 'older_only', 'why': 'column absent from the newer export'}
    for key in only_new:
        result[key] = {'class': 'SEASON_LIMITED', 'side': 'newer_only', 'why': 'column absent from the older export'}
    for key in new['columns']:
        if key in only_new:
            continue
        reasons, codes = [], []
        a, b = old_types[key], new_types[key]
        if 'empty' not in (a, b) and a != b:
            reasons.append(f'type {a} -> {b}')
            codes.append('SCHEMA_CHANGED')
        da, db = _definition_hash(old['glossary'].get(old_header[key])), _definition_hash(new['glossary'].get(new_header[key]))
        if da and db and da != db:
            reasons.append('definition text differs')
            codes.append('DEFINITION_CHANGED')
        elif bool(da) != bool(db):
            reasons.append('definition present in only one export')
            codes.append('NEEDS_REVIEW')
        base = new_header[key]
        if '%' in base or '/' in base:
            ma = _scale([to_number(r[old_index[key]]) for r in old['rows'] if r[old_index[key]] != ''])
            mb = _scale([to_number(r[new_index[key]]) for r in new['rows'] if r[new_index[key]] != ''])
            if ma and mb and max(ma, mb) / min(ma, mb) > 4:
                reasons.append(f'typical size differs a lot ({ma:.3g} vs {mb:.3g}): unit or scale may have changed')
                codes.append('UNIT_CHANGED')
        klass = max(codes, key=SEVERITY.index) if codes else 'CONSISTENT'
        result[key] = {'class': klass, 'why': '; '.join(reasons) or 'same name, type, definition and typical size'}
    for key in only_old:
        candidates = [n for n in only_new if n.split('.')[0] == key.split('.')[0]][:2]
        if candidates:
            result[key] = {'class': 'NEEDS_REVIEW', 'side': 'older_only', 'why': f'possible rename to {candidates}'}
    return result


def compatibility(root, registry, manifest, older=2025, newer=2026):
    """Two-season comparison of the current archived export of each table."""
    root = Path(root)
    report = {}
    for table_id in sorted(registry['tables']):
        a, b = current_entry(manifest, older, table_id), current_entry(manifest, newer, table_id)
        if not a or not b:
            report[table_id] = {'status': 'not_comparable', 'missing': [str(s) for s, e in ((older, a), (newer, b)) if not e]}
            continue
        columns = compare_exports((root / a['raw_path']).read_bytes(), (root / b['raw_path']).read_bytes())
        counts = {}
        for item in columns.values():
            counts[item['class']] = counts.get(item['class'], 0) + 1
        report[table_id] = {'status': 'compared', 'counts': counts, 'columns': {k: v for k, v in columns.items() if v['class'] != 'CONSISTENT'}}
    return {'version': 1, 'older': older, 'newer': newer, 'tables': report,
            'note': 'a similar name does not prove the same meaning; CONSISTENT only means name, type, definition text and typical size agree'}


def _longest_run(flags, seasons):
    """flags[i] says seasons[i] and seasons[i+1] agree. Returns (first, last) of the longest chain; a lone season is a chain of one."""
    if not seasons:
        return (None, None)
    best, start = (0, 0), 0
    for i, ok in enumerate(flags):
        if ok:
            if i + 1 - start > best[1] - best[0]:
                best = (start, i + 1)
        else:
            start = i + 1
    return (seasons[best[0]], seasons[best[1]])


def multi_season(root, registry, manifest, seasons=SEASONS):
    """Compare every table across all seasons that have a snapshot: stability of columns, types, definitions and scale.

    Columns are compared only between seasons of the SAME table and the SAME column key; similar names elsewhere are never combined.
    """
    root = Path(root)
    tables = {}
    for table_id in sorted(registry['tables']):
        entries = {s: current_entry(manifest, s, table_id) for s in seasons}
        present = [s for s in seasons if entries[s]]
        if not present:
            tables[table_id] = {'seasons': [], 'status': 'no_snapshots'}
            continue
        blobs = {s: (root / entries[s]['raw_path']).read_bytes() for s in present}
        pairs = {}
        for earlier, later in zip(present, present[1:]):
            pairs[(earlier, later)] = compare_exports(blobs[earlier], blobs[later])
        keys = []
        for s in present:
            for key in parse_export(blobs[s])['columns']:
                if key not in keys:
                    keys.append(key)
        columns = {}
        for key in keys:
            have = [s for s in present if key in {c for c in parse_export(blobs[s])['columns']}]
            classes, reasons = [], []
            for (earlier, later), result in pairs.items():
                item = result.get(key)
                if item is None:
                    continue
                classes.append(item['class'])
                if item['class'] != 'CONSISTENT':
                    reasons.append(f'{earlier}->{later}: {item["why"]}')
            overall = 'SEASON_LIMITED' if len(have) < len(present) and all(c in ('CONSISTENT', 'SEASON_LIMITED') for c in classes) else \
                (max(classes, key=SEVERITY.index) if classes else 'CONSISTENT')
            flags = [pairs[(e, l)].get(key, {}).get('class') == 'CONSISTENT' and l - e == 1 for e, l in zip(present, present[1:])]
            run = _longest_run(flags, present)
            columns[key] = {'class': overall, 'seasons': have, 'consistent_run': [run[0], run[1]] if run[0] is not None else None, 'notes': reasons[:3]}
        table_flags = [all(item['class'] == 'CONSISTENT' for item in pairs[(e, l)].values()) and l - e == 1 for e, l in zip(present, present[1:])]
        table_run = _longest_run(table_flags, present)
        counts = {}
        for item in columns.values():
            counts[item['class']] = counts.get(item['class'], 0) + 1
        tables[table_id] = {'seasons': present, 'first_season': present[0], 'last_season': present[-1], 'column_counts': counts,
                            'table_consistent_run': [table_run[0], table_run[1]], 'columns': {k: v for k, v in columns.items() if v['class'] != 'CONSISTENT'},
                            'consistent_columns': sum(1 for v in columns.values() if v['class'] == 'CONSISTENT')}
    return {'version': 2, 'seasons': seasons, 'tables': tables,
            'note': 'columns are compared only within the same table and key. CONSISTENT = name, type, vendor definition text and typical size of rate columns '
                    'agree between adjacent available seasons; it does not prove identical meaning. Never merge fields across tables by name similarity.'}


# ---------------------------------------------------------------- data quality
SIBLING_GROUPS = {
    'routes_and_separation': ['receiving_routes_run', 'receiving_separation_by_alignment', 'receiving_separation_by_breaks',
                              'receiving_separation_by_coverage', 'receiving_separation_by_routes'],
    'receiving_advanced_and_coverage_split': ['receiving_advanced', 'receiving_man_vs_zone'],
    'passing': ['passing_advanced', 'passing_depth', 'passing_basic'],
    'rushing': ['rushing_advanced', 'rushing_basic'],
}
NONNEGATIVE_BASES = {'RTE', 'TGT', 'REC', 'ATT', 'Snaps', 'DB', 'G', 'SNAPS', 'TM Snaps'}
# shares of a total that can legitimately leave 0-100 when a component is negative (yards before contact, air yards, a team total)
SIGNED_SHARE_BASES = {'YACO %', 'YAC %', 'TM YDS %', 'TM TD %', 'EXP YDS %'}


def _doc(root, entry):
    return json.loads((Path(root) / entry['normalized_path']).read_text(encoding='utf-8'))


def quality(root, registry, manifest, seasons=SEASONS):
    root = Path(root)
    seasons_report, tables_report, sibling_report, yoy = {}, {}, [], []
    last_rows = {}
    ids_by = {}
    for season in seasons:
        season_tally = {'tables': 0, 'rows': 0, 'player_rows': 0, 'matched': 0, 'ambiguous': 0, 'unmatched': 0, 'other': 0, 'review': 0, 'multi_team': 0}
        for table_id in sorted(registry['tables']):
            entry = current_entry(manifest, season, table_id)
            if not entry:
                continue
            doc = _doc(root, entry)
            rows = doc['rows']
            season_tally['tables'] += 1
            season_tally['rows'] += len(rows)
            teams = {t for r in rows for t in (r['entity'].get('teams') or ([r['entity'].get('team')] if r['entity'].get('team') else []))}
            item = {'rows': len(rows), 'teams': len(teams), 'status': entry.get('status'), 'scope': entry.get('scope')}
            if doc['level'] == 'player':
                tally = doc['identity']['tally']
                season_tally['player_rows'] += len(rows)
                for k, v in tally.items():
                    season_tally[k if k in ('matched', 'ambiguous', 'unmatched') else 'other'] += v
                season_tally['review'] += len(doc['identity']['review'])
                season_tally['multi_team'] += sum(1 for r in rows if r['entity'].get('multi_team'))
                ids = [r['entity']['player_id'] for r in rows if r['entity'].get('player_id')]
                item['duplicate_player_ids'] = len(ids) - len(set(ids))
                item['split_entities'] = sum(1 for r in rows if r['entity'].get('split_entity'))
                games = [r['context'].get('games') for r in rows if isinstance(r['context'].get('games'), (int, float))]
                item['max_games'] = max(games) if games else None
                item['games_over_17'] = sum(1 for g in games if g > 17)
                item['games_over_17_single_team'] = sum(1 for r in rows if isinstance(r['context'].get('games'), (int, float)) and r['context']['games'] > 17
                                                        and not r['entity'].get('multi_team'))
                ids_by[(season, table_id)] = {r['entity']['player_id'] or (r['entity']['name'], r['entity'].get('fp_team')) for r in rows}
                item['unmatched_names'] = sorted({r['entity']['name'] for r in rows if r['entity']['match']['status'] == 'unmatched'})[:10]
            else:
                item['missing_teams'] = sorted(set(__import__('fp_ingest.identity', fromlist=['TEAMS']).TEAMS) - teams)
            impossible, explained = 0, 0
            percent_cols = [c['key'] for c in doc['columns'] if c.get('unit') == 'percent_points']
            count_cols = [c['key'] for c in doc['columns'] if c['key'].split('.', 1)[-1].split('#')[0] in NONNEGATIVE_BASES]
            for r in rows:
                for key in percent_cols:
                    v = r['metrics'].get(key)
                    if isinstance(v, (int, float)) and (v < -0.001 or v > 100.5):
                        if key.split('.', 1)[-1].split('#')[0] in SIGNED_SHARE_BASES:
                            explained += 1
                        else:
                            impossible += 1
                for key in count_cols:
                    v = r['metrics'].get(key)
                    if isinstance(v, (int, float)) and v < 0:
                        impossible += 1
            item['impossible_values'] = impossible
            item['signed_share_outside_0_100'] = explained
            cells = sum(len(r['metrics']) for r in rows)
            item['null_pct'] = round(100 * sum(1 for r in rows for v in r['metrics'].values() if v is None) / max(1, cells), 1)
            tables_report.setdefault(table_id, {})[str(season)] = item
            previous = last_rows.get(table_id)
            if previous and previous[1] and not 0.75 <= len(rows) / previous[1] <= 1.33:
                yoy.append({'table': table_id, 'from': previous[0], 'to': season, 'rows': [previous[1], len(rows)]})
            last_rows[table_id] = (season, len(rows))
        if season_tally['tables']:
            pr = season_tally['player_rows']
            season_tally['match_rate'] = round(100 * season_tally['matched'] / pr, 2) if pr else None
            seasons_report[str(season)] = season_tally
    for season in seasons:
        for group, members in SIBLING_GROUPS.items():
            sets = {t: ids_by[(season, t)] for t in members if (season, t) in ids_by}
            if len(sets) < 2:
                continue
            union = set().union(*sets.values())
            core = set.intersection(*sets.values())
            sibling_report.append({'season': season, 'group': group, 'tables': {t: len(s) for t, s in sets.items()},
                                   'in_all': len(core), 'in_some_only': len(union) - len(core)})
    return {'version': 1, 'seasons': seasons_report, 'tables': tables_report, 'sibling_populations': sibling_report, 'row_count_jumps': yoy,
            'note': 'siblings legitimately differ (eligibility thresholds differ by table); large differences or year-over-year jumps are listed for review'}


# ---------------------------------------------------------------- research readiness
FAMILIES = {
    'routes / route participation': ['receiving_routes_run'],
    'alignment (wide/slot/inline/backfield)': ['receiving_routes_run', 'receiving_separation_by_alignment'],
    'first-read / designed targets': ['receiving_advanced'],
    'separation': ['receiving_separation_by_alignment', 'receiving_separation_by_breaks', 'receiving_separation_by_coverage', 'receiving_separation_by_routes'],
    'coverage / shell': ['receiving_man_vs_zone', 'receiving_separation_by_coverage', 'coverage_matrix', 'qb_coverage_matchup', 'wr_coverage_matchup'],
    'route concepts': ['receiving_separation_by_routes'],
    'advanced rushing': ['rushing_advanced'],
    'XFP / opportunity': ['rushing_bell_cow', 'efficiency'],
    'red zone / goal line': ['offense_snaps', 'rushing_basic', 'receiving_basic'],
    'pressure / time-to-throw': ['passing_advanced'],
    'run / pass tendencies': ['run_pass_report'],
    'OL / DL': ['line_matchups'],
}
DESCRIPTIVE_ONLY = {'rushing_basic', 'receiving_basic', 'passing_basic'}


def readiness(registry, availability_matrix, compat):
    """Per feature family: how many consecutive consistent regular-season seasons exist. Coverage is not predictive value."""
    out = {}
    for family, tables in FAMILIES.items():
        per_table = {}
        for table_id in tables:
            cells = availability_matrix['tables'].get(table_id, {})
            have = [int(s) for s, c in cells.items() if c['status'] in ('AVAILABLE', 'PARTIAL')]
            info = compat['tables'].get(table_id, {})
            run = info.get('table_consistent_run')
            historical = [s for s in have if s < 2026]
            partial = [s for s in have if cells[str(s)]['status'] == 'PARTIAL']
            per_table[table_id] = {'seasons': have, 'historical_seasons': historical, 'partial_seasons': partial, 'consistent_run': run,
                                   'non_consistent_columns': sum(v for k, v in (info.get('column_counts') or {}).items() if k not in ('CONSISTENT', 'SEASON_LIMITED'))}
        usable = [t for t, v in per_table.items() if v['seasons']]
        if not usable:
            label = 'NO_DATA'
        elif all(t in DESCRIPTIVE_ONLY for t in usable):
            label = 'DESCRIPTIVE_ONLY_FOR_NOW'
        else:
            best = max((per_table[t] for t in usable if t not in DESCRIPTIVE_ONLY), key=lambda v: (len(v['historical_seasons']), len(v['seasons'])))
            hist = len(best['historical_seasons'])
            clean_run = (best['consistent_run'][1] - best['consistent_run'][0] + 1) if best['consistent_run'] else 0
            if hist == 0:
                label = '2026_PROSPECTIVE_ONLY'
            elif best['non_consistent_columns'] and clean_run < 3:
                label = 'NEEDS_SCHEMA_REVIEW'
            elif hist >= 4 and clean_run >= 4 and not best['partial_seasons']:
                label = 'READY_FOR_MULTI_SEASON_RESEARCH'
            else:
                label = 'LIMITED_HISTORY'
        caveats = [f"{t}: {v['non_consistent_columns']} column(s) changed unit/definition/schema; consistent run {v['consistent_run'][0]}-{v['consistent_run'][1]}"
                   for t, v in per_table.items() if v['non_consistent_columns']]
        descriptive = {t: v['historical_seasons'] for t, v in per_table.items() if t in DESCRIPTIVE_ONLY and v['historical_seasons']}
        out[family] = {'label': label, 'caveats': caveats, 'descriptive_history_in_basic_tables': descriptive, 'tables': per_table}
    return {'version': 1, 'families': out,
            'note': 'READY means enough consistent completed regular seasons exist to design a study; it does not mean the metric predicts anything. '
                    'Completed-season totals are retrospective and may never feed same-season predictions.'}
