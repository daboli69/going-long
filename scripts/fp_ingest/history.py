"""Multi-season bookkeeping: which Fantasy Points tables exist for which season, and whether a table means the same thing across seasons.

Both outputs are metadata (table names, column names, statuses, counts, hashes of definition text); neither contains a licensed value
or vendor definition text, so they are safe to look at anywhere, but they are written under FantasyPoints/manifests like everything else.
"""
import hashlib
import json
import statistics
from pathlib import Path

from .parse import column_types, parse_export, to_number
from .store import GOOD, current_entry

SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
AVAILABILITY_CONFIG = Path(__file__).resolve().parents[2] / 'config' / 'fantasy_points_availability.json'

# How a missing table must be read. Only "provider_unavailable" means the provider does not offer it; "unknown" means nobody has checked.
STATUS_MEANING = {
    'imported': 'archived and normalized',
    'provider_unavailable': 'Fantasy Points does not offer this table for that season (operator-declared); absence is NOT an import failure and NOT zero',
    'import_problem': 'a file for this table and season exists but was held or rejected: fix it, do not treat it as unavailable',
    'unknown': 'no file and no declaration: not yet downloaded or not yet checked',
}


def load_declarations(path=AVAILABILITY_CONFIG):
    if not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding='utf-8')).get('declarations', {})


def availability(registry, manifest, declarations=None, seasons=SEASONS):
    declarations = load_declarations() if declarations is None else declarations
    matrix = {}
    for table_id in sorted(registry['tables']):
        row = {}
        for season in seasons:
            entry = current_entry(manifest, season, table_id)
            declared = (declarations.get(str(season)) or {}).get(table_id)
            problems = [e for e in manifest.files.values() if e.get('table_id') == table_id and e.get('season') == season
                        and e.get('status') in ('rejected', 'quarantined_schema', 'held_scope', 'unrecognized')]
            if entry:
                cell = {'status': 'imported', 'scope': entry['scope'], 'through_games': entry.get('through_games'), 'rows': entry.get('row_count'),
                        'complete': entry.get('status') != 'partial'}
            elif problems:
                cell = {'status': 'import_problem', 'detail': problems[0].get('reason', {}).get('code')}
            elif declared:
                cell = {'status': 'provider_unavailable', 'evidence': declared.get('evidence')}
            else:
                cell = {'status': 'unknown'}
            row[str(season)] = cell
        matrix[table_id] = row
    return {'version': 1, 'seasons': seasons, 'status_meaning': STATUS_MEANING, 'tables': matrix}


def _scale(values):
    numbers = [abs(v) for v in values if isinstance(v, (int, float))]
    return statistics.median(numbers) if len(numbers) >= 20 else None


def _definition_hash(text):
    return hashlib.sha256(' '.join((text or '').split()).lower().encode('utf-8')).hexdigest()[:12] if text else None


def compare_exports(older_bytes, newer_bytes):
    """Column-by-column comparison of two exports of the same table (typically 2025 vs 2026)."""
    old, new = parse_export(older_bytes), parse_export(newer_bytes)
    old_types, new_types = column_types(old), column_types(new)
    old_index, new_index = {k: i for i, k in enumerate(old['columns'])}, {k: i for i, k in enumerate(new['columns'])}
    old_header = dict(zip(old['columns'], old['headers']))
    new_header = dict(zip(new['columns'], new['headers']))
    result = {}
    only_old = [k for k in old['columns'] if k not in new_index]
    only_new = [k for k in new['columns'] if k not in old_index]
    for key in old['columns']:
        if key in only_old:
            result[key] = {'class': 'HISTORICAL_ONLY', 'why': 'column absent from the newer export'}
    for key in new['columns']:
        if key in only_new:
            result[key] = {'class': '2026_ONLY', 'why': 'column absent from the older export'}
    for key in new['columns']:
        if key in only_new:
            continue
        reasons = []
        a, b = old_types[key], new_types[key]
        if 'empty' not in (a, b) and a != b:
            reasons.append(f'type {a} -> {b}')
        da, db = _definition_hash(old['glossary'].get(old_header[key])), _definition_hash(new['glossary'].get(new_header[key]))
        if da and db and da != db:
            reasons.append('definition text differs')
        elif bool(da) != bool(db):
            reasons.append('definition present in only one export')
        base = new_header[key]
        if '%' in base or '/' in base:
            ma = _scale([to_number(r[old_index[key]]) for r in old['rows'] if r[old_index[key]] != ''])
            mb = _scale([to_number(r[new_index[key]]) for r in new['rows'] if r[new_index[key]] != ''])
            if ma and mb and max(ma, mb) / min(ma, mb) > 4:
                reasons.append(f'typical size differs a lot ({ma:.3g} vs {mb:.3g}): unit or scale may have changed')
        hard = any(r.startswith(('type', 'definition text differs')) for r in reasons)
        result[key] = {'class': 'SCHEMA_CHANGED' if hard else ('NEEDS_REVIEW' if reasons else 'CONSISTENT'), 'why': '; '.join(reasons) or 'same name, type, definition and typical size'}
    renames = {k: [n for n in only_new if n.split('.')[0] == k.split('.')[0]][:2] for k in only_old}
    for key, candidates in renames.items():
        if candidates:
            result[key] = {'class': 'NEEDS_REVIEW', 'why': f'possible rename to {candidates}'}
    return result


def compatibility(root, registry, manifest, older=2025, newer=2026):
    """Compare the current archived export of each table in two seasons."""
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
