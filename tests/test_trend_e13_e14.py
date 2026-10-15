"""E13/E14 guard: specs stay frozen against the ledger, are wired into the CLI, and cannot read same-season features."""
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))

from trend_research import data, experiments13, ledger  # noqa: E402


class E13E14Tests(unittest.TestCase):
    def test_specs_match_registered_hashes(self):
        book = json.loads((REPO / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
        for exp_id, spec in experiments13.SPECS.items():
            self.assertEqual(book['experiments'][exp_id]['spec_sha256'], ledger.spec_hash(spec), exp_id)

    def test_ledger_holds_aggregates_only(self):
        book = json.loads((REPO / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))
        text = json.dumps({k: book['experiments'][k]['result'] for k in experiments13.SPECS})
        self.assertNotIn('player_id', text)
        self.assertNotIn('00-00', text)  # gsis id prefix

    def test_runners_cover_specs_and_cli_wiring(self):
        self.assertEqual(set(experiments13.SPECS), set(experiments13.RUNNERS))
        self.assertIn('experiments13', (REPO / 'scripts' / 'trend_research.py').read_text(encoding='utf-8'))

    def test_same_season_features_are_refused(self):
        with self.assertRaises(data.LeakageError):
            data.assert_no_same_season(2025, 2025)

    def test_primary_outcomes_declared(self):
        for spec in experiments13.SPECS.values():
            self.assertTrue(spec['primary_outcome'])
            self.assertIn('leakage', spec)


if __name__ == '__main__':
    unittest.main()
