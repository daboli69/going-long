"""Licensed data stays out of Git without ignoring tracked application code."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ignored(path, ignorecase):
    done = subprocess.run(['git', '-c', f'core.ignorecase={ignorecase}', 'check-ignore', '-q', '--no-index', path], cwd=ROOT)
    return done.returncode == 0


class PrivateDataIgnoreTests(unittest.TestCase):
    def test_licensed_roots_are_ignored_even_on_case_insensitive_checkouts(self):
        for ignorecase in ('false', 'true'):
            for path in ('FantasyPoints/raw/2025/x.csv', 'StatApi/raw/y.json.gz', '.cache/z.json'):
                self.assertTrue(ignored(path, ignorecase), (ignorecase, path))

    def test_tracked_statapi_code_is_never_ignored(self):
        for ignorecase in ('false', 'true'):
            for path in ('scripts/statapi/client.py', 'scripts/statapi/normalize.py', 'docs/STATAPI_ARCHIVE.md'):
                self.assertFalse(ignored(path, ignorecase), (ignorecase, path))
        tracked = subprocess.run(['git', 'ls-files', 'scripts/statapi'], cwd=ROOT, capture_output=True, text=True).stdout.split()
        self.assertTrue(tracked, 'scripts/statapi must remain tracked application code')

    def test_no_licensed_export_or_credential_was_ever_tracked(self):
        names = subprocess.run(['git', 'log', '--all', '--name-only', '--format='], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
        bad = [n for n in set(names) if n.startswith(('FantasyPoints/', 'StatApi/')) or n.endswith('credential.json') or n.endswith('.sqlite3')]
        self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()
