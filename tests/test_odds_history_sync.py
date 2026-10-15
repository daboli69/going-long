import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from odds_history import Archive
from sync_odds_history import stage, sync, ENDPOINT
from test_odds_history import BODY


class HistorySyncTests(unittest.TestCase):
    def fixture(self, root):
        a = Archive(root, fetch=Mock(return_value=Mock(status_code=200, json=Mock(return_value=BODY), headers={
            'x-requests-last': '30', 'x-requests-used': '30', 'x-requests-remaining': '19970'})))
        a.request('/v4/historical/sports/americanfootball_nfl/odds', {'date': '2025-10-12T16:00:00Z'}, 30, 'provider-private')
        (Path(root) / 'credential.json').write_text(json.dumps({'api_key': 'never-copy-this'}))
        (Path(root) / 'plan.json').write_text(json.dumps({'cutoff': '2025-10-13T00:00:00Z'}))
        summary = a.status(); summary['acquisition_complete'] = True
        (Path(root) / 'summary.json').write_text(json.dumps(summary))
        return a

    def test_lossless_stage_originals_receipts_and_cutoff_only(self):
        with tempfile.TemporaryDirectory() as root:
            a = self.fixture(root)
            objects, index = stage(root)
            self.assertEqual([o['kind'] for o in objects], ['raw', 'receipts', 'event', 'index'])
            self.assertEqual(index['quotes'], 2)
            for obj in objects:
                raw = obj['path'].read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), obj['sha256'])
                self.assertNotIn(b'never-copy-this', gzip.decompress(raw))
                self.assertNotIn(b'provider-private', gzip.decompress(raw))
            (Path(root) / 'plan.json').write_text(json.dumps({'cutoff': '2025-10-11T00:00:00Z'}))
            self.assertEqual(stage(root)[1]['events'], [])

    def test_failed_or_unfinished_download_cannot_publish(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            p = Path(root) / 'summary.json'; s = json.loads(p.read_text()); s['acquisition_complete'] = False; p.write_text(json.dumps(s))
            with self.assertRaises(ValueError): stage(root)

    def test_verified_idempotent_upload_uses_existing_limited_token_and_fixed_endpoint(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            calls = []
            def post(url, **kw):
                calls.append(kw['json']['kind'])
                self.assertEqual(url, ENDPOINT)
                self.assertFalse(kw['allow_redirects'])
                self.assertEqual(kw['headers']['Authorization'], 'Bearer ' + 't' * 32)
                b = base64.b64decode(kw['json']['gzip'])
                return Mock(status_code=200, json=Mock(return_value={'ok': True, 'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)}))
            self.assertTrue(sync(root, post=post, token='t' * 32)['verified_upload'])
            self.assertEqual(calls[-1], 'index')
            calls.clear(); sync(root, post=post, token='t' * 32)
            self.assertEqual(calls, ['index'])
            self.assertTrue((Path(root) / 'credential.json').exists())

    def test_wrong_ack_preserves_local_archive_and_does_not_publish_index(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            post = Mock(return_value=Mock(status_code=200, json=Mock(return_value={'ok': True, 'sha256': 'wrong'})))
            with self.assertRaises(RuntimeError): sync(root, post=post, token='t' * 32)
            self.assertTrue(all(c.kwargs['json']['kind'] != 'index' for c in post.call_args_list))
            self.assertTrue((Path(root) / 'index.sqlite3').exists())
            self.assertFalse((Path(root) / 'cloud-summary.json').exists())


if __name__ == '__main__': unittest.main()
