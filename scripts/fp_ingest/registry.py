"""Table registry: which Fantasy Points export a file is, decided by its columns (never by its filename alone)."""
import difflib
import hashlib
import json
import re
from pathlib import Path

from .parse import column_types, parse_export
from .table_meta import TABLES

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / 'config' / 'fantasy_points_tables.json'
IDENTITY_KEYS = {'Rank', 'Name', 'Team', 'POS', 'G', 'Season', 'OPP', 'Location', 'Team Name'}


def signature(keys):
    return hashlib.sha256('\x1f'.join(keys).encode('utf-8')).hexdigest()[:16]


def filename_stem(name):
    stem = re.sub(r'\.csv$', '', name, flags=re.I)
    stem = re.sub(r'\s*\(\d+\)\s*$', '', stem)
    stem = re.sub(r'[\s_\-]*(export)?$', '', stem, flags=re.I)
    return re.sub(r'[^a-z0-9]', '', stem.lower())


def merge_types(first, second):
    """Column types from several exports of one table: numeric beats empty, a numeric/text conflict becomes text and is reported."""
    merged = dict(first)
    conflicts = []
    for key, kind in second.items():
        have = merged.get(key, 'empty')
        if have == 'empty':
            merged[key] = kind
        elif kind != 'empty' and kind != have:
            merged[key] = 'text'
            conflicts.append(key)
    return merged, conflicts


def seed(files):
    """Build a registry from real exports: {table_id: path or [paths]}, e.g. the same table from different seasons. All files of a
    table must share one column layout. Only used to add a new table or refresh the config."""
    tables = {}
    for table_id, paths in files.items():
        meta = TABLES[table_id]
        paths = paths if isinstance(paths, (list, tuple)) else [paths]
        parsed, types = None, {}
        for path in paths:
            current = parse_export(Path(path).read_bytes())
            if parsed is not None and current['columns'] != parsed['columns']:
                raise ValueError(f'{table_id}: {Path(path).name} has a different column layout than the other sample files')
            parsed = current
            types, conflicts = merge_types(types, column_types(current))
            if conflicts:
                raise ValueError(f'{table_id}: numeric/text conflict across samples in {conflicts[:3]}')
        tables[table_id] = {
            'id': table_id, 'label': meta['label'], 'level': meta['level'], 'side': meta['side'],
            'forward_looking': bool(meta.get('forward_looking')), 'weekly_expected': meta.get('weekly_expected', True),
            'description': meta['description'], **({'granularity': meta['granularity']} if meta.get('granularity') else {}),
            'filename_hints': meta['hints'], 'signature': signature(parsed['columns']),
            'columns': [{'key': key, 'type': types[key]} for key in parsed['columns']],
            # vendor glossary text is deliberately not stored in the repo (licensed); it stays in the archived raw files
        }
    return {'version': 1, 'source': 'Fantasy Points Data Suite', 'tables': tables}


def seed_weekly(registry, files):
    """Add (or refresh) only the by-game tables of an existing registry. ``files``: {weekly_table_id: [paths]}. Cumulative tables are untouched."""
    added = seed(files)['tables']
    return {**registry, 'tables': {**registry['tables'], **added}}


def load(path=REGISTRY_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _drift(table, parsed, types):
    expected = [c['key'] for c in table['columns']]
    expected_types = {c['key']: c['type'] for c in table['columns']}
    missing = [key for key in expected if key not in parsed['columns']]
    new = [key for key in parsed['columns'] if key not in expected_types]
    renames = []
    for key in list(missing):
        match = difflib.get_close_matches(key, new, n=1, cutoff=0.7)
        if match:
            renames.append({'from': key, 'to': match[0]})
    changed = [{'column': key, 'was': expected_types[key], 'now': types[key]} for key in parsed['columns']
               if key in expected_types and 'empty' not in (types[key], expected_types[key]) and types[key] != expected_types[key]]
    reordered = not missing and not new and parsed['columns'] != expected
    return {'missing': missing, 'new': new, 'possible_renames': renames, 'type_changes': changed, 'reordered': reordered}


def classify(registry, filename, parsed):
    """Return {status, table_id, drift}. status: known | drift | unknown."""
    types = column_types(parsed)
    sig = signature(parsed['columns'])
    tables = registry['tables']
    for table in tables.values():
        if table['signature'] == sig:
            drift = _drift(table, parsed, types)
            return {'status': 'drift' if drift['type_changes'] else 'known', 'table_id': table['id'], 'drift': drift, 'types': types}
    keys = set(parsed['columns'])
    stem = filename_stem(filename)
    best, best_score = None, 0.0
    for table in tables.values():
        expected = {c['key'] for c in table['columns']}
        score = len(keys & expected) / max(1, len(keys | expected))
        if stem in table['filename_hints']:
            score += 0.25
        if score > best_score:
            best, best_score = table, score
    if best is not None and best_score >= 0.5:
        return {'status': 'drift', 'table_id': best['id'], 'drift': _drift(best, parsed, types), 'types': types, 'match_score': round(best_score, 3)}
    return {'status': 'unknown', 'table_id': None, 'drift': None, 'types': types}


def blocking(drift):
    """Missing columns, suspected renames or a type change stop normalization; added columns alone do not."""
    return bool(drift and (drift['missing'] or drift['type_changes']))
