import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_results import assemble


class ResultsTests(unittest.TestCase):
    def test_final_only_and_no_missing_zero(self):
        now = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)
        g = dict(sport='nfl', id='g', home='A', away='B', kickoff='2026-09-10T00:00:00Z', completed=True, homeScore=20, awayScore=10)
        p = {'p': {'games': [{'date': '2026-09-09', 'rec_yds': 0, 'rush_yds': None}, {'date': '2026-09-12', 'rec_yds': 99}]}}
        out = assemble([g, {**g, 'id': 'future', 'kickoff': '2026-09-12T00:00:00Z'}], p, now=now)
        self.assertEqual(list(out['games']), ['nfl|g'])
        self.assertEqual(out['players'], {'p|2026-09-09': {'rec_yds': 0}})
        retained = assemble([], {}, out, now=now)
        self.assertEqual(retained['games'], out['games'])
