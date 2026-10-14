"""Offline, lossless market journal archive. Never connects to a database or deletes rows.

The original PostgreSQL COPY bytes are retained, including received_at and JSON text.
Output is private; upload/cutover requires a separately verified recovery procedure.
"""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import uuid

COLUMNS = ['id', 'owner_id', 'kind', 'observed_at', 'received_at', 'payload']
KINDS = {'quote', 'prediction', 'settlement', 'closing', 'reference', 'run', 'notification', 'arbitrage', 'inactive_report'}
MAX_RAW = 8 * 1024 * 1024
HEADER = b'COPY public.market_journal (id, owner_id, kind, observed_at, received_at, payload) FROM stdin;'


def private_destination(path):
    path = Path(path).resolve()
    parts = {p.lower() for p in path.parts}
    if parts & {'data', 'dist', 'public', 'shared', 'apps'}:
        raise ValueError('Recovery output must not enter a public/build tree')
    if not parts & {'private', '.cache', 'fantasypoints'}:
        raise ValueError('Choose a private, .cache or FantasyPoints destination')
    # Within any Git checkout, a nested directory named "private" is insufficient.
    for parent in path.parents:
        if (parent / '.git').exists():
            if not any(path.is_relative_to(parent / name) for name in ('private', '.cache', 'FantasyPoints')):
                raise ValueError('Use an ignored private root of the checkout')
            break
    return path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def unescape(field):
    if field == b'\\N':
        raise ValueError('Unexpected NULL journal column')
    def replace(m):
        text = m[1]
        if text[:1] == b'x':
            return bytes([int(text[1:], 16)])
        if text[:1] in b'01234567':
            return bytes([int(text, 8)])
        return {b'b': b'\b', b'f': b'\f', b'n': b'\n', b'r': b'\r', b't': b'\t', b'v': b'\v'}.get(text, text)
    return re.sub(rb'\\([0-7]{1,3}|x[0-9a-fA-F]{1,2}|.)', replace, field).decode('utf-8')


def row(line):
    fields = line.removesuffix(b'\n').removesuffix(b'\r').split(b'\t')
    if len(fields) != 6 or not line.endswith(b'\n'):
        raise ValueError('Malformed COPY row')
    values = dict(zip(COLUMNS, map(unescape, fields)))
    if not re.fullmatch('[0-9a-f]{64}', values['id']) or str(uuid.UUID(values['owner_id'])) != values['owner_id'] or values['kind'] not in KINDS:
        raise ValueError('Invalid journal identity')
    for key in ('observed_at', 'received_at'):
        if datetime.fromisoformat(values[key]).utcoffset() is None:
            raise ValueError('Journal timestamp lacks offset')
    if not isinstance(json.loads(values['payload']), dict):
        raise ValueError('Journal payload must be an object')
    return values


def source_rows(source):
    found = False
    with gzip.open(source, 'rb') as f:
        for line in f:
            if line.rstrip(b'\r\n') == HEADER:
                if found:
                    raise ValueError('Duplicate journal COPY section')
                found = True
                for line in f:
                    if line.rstrip(b'\r\n') == b'\\.':
                        break
                    yield line, row(line)
                else:
                    raise ValueError('Incomplete journal COPY section')
        # Consume the whole gzip, including its CRC and trailer, before success.
    if not found:
        raise ValueError('Expected journal COPY columns not found')


def safe_path(root, name):
    if not isinstance(name, str) or '\\' in name or '..' in name.split('/'):
        raise ValueError('Unsafe archive path')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError('Unsafe archive path')
    return path


def verify(source, root):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'going-journal-copy-v1' or manifest.get('columns') != COLUMNS or manifest.get('source_sha256') != sha(source):
        raise ValueError('Archive source or schema mismatch')
    for owner in {p['owner_id'] for p in manifest['shards']}:
        subset = [p for p in manifest['shards'] if p['owner_id'] == owner]
        expected_owner = dict(manifest, rows=sum(p['rows'] for p in subset), shards=subset)
        owner_path = safe_path(root, f'{owner}/manifest.json')
        if json.loads(owner_path.read_text(encoding='utf-8')) != expected_owner:
            raise ValueError('Owner manifest does not match complete verified archive')
    # Disk-backed comparison avoids retaining a million private rows in memory.
    with tempfile.TemporaryDirectory(prefix='going-journal-verify-') as tmp:
        db = sqlite3.connect(str(Path(tmp) / 'identity.sqlite'))
        try:
            db.execute('CREATE TABLE identity(id TEXT PRIMARY KEY, hash TEXT NOT NULL, seen INTEGER DEFAULT 0)')
            expected = 0
            for line, value in source_rows(source):
                db.execute('INSERT INTO identity(id,hash) VALUES(?,?)', (value['id'], hashlib.sha256(line).hexdigest()))
                expected += 1
            db.commit()
            actual = 0
            paths = set()
            for part in manifest['shards']:
                if part['path'] in paths:
                    raise ValueError('Duplicate archive shard')
                paths.add(part['path'])
                path = safe_path(root, part['path'])
                if path.stat().st_size != part['gzip_bytes'] or sha(path) != part['gzip_sha256']:
                    raise ValueError('Compressed shard checksum mismatch')
                digest = hashlib.sha256(); count = size = 0; clocks = []
                with gzip.open(path, 'rb') as f:
                    for line in f:
                        value = row(line)
                        if value['owner_id'] != part['owner_id'] or value['kind'] != part['kind']:
                            raise ValueError('Shard owner/kind mismatch')
                        clock = datetime.fromisoformat(value['observed_at']).timestamp(); clocks.append(clock)
                        changed = db.execute('UPDATE identity SET seen=1 WHERE id=? AND hash=? AND seen=0', (value['id'], hashlib.sha256(line).hexdigest())).rowcount
                        if changed != 1:
                            raise ValueError('Missing, altered or duplicate archived record')
                        digest.update(line); size += len(line); count += 1
                if not count or (count, size, digest.hexdigest(), min(clocks), max(clocks)) != (part['rows'], part['raw_bytes'], part['raw_sha256'], part['min_observed'], part['max_observed']):
                    raise ValueError('Shard manifest metadata mismatch')
                actual += count
            if actual != expected or actual != manifest['rows'] or db.execute('SELECT count(*) FROM identity WHERE seen=0').fetchone()[0]:
                raise ValueError('Archive incomplete')
            return {'verified': True, 'rows': actual, 'shards': len(paths), 'gzip_bytes': sum(p['gzip_bytes'] for p in manifest['shards']), 'source_sha256': manifest['source_sha256']}
        finally:
            db.close()


def build(source, output):
    source = Path(source).resolve(); output = private_destination(output)
    if output.exists():
        raise ValueError('Archive destination already exists; refusing overwrite')
    # Require an explicitly private/ignored destination, not a public build/data tree.
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=output.name + '-incomplete-', dir=output.parent))
    manifest = {'schema': 'going-journal-copy-v1', 'columns': COLUMNS, 'source_sha256': sha(source), 'rows': 0, 'shards': []}
    opened = {}; counters = Counter()

    def finish(key):
        item = opened.pop(key); item['stream'].close()
        part = item['part']; path = staging / part['path']
        part.update(gzip_bytes=path.stat().st_size, gzip_sha256=sha(path), raw_sha256=item['digest'].hexdigest())
        manifest['shards'].append(part)

    try:
        for line, value in source_rows(source):
            if len(line) > MAX_RAW:
                raise ValueError('Journal record exceeds bounded shard size')
            key = (value['owner_id'], value['kind'], value['observed_at'][:7])
            if key in opened and opened[key]['part']['raw_bytes'] + len(line) > MAX_RAW:
                finish(key)
            if key not in opened:
                name = f'{key[0]}/shards/{key[1]}-{key[2]}-{counters[key]:05d}.copy.gz'; counters[key] += 1
                path = safe_path(staging, name); path.parent.mkdir(parents=True, exist_ok=True)
                part = {'path': name, 'owner_id': key[0], 'kind': key[1], 'rows': 0, 'raw_bytes': 0, 'min_observed': float('inf'), 'max_observed': float('-inf')}
                opened[key] = {'stream': gzip.GzipFile(filename=str(path), mode='wb', mtime=0), 'part': part, 'digest': hashlib.sha256()}
            item = opened[key]; part = item['part']; item['stream'].write(line); item['digest'].update(line)
            part['rows'] += 1; part['raw_bytes'] += len(line)
            clock = datetime.fromisoformat(value['observed_at']).timestamp()
            part['min_observed'] = min(clock, part['min_observed']); part['max_observed'] = max(clock, part['max_observed'])
            manifest['rows'] += 1
        for key in list(opened):
            finish(key)
        manifest['shards'].sort(key=lambda p: p['path'])
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        # Per-owner manifests are the only manifests intended for private hosted reads.
        for owner in {p['owner_id'] for p in manifest['shards']}:
            subset = [p for p in manifest['shards'] if p['owner_id'] == owner]
            (staging / owner / 'manifest.json').write_text(json.dumps(dict(manifest, rows=sum(p['rows'] for p in subset), shards=subset), indent=2), encoding='utf-8')
        receipt = verify(source, staging)
        (staging / 'verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        staging.rename(output)
        return receipt
    finally:
        for item in opened.values():
            item['stream'].close()


def compact(source, root, output, cutoff):
    """Prepare a PRIVATE recovery backup, never modify a live database.

    All non-journal SQL is copied unchanged. Archived historical journal rows are
    omitted only from this new restore candidate; the verified archive retains them.
    Recent rows and every prediction referenced by a placed bet stay relational.
    """
    cutoff_time = datetime.fromisoformat(cutoff)
    if cutoff_time.utcoffset() is None:
        raise ValueError('Compaction cutoff requires an offset')
    output = private_destination(output)
    if output.exists():
        raise ValueError('Choose a new private recovery backup path')
    verified = verify(source, root)
    referenced = set()
    with gzip.open(source, 'rb') as f:
        for line in f:
            match = re.match(rb'^COPY public\.placed_bets \((.*?)\) FROM stdin;', line)
            if not match:
                continue
            columns = [v.strip().decode() for v in match[1].split(b',')]
            if 'prediction_id' not in columns:
                raise ValueError('Unknown placed bet schema')
            index = columns.index('prediction_id')
            for line in f:
                if line.rstrip(b'\r\n') == b'\\.': break
                fields = line.rstrip(b'\r\n').split(b'\t')
                if len(fields) != len(columns): raise ValueError('Malformed placed bet row')
                referenced.add(unescape(fields[index]))
            else:
                raise ValueError('Incomplete placed bet COPY section')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.incomplete')
    if temporary.exists(): raise ValueError('Incomplete candidate already exists')
    retained = 0; archived_only = 0; matched_refs = set(); active = False
    with gzip.open(source, 'rb') as src, temporary.open('xb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as dst:
            for line in src:
                if line.rstrip(b'\r\n') == HEADER:
                    active = True; dst.write(line); continue
                if active:
                    if line.rstrip(b'\r\n') == b'\\.':
                        active = False; dst.write(line); continue
                    value = row(line)
                    is_ref = value['id'] in referenced
                    if is_ref:
                        if value['kind'] != 'prediction': raise ValueError('Bet references a non-prediction')
                        matched_refs.add(value['id'])
                    if is_ref or datetime.fromisoformat(value['observed_at']) >= cutoff_time:
                        dst.write(line); retained += 1
                    else: archived_only += 1
                else: dst.write(line)
    if referenced != matched_refs or retained + archived_only != verified['rows']:
        raise ValueError('Recovery candidate lost a bet reference or journal coverage')
    # Check the candidate gzip and retained COPY section independently before rename.
    if sum(1 for _ in source_rows(temporary)) != retained:
        raise ValueError('Recovery candidate row count mismatch')
    temporary.rename(output)
    return {'verified_archive_rows': verified['rows'], 'retained_relational_rows': retained,
            'archive_only_rows': archived_only, 'bet_prediction_references': len(referenced),
            'cutoff': cutoff, 'candidate_gzip_bytes': output.stat().st_size,
            'candidate_sha256': sha(output), 'source_sha256': verified['source_sha256'],
            'production_changed': False}


def bootstrap(source, root, output):
    """Private SQL Editor recovery script for an EMPTY replacement project only.

    Restores original auth identities/session metadata; never resets passwords. The
    credential-bearing script must be reviewed/submitted by the owner in the UI.
    Managed platform migration tables and roles are deliberately not overwritten.
    """
    verify(source, root)
    output = private_destination(output)
    if output.exists():
        raise ValueError('Choose a new private SQL script path')
    tables = ['auth.users', 'auth.identities', 'auth.sessions', 'auth.refresh_tokens', 'auth.mfa_amr_claims']
    platform_history = {'auth.schema_migrations', 'storage.migrations', 'realtime.schema_migrations'}
    records = {table: [] for table in tables}; json_columns = set(); table = None
    with gzip.open(source, 'rt', encoding='utf-8') as src:
        for line in src:
            create = re.match(r'^CREATE TABLE ([\w.]+) \(', line)
            if create: table = create[1]
            if table and (column := re.match(r'^\s+(\w+) (jsonb?)\b', line)):
                json_columns.add((table, column[1]))
            if line.startswith(');'): table = None
            match = re.match(r'^COPY ([\w.]+) \((.*?)\) FROM stdin;', line)
            if not match: continue
            name = match[1]; columns = [v.strip() for v in match[2].split(',')]
            if not all(re.fullmatch(r'[a-z_]+', c) for c in columns): raise ValueError('Unsafe auth column')
            for line in src:
                if line.rstrip('\r\n') == r'\.': break
                if name not in records:
                    if name == 'public.market_journal' or name in platform_history: continue
                    raise ValueError('Unsupported nonempty recovery table; explicit feature-preserving restore required')
                fields = line.rstrip('\r\n').split('\t')
                if len(fields) != len(columns): raise ValueError('Malformed auth COPY')
                value = {}
                for key, text in zip(columns, fields):
                    decoded = None if text == r'\N' else unescape(text.encode('utf-8'))
                    value[key] = json.loads(decoded) if decoded is not None and (name, key) in json_columns else decoded
                records[name].append(value)
            else:
                raise ValueError('Incomplete recovery COPY section')
    # This version targets the inspected backup, with no recent public journal/bets.
    # Never silently discard a hot/accepted record from a different backup.
    with gzip.open(source, 'rb') as src:
        active_bets = False
        for line in src:
            if line.startswith(b'COPY public.placed_bets '): active_bets = True; continue
            if active_bets:
                if line.rstrip(b'\r\n') == b'\\.': active_bets = False
                else: raise ValueError('Bootstrap with placed bets requires explicit relational restore')
    sql = ['-- PRIVATE: contains existing authentication records. Do not commit or share.',
           '-- Run ONLY in the new empty GOING Recovery project; original project is untouched.',
           'begin;', 'set local standard_conforming_strings=on;',
           "do $$ begin if to_regclass('public.market_journal') is not null or exists(select 1 from auth.users) then raise exception 'New empty recovery target required'; end if; end $$;"]
    for name in tables:
        if not records[name]: continue
        columns = list(records[name][0])
        if any(list(r) != columns for r in records[name]): raise ValueError('Auth column shape changed')
        for column in columns:
            sql.append(f"do $$ begin if not exists(select 1 from information_schema.columns where table_schema='auth' and table_name='{name.split('.')[1]}' and column_name='{column}') then raise exception 'Auth schema differs; stop restoration'; end if; end $$;")
        data = json.dumps(records[name], ensure_ascii=True).replace("'", "''")
        names = ','.join('"' + c + '"' for c in columns)
        sql.append(f"insert into {name} ({names}) select {names} from json_populate_recordset(null::{name},'{data}'::json);")
    sql.append("select setval(pg_get_serial_sequence('auth.refresh_tokens','id'),greatest(coalesce((select max(id) from auth.refresh_tokens),1),1),true);")
    migrations = Path(__file__).resolve().parents[1] / 'supabase/migrations'
    for name in ['20260911_market_journal.sql', '20260912_validation_queries.sql', '20261013_private_fp_inputs.sql', '20261014_private_journal_archive.sql']:
        sql.extend(line for line in (migrations / name).read_text(encoding='utf-8').splitlines() if line.strip().lower() not in {'begin;', 'commit;'})
    sql.extend(['commit;', "select pg_database_size(current_database()) as database_bytes,(select count(*) from auth.users) as restored_accounts,(select count(*) from public.market_journal) as relational_journal_rows;"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f: f.write('\n'.join(sql) + '\n')
    return {'private_script_created': True, 'auth_rows': {k: len(v) for k, v in records.items()},
            'script_sha256': sha(output), 'production_changed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'verify', 'compact', 'bootstrap'])
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--cutoff')
    args = parser.parse_args()
    # Errors contain no payload values. Incomplete output is retained, never promoted.
    if args.command == 'compact' and (not args.output or not args.cutoff):
        parser.error('compact requires --output and --cutoff')
    if args.command == 'bootstrap' and not args.output: parser.error('bootstrap requires --output')
    result = build(args.backup, args.archive) if args.command == 'build' else compact(args.backup, args.archive, args.output, args.cutoff) if args.command == 'compact' else bootstrap(args.backup, args.archive, args.output) if args.command == 'bootstrap' else verify(args.backup, args.archive)
    print(json.dumps(result))
