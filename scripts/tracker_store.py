"""Read the segmented public tracker store (see shared/tracker-store.mjs).

``load_tracker(data_dir)`` returns the same object the former single file held:
``{"schema_version": 1, "records": [...], ...summaries}``. It never returns an empty tracker
for a present-but-unusable store; a missing segment or checksum mismatch raises.
"""
import copy
import hashlib
import json
from pathlib import Path

LAYOUT = 'public-tracker-segments-v1'
STORE_DIR = 'public_tracker'
LEGACY_FILE = 'public_tracker.json'


def _expand(value, dictionary):
    if isinstance(value, list):
        return [_expand(v, dictionary) for v in value]
    if isinstance(value, dict):
        if list(value.keys()) == ['$ref']:
            return copy.deepcopy(dictionary[value['$ref']])
        return {k: _expand(v, dictionary) for k, v in value.items()}
    return value


def load_tracker(data_dir):
    data_dir = Path(data_dir)
    manifest_path = data_dir / STORE_DIR / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('layout') != LAYOUT:
            raise ValueError('Unrecognized public tracker manifest layout')
        records = []
        for entry in manifest['segments']:
            raw = (data_dir / STORE_DIR / entry['file']).read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('Tracker segment %s does not match its manifest checksum' % entry['file'])
            segment = json.loads(raw.decode('utf-8'))
            rows = [_expand(r, segment.get('dict', {})) for r in segment['records']]
            if len(rows) != entry['records']:
                raise ValueError('Tracker segment %s has the wrong record count' % entry['file'])
            records.extend(rows)
        if len(records) != manifest['total_records']:
            raise ValueError('Tracker record count does not match the manifest')
        return {key: (records if key == 'records' else manifest['summary'][key]) for key in manifest['top_level_keys']}
    legacy = json.loads((data_dir / LEGACY_FILE).read_text(encoding='utf-8'))
    if legacy.get('schema_version') == 1 and isinstance(legacy.get('records'), list):
        return legacy
    raise ValueError('The public tracker moved to %s/manifest.json but that manifest is missing' % STORE_DIR)
