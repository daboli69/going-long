"""A usable partial feed is publishable; provider health is reported separately."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_nfl_betting as B
import parlay_feed as P


class RefreshBuilderTests(unittest.TestCase):
    def test_partial_nfl_builder_persists_successful_quotes_without_failing_publication(self):
        feed = {'provider': 'parlay', 'generated_at': '2026-10-18T12:42:20Z',
                'refresh_status': 'FALLBACK', 'feed_status': 'FALLBACK',
                'refresh_error': 'derivative board incomplete',
                'source_states': {'props': 'FRESH', 'derivatives': 'DEGRADED', 'odds': 'FRESH'},
                'props': [{'quoteKey': 'synthetic', 'updatedAt': '2026-10-18T12:40:00Z'}], 'games_raw': []}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'nfl_betting.json'
            with patch.object(B, 'OUT', output), patch.object(P, 'fetch_parlay', return_value=feed), \
                    patch.object(B, 'fetch_lines', return_value=[]), patch.object(B, 'build_ratings', return_value={}):
                B.build()
            result = json.loads(output.read_text())
        self.assertEqual(result['props'], feed['props'])
        self.assertEqual(result['refresh_status'], 'FALLBACK')
        self.assertEqual(result['source_states']['derivatives'], 'DEGRADED')
        self.assertEqual(result['generated_at'], feed['generated_at'])


if __name__ == '__main__':
    unittest.main()
