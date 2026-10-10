"""Exact source provenance and fail-closed behavior, entirely mocked/offline."""
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import availability_source as S
import polars as pl

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)


class SourceTests(unittest.TestCase):
    def response(self, stamp):
        content = io.BytesIO(); pl.DataFrame({'gsis_id': ['synthetic-player'], 'week': [5], 'season_type': ['REG'], 'date_modified': ['2026-10-10T10:00:00Z']}).write_parquet(content)
        return Mock(headers={'Last-Modified': stamp} if stamp else {}, content=content.getvalue())

    def test_source_clock_and_hash_belong_to_exact_bytes(self):
        response = self.response('Sat, 10 Oct 2026 10:00:00 GMT')
        with patch.object(S.requests, 'get', return_value=response):
            rows, source = S.load_source('injuries', 2026, NOW)
        self.assertEqual(rows[0]['gsis_id'], 'synthetic-player')
        self.assertEqual(source['content_at'], '2026-10-10T10:00:00+00:00')
        self.assertEqual(source['sha256'], S.hashlib.sha256(response.content).hexdigest())

    def test_aware_parquet_datetimes_normalize_and_unknown_timezone_stays_unknown(self):
        self.assertEqual(S.source_stamp(NOW), '2026-10-10T12:00:00+00:00')
        self.assertIsNone(S.source_stamp(NOW.replace(tzinfo=None)))
        self.assertIsNone(S.source_stamp('2026-10-10 12:00:00'))

    def test_new_upload_with_old_current_week_reports_is_not_fresh(self):
        response = self.response('Sat, 10 Oct 2026 10:00:00 GMT')
        content = io.BytesIO(); pl.DataFrame({'week': [5], 'season_type': ['REG'], 'date_modified': ['2026-10-08T10:00:00Z']}).write_parquet(content)
        response.content = content.getvalue()
        with patch.object(S.requests, 'get', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'report content stale'):
                S.load_source('injuries', 2026, NOW)

    def test_missing_stale_future_source_clocks_fail_before_publication(self):
        for stamp in (None, 'Thu, 08 Oct 2026 10:00:00 GMT', 'Sun, 11 Oct 2026 10:00:00 GMT'):
            with self.subTest(stamp=stamp), patch.object(S.requests, 'get', return_value=self.response(stamp)):
                with self.assertRaises(RuntimeError): S.load_source('rosters', 2026, NOW)

    def test_newer_production_content_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.json'
            path.write_text(json.dumps({'source_content_at': '2026-10-10T11:00:00Z'}))
            before = path.read_bytes()
            with patch.object(S, 'datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                with self.assertRaisesRegex(RuntimeError, 'Newer production'):
                    S.preserve_newer(path, {'source_content_at': '2026-10-10T10:00:00Z'})
            self.assertEqual(path.read_bytes(), before)

    def test_identical_reuploaded_bytes_do_not_reage_old_content(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.json'
            old = {'source_content_at': '2026-10-08T10:00:00Z', 'sources': {'injuries': {'sha256': 'same', 'content_at': '2026-10-08T10:00:00Z'}}}
            path.write_text(json.dumps(old))
            payload = {'source_content_at': '2026-10-10T10:00:00Z', 'sources': {'injuries': {'sha256': 'same'}}}
            with patch.object(S, 'datetime', wraps=datetime) as clock:
                clock.now.return_value = NOW
                with self.assertRaisesRegex(RuntimeError, 'stale'):
                    S.preserve_newer(path, payload)
            self.assertEqual(payload['source_content_at'], old['source_content_at'])


if __name__ == '__main__': unittest.main()
