import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import refresh_health as H

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
STAMP = '2026-10-10T10:00:00Z'


def fixtures(root):
    docs = {
        'injury_context.json': {'current_players': {}, 'current_reports': {}},
        'nfl_roster.json': {'players': [{'id': t, 'team': t, 'roster_status': 'ACT'} for t in sorted(H.NFL_TEAMS)], 'week': 5},
        'history.json': {'betting': {'schema_version': 1, 'profiles': {}, 'generated_at': STAMP}},
        'results.json': {'schema_version': 1, 'games': {}, 'players': {},
                         'player_source_at': STAMP,
                         'sources': {s: {'status': 'loaded', 'checked_at': STAMP} for s in ('nfl', 'ncaa')}},
        'savant_context.json': {'observed_at': STAMP, 'sources': {'savant_csv': {'status': 'loaded'}}},
        'public_tracker/manifest.json': {'schema_version': 1, 'layout': 'public-tracker-segments-v1', 'segments': []},
    }
    for name in ('nfl_betting.json', 'ncaa_lines.json'):
        docs[name] = {'feed_status': 'FRESH', 'refresh_status': 'FRESH',
                      'source_states': {'odds': 'FRESH', 'props': 'FRESH', 'derivatives': 'FRESH'},
                      'props': [{'updatedAt': STAMP}]}
    for name, doc in docs.items():
        doc['generated_at'] = STAMP
        p = root / 'data' / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc))
    return docs


class RefreshHealthTests(unittest.TestCase):
    def test_success_is_read_only_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixtures(root)
            before = {p: p.read_bytes() for p in (root / 'data').rglob('*.json')}
            report = H.audit(root, NOW, {'validate_models': {'outcome': 'success'}})
            self.assertTrue(report['healthy'], report['issues'])
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            self.assertTrue(all(len(v['sha256']) == 64 for v in report['artifacts'].values()))

    def test_partial_refresh_cannot_be_healthy_despite_recent_generated_at(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            doc = docs['nfl_betting.json']; doc['source_states']['props'] = 'STALE'
            doc['feed_status'] = doc['refresh_status'] = 'FALLBACK'
            doc['props'][0]['updatedAt'] = '2026-10-08T10:00:00Z'
            p = root / 'data/nfl_betting.json'; p.write_text(json.dumps(doc)); before = p.read_bytes()
            report = H.audit(root, NOW)
            self.assertFalse(report['healthy'])
            self.assertIn('nfl_betting.json: props is STALE', report['issues'])
            self.assertEqual(p.read_bytes(), before)

    def test_missing_malformed_stale_availability_and_incomplete_team_pool_fail(self):
        for bad in (None, [], {'generated_at': STAMP}, {'generated_at': STAMP, 'players': []}):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); fixtures(root)
                (root / 'data/nfl_roster.json').write_text(json.dumps(bad))
                self.assertFalse(H.audit(root, NOW)['healthy'])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            docs['injury_context.json']['generated_at'] = '2026-10-08T10:00:00Z'
            (root / 'data/injury_context.json').write_text(json.dumps(docs['injury_context.json']))
            self.assertFalse(H.audit(root, NOW)['healthy'])

    def test_job_failure_model_validation_or_truncated_source_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            for steps in ({'validate_models': 'failure'}, {'validate_models': 'success', 'dfs_team_td': 'failure'}, {}):
                self.assertFalse(H.audit(root, NOW, steps)['healthy'])
            docs['nfl_betting.json']['coverage'] = {'possibly_truncated': True}
            (root / 'data/nfl_betting.json').write_text(json.dumps(docs['nfl_betting.json']))
            self.assertFalse(H.audit(root, NOW)['healthy'])

    def test_actual_source_check_age_matters_even_when_envelope_was_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            docs['results.json']['sources']['nfl']['checked_at'] = '2026-10-08T10:00:00Z'
            (root / 'data/results.json').write_text(json.dumps(docs['results.json']))
            self.assertFalse(H.audit(root, NOW)['healthy'])
            docs['results.json']['sources'] = None
            (root / 'data/results.json').write_text(json.dumps(docs['results.json']))
            self.assertFalse(H.audit(root, NOW)['healthy'])

    def test_workflow_dependency_order_and_failed_validation_publication_guard(self):
        text = (Path(__file__).resolve().parents[1] / '.github/workflows/data.yml').read_text()
        blocks = re.split(r'^      - name: ', text, flags=re.M)[1:]
        by_id = {}
        for i, block in enumerate(blocks):
            match = re.search(r'^        id: (\w+)$', block, flags=re.M)
            if match: by_id[match[1]] = (i, block)
        for target in ('going_score', 'jackpot', 'slate_breaker'):
            for dependency in ('history', 'projections', 'context', 'injury_context', 'roster_public'):
                self.assertLess(by_id[dependency][0], by_id[target][0], (dependency, target))
        for target in ('savant', 'results'):
            self.assertIn('continue-on-error: true', by_id[target][1])
        for block in blocks:
            if 'if: ${{ !cancelled() }}' in block:
                self.assertTrue(block.startswith(('Report source failures\n', 'Preserve refresh diagnostics\n')), block.splitlines()[0])
            if block.startswith('Commit generated snapshots\n') or 'id: freeze\n' in block:
                self.assertIn("steps.validate_models.outcome == 'success'", block)
        report = next(block for block in blocks if block.startswith('Report source failures\n'))
        self.assertIn('toJSON(steps)', report)
        self.assertIn('refresh_health.py', report)
        self.assertNotIn('|| echo', by_id['freeze'][1])
        self.assertIn('exit "$status"', by_id['freeze'][1])

    def test_nested_model_and_player_provenance_cannot_be_reaged(self):
        for name, nested in (('history.json', True), ('results.json', False)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); docs = fixtures(root)
                if nested:
                    docs[name]['betting']['generated_at'] = '2026-10-08T10:00:00Z'
                else:
                    docs[name]['player_source_at'] = '2026-10-08T10:00:00Z'
                (root / 'data' / name).write_text(json.dumps(docs[name]))
                self.assertFalse(H.audit(root, NOW)['healthy'])

    def test_successful_exit_with_all_context_sources_down_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            docs['savant_context.json']['sources'] = {s: {'status': 'unavailable'} for s in ('savant_api', 'savant_csv', 'nflreadpy_fallback')}
            path = root / 'data/savant_context.json'; path.write_text(json.dumps(docs['savant_context.json']))
            self.assertFalse(H.audit(root, NOW, {'validate_models': 'success', 'savant': 'success'})['healthy'])
            docs['savant_context.json']['sources']['savant_csv']['status'] = 'loaded'
            path.write_text(json.dumps(docs['savant_context.json']))
            report = H.audit(root, NOW)
            self.assertTrue(report['healthy'], report['issues'])
            self.assertTrue(report['warnings'])


if __name__ == '__main__':
    unittest.main()
