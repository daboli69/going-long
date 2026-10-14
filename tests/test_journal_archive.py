import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('journal_archive', Path(__file__).parents[1] / 'scripts/journal_archive.py')
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)
OWNER = '11111111-1111-1111-1111-111111111111'


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root / 'backup.gz'; self.out = self.root / 'private' / 'archive'

    def make(self, count=3, duplicate=False, end=True):
        lines = []
        for i in range(count):
            identity = hashlib.sha256(str(0 if duplicate else i).encode()).hexdigest()
            body = json.dumps({'name': 'Jos\u00e9', 'text': '\t\\\n', 'prediction_id': str(i)}, ensure_ascii=False)
            body = body.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')
            lines.append(f'{identity}\t{OWNER}\tprediction\t2026-09-12 12:00:00+00\t2026-09-12 12:01:00+00\t{body}\n'.encode())
        with gzip.open(self.source, 'wb') as f:
            f.write(archive.HEADER + b'\n' + b''.join(lines) + (b'\\.\n' if end else b''))
        return lines

    def test_roundtrip_preserves_exact_original_bytes_and_never_overwrites(self):
        lines = self.make(); receipt = archive.build(self.source, self.out)
        self.assertEqual(receipt['rows'], 3); self.assertTrue(receipt['verified'])
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(gzip.decompress((self.out / manifest['shards'][0]['path']).read_bytes()), b''.join(lines))
        self.assertEqual(archive.verify(self.source, self.out), receipt)
        with self.assertRaisesRegex(ValueError, 'already exists'): archive.build(self.source, self.out)

    def test_duplicate_source_id_cannot_be_promoted(self):
        self.make(duplicate=True)
        with self.assertRaises(Exception): archive.build(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_incomplete_source_cannot_be_promoted(self):
        self.make(end=False)
        with self.assertRaisesRegex(ValueError, 'Incomplete'): archive.build(self.source, self.out)
        self.assertFalse(self.out.exists())

    def test_missing_or_corrupt_shard_fails_verification(self):
        self.make(); archive.build(self.source, self.out)
        manifest = json.loads((self.out / 'manifest.json').read_text()); shard = self.out / manifest['shards'][0]['path']
        shard.write_bytes(shard.read_bytes()[:-5])
        with self.assertRaisesRegex(ValueError, 'checksum'): archive.verify(self.source, self.out)

    def test_owner_manifest_cannot_silently_omit_history(self):
        self.make(); archive.build(self.source, self.out)
        p = self.out / OWNER / 'manifest.json'; m = json.loads(p.read_text()); m['shards'] = []; m['rows'] = 0; p.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'Owner manifest'): archive.verify(self.source, self.out)

    def test_byte_escapes_are_utf8_not_unicode_escape(self):
        self.assertEqual(archive.unescape(b'Jos\\303\\251'), 'Jos\u00e9')
        self.assertEqual(archive.unescape(b'a\\tb\\n\\\\'), 'a\tb\n\\')

    def test_public_output_forbidden(self):
        self.make()
        with self.assertRaisesRegex(ValueError, 'private|public/build'): archive.build(self.source, self.root / 'data' / 'archive')

    def test_nested_private_name_cannot_escape_public_build_guard(self):
        for name in ['data/private', 'dist/private', 'shared/private', 'apps/yard/private', 'public/private']:
            with self.assertRaisesRegex(ValueError, 'public/build'):
                archive.private_destination(self.root / name)
        fake_repo = self.root / 'repo'; (fake_repo / '.git').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'ignored private root'):
            archive.private_destination(fake_repo / 'other/private/archive')
        self.assertEqual(archive.private_destination(fake_repo / '.cache/archive'), fake_repo / '.cache/archive')

    def test_shard_rotation(self):
        self.make(); before = archive.MAX_RAW
        try:
            archive.MAX_RAW = 300
            receipt = archive.build(self.source, self.out)
            self.assertEqual(receipt['shards'], 3)
        finally: archive.MAX_RAW = before

    def test_compact_preserves_nonjournal_sql_and_references(self):
        lines = self.make()
        # Old predictions referenced by bets must remain relational despite cutoff.
        with gzip.open(self.source, 'ab') as f:
            f.write(b'-- Preserve every non-journal byte, including other tables.\n')
            f.write(b'COPY public.placed_bets (id, prediction_id) FROM stdin;\n')
            f.write(b'bet\t' + hashlib.sha256(b'0').hexdigest().encode() + b'\n\\.\n')
        archive.build(self.source, self.out)
        output = self.root / 'private' / 'compact.gz'
        result = archive.compact(self.source, self.out, output, '2026-10-01T00:00:00+00:00')
        self.assertEqual((result['retained_relational_rows'], result['archive_only_rows']), (1, 2))
        self.assertEqual([line for line, _ in archive.source_rows(output)], lines[:1])
        with gzip.open(self.source, 'rb') as f: original = f.read()
        with gzip.open(output, 'rb') as f: candidate = f.read()
        self.assertEqual(original.replace(lines[1], b'').replace(lines[2], b''), candidate)

    def test_compact_missing_bet_reference_fails_without_promoting(self):
        self.make()
        with gzip.open(self.source, 'ab') as f:
            f.write(b'COPY public.placed_bets (prediction_id) FROM stdin;\n' + b'f' * 64 + b'\n\\.\n')
        archive.build(self.source, self.out)
        output = self.root / 'private' / 'compact.gz'
        with self.assertRaisesRegex(ValueError, 'bet reference'):
            archive.compact(self.source, self.out, output, '2026-10-01T00:00:00+00:00')
        self.assertFalse(output.exists())

    def test_private_bootstrap_preserves_auth_json_and_guards_empty_target(self):
        self.make()
        value = json.dumps({'name': "O'Neal", 'nested': {'value': 2}})
        with gzip.open(self.source, 'ab') as f:
            f.write(b'CREATE TABLE auth.users (\n id uuid,\n raw_user_meta_data jsonb\n);\n')
            f.write(b'COPY auth.users (id, raw_user_meta_data) FROM stdin;\n')
            f.write((OWNER + '\t' + value + '\n\\.\n').encode())
        archive.build(self.source, self.out)
        output = self.root / 'private' / 'setup.sql'; result = archive.bootstrap(self.source, self.out, output)
        self.assertEqual(result['auth_rows']['auth.users'], 1)
        sql = output.read_text(encoding='utf8')
        self.assertIn('New empty recovery target required', sql)
        self.assertIn("O''Neal", sql)
        self.assertIn('"nested": {"value": 2}', sql)
        self.assertIn('set local standard_conforming_strings=on', sql)
        self.assertNotIn('truncate ', sql.lower())

    def test_bootstrap_refuses_unsupported_nonempty_feature_tables(self):
        self.make()
        with gzip.open(self.source, 'ab') as f:
            f.write(b'COPY auth.mfa_factors (id) FROM stdin;\nfactor\n\\.\n')
        archive.build(self.source, self.out)
        output = self.root / 'private' / 'setup.sql'
        with self.assertRaisesRegex(ValueError, 'Unsupported nonempty'):
            archive.bootstrap(self.source, self.out, output)
        self.assertFalse(output.exists())

    def test_nonjournal_copy_terminator_is_required(self):
        self.make()
        with gzip.open(self.source, 'ab') as f:
            f.write(b'COPY auth.users (id) FROM stdin;\n' + OWNER.encode() + b'\n')
        archive.build(self.source, self.out)
        with self.assertRaisesRegex(ValueError, 'Incomplete recovery COPY'):
            archive.bootstrap(self.source, self.out, self.root / 'private/setup.sql')
        # Fresh source/archive, with a truncated placed-bet section instead.
        self.make()
        with gzip.open(self.source, 'ab') as f:
            f.write(b'COPY public.placed_bets (prediction_id) FROM stdin;\n')
        second = self.root / 'private/second'; archive.build(self.source, second)
        with self.assertRaisesRegex(ValueError, 'Incomplete placed bet COPY'):
            archive.compact(self.source, second, self.root / 'private/compact.gz', '2026-10-01T00:00:00Z')
