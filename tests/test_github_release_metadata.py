import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import github_release_metadata as G


class ReleaseMetadataTests(unittest.TestCase):
    def test_token_is_scoped_to_official_metadata_without_redirects(self):
        response = Mock(status_code=200); response.json.return_value = {'assets': []}
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'fixture-never-persist'}), patch.object(G.requests, 'get', return_value=response) as get:
            self.assertEqual(G.release_metadata('stats_team'), {'assets': []})
            args = get.call_args
            self.assertEqual(args.args[0], 'https://api.github.com/repos/nflverse/nflverse-data/releases/tags/stats_team')
            self.assertEqual(args.kwargs['headers']['Authorization'], 'Bearer fixture-never-persist')
            self.assertFalse(args.kwargs['allow_redirects'])
            with self.assertRaises(ValueError): G.release_metadata('https://other.example')
            self.assertEqual(get.call_count, 1)
            response.status_code = 302
            with self.assertRaisesRegex(RuntimeError, 'redirect'): G.release_metadata('stats_player')

    def test_local_public_mode_never_invents_a_token(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(G.requests, 'get', return_value=Mock(status_code=200)) as get:
            G.release_metadata('stats_player')
            self.assertNotIn('Authorization', get.call_args.kwargs['headers'])


if __name__ == '__main__': unittest.main()
