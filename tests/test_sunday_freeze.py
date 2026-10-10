"""Throwaway-only freeze tests; production files and clocks are never mutated."""
import datetime
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sunday_freeze as freeze


class FreezeTests(unittest.TestCase):
    def test_concurrent_writers_publish_one_complete_immutable_document(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'freezes' / 'fixture.json'
            with ThreadPoolExecutor(max_workers=6) as workers:
                results = list(workers.map(lambda i: freeze.write_once(path, {'writer': i, 'rows': list(range(100))}), range(6)))
            self.assertEqual(sum(results), 1)
            before = path.read_bytes()
            self.assertIn(json.loads(before)['writer'], range(6))
            self.assertFalse(freeze.write_once(path, {'replacement': True}))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_serialization_failure_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixture.json'
            with self.assertRaises(ValueError):
                freeze.write_once(path, {'bad': float('nan')})
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_mixed_offset_kickoffs_do_not_allow_a_postgame_freeze(self):
        class Clock(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 11, 12, 30, tzinfo=datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'data').mkdir()
            (root / 'data/nfl_betting.json').write_text(json.dumps({'games_raw': [
                {'commence_time': '2026-10-11T09:30:00-04:00'},
                {'commence_time': '2026-10-11T12:00:00Z'}]}))
            with patch.object(freeze, 'REPO', root), patch.object(freeze.datetime, 'datetime', Clock):
                freeze.main('2026-10-11')
            self.assertFalse((root / 'data/freezes/2026-10-11.json').exists())

    def test_eastern_sunday_includes_utc_monday_and_records_roster_receipt(self):
        class Clock(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 11, 8, 0, tzinfo=datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for sub in ('data', 'config', 'research/today-ranking'):
                (root / sub).mkdir(parents=True)
            docs = {'data/nfl_betting.json': {'games_raw': [{'commence_time': '2026-10-12T00:20:00Z'}]},
                    'data/history.json': {'betting': {'profiles': {}}}, 'data/nfl_roster.json': {'generated_at': '2026-10-11T07:00:00Z'},
                    'config/champion_policy.json': {'active': True}, 'config/calibration_policy.json': {'version': 'fixture'},
                    'research/today-ranking/experiment-v3.json': {'id': 'fixture'}}
            for file, doc in docs.items():
                (root / file).write_text(json.dumps(doc))
            with patch.object(freeze, 'REPO', root), patch.object(freeze.datetime, 'datetime', Clock), \
                 patch.object(freeze.eligibility, 'freshness', return_value={'ok': False, 'reason': 'isolated fixture'}), \
                 patch.object(freeze.subprocess, 'check_output', return_value=b'offline-fixture'):
                freeze.main('2026-10-11')
                path = root / 'data/freezes/2026-10-11.json'; before = path.read_bytes()
                freeze.main('2026-10-11')
            doc = json.loads(before)
            self.assertEqual(doc['first_kickoff'], '2026-10-12T00:20:00Z')
            self.assertEqual(doc['data']['nfl_roster.json']['sha256'], freeze.sha(root / 'data/nfl_roster.json'))
            self.assertFalse(doc['availability']['ok'])
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
