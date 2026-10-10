import json
import gzip
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
        'history.json': {'betting': {'schema_version': 1, 'profiles': {}, 'generated_at': STAMP, 'source_content_at': STAMP, 'source_roster_at': STAMP, 'source_injury_at': STAMP}},
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
        if name in ('injury_context.json', 'nfl_roster.json'):
            doc.update(source_content_at=STAMP, source_roster_at=STAMP, source_injury_at=STAMP)
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
        for bad in (None, [], {'generated_at': STAMP, 'source_content_at': STAMP, 'source_roster_at': STAMP, 'source_injury_at': STAMP}, {'generated_at': STAMP, 'source_content_at': STAMP, 'source_roster_at': STAMP, 'source_injury_at': STAMP, 'players': []}):
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

    def test_workflow_dependency_order_and_independent_integrity_publication_guard(self):
        text = (Path(__file__).resolve().parents[1] / '.github/workflows/data.yml').read_text()
        blocks = re.split(r'^      - name: ', text, flags=re.M)[1:]
        by_id = {}
        for i, block in enumerate(blocks):
            match = re.search(r'^        id: (\w+)$', block, flags=re.M)
            if match: by_id[match[1]] = (i, block)
        for target in ('going_score', 'jackpot', 'slate_breaker'):
            for dependency in ('history', 'projections', 'context', 'injury_context', 'roster_public'):
                self.assertLess(by_id[dependency][0], by_id[target][0], (dependency, target))
        for dependency in ('context', 'injury_context', 'roster_public'):
            self.assertLess(by_id[dependency][0], by_id['projections'][0])
        for target in ('savant', 'results'):
            self.assertIn('continue-on-error: true', by_id[target][1])
        for block in blocks:
            self.assertNotIn('steps.validate_models.outcome', block)
            if block.startswith('Commit generated snapshots\n'):
                self.assertIn("steps.data_integrity.outcome == 'success'", block)
        self.assertIn('continue-on-error: true', by_id['validate_models'][1])
        self.assertIn('test_derivatives.py', by_id['validate_projection_logic'][1])
        self.assertIn('test_champion_policy.py', by_id['validate_projection_logic'][1])
        self.assertIn('--publication-check', by_id['data_integrity'][1])
        self.assertNotIn('date -u', by_id['freeze'][1])
        report = next(block for block in blocks if block.startswith('Report source failures\n'))
        self.assertIn('toJSON(steps)', report)
        self.assertIn('refresh_health.py', report)
        self.assertNotIn('|| echo', by_id['freeze'][1])
        self.assertIn('exit "$status"', by_id['freeze'][1])
        publication = by_id['publish'][1]
        self.assertIn('publication_paths', publication)
        self.assertEqual(publication.count('git push origin HEAD:main'), 1)
        self.assertNotIn('git reset', publication)
        self.assertNotIn('git restore', publication)
        self.assertNotIn('--force', publication)

    def test_roster_move_diagnostic_and_partial_source_failure_allow_valid_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            # Old snapshots can fail a roster-move assertion and props can fail independently.
            docs['nfl_betting.json']['source_states']['props'] = 'STALE'
            (root / 'data/nfl_betting.json').write_text(json.dumps(docs['nfl_betting.json']))
            report = H.audit(root, NOW, {'validate_models': 'failure', 'nfl': 'failure'}, ['data/nfl_roster.json'])
            self.assertFalse(report['healthy'])
            self.assertTrue(report['publication_ready'], report['data_integrity_issues'])
            self.assertEqual(len(report['test_failures']), 1)
            self.assertIn('workflow step nfl: failure', report['source_failures'])
            self.assertIn('nfl_betting.json: props is STALE', report['source_failures'])
            docs['nfl_roster.json']['players'] = []
            (root / 'data/nfl_roster.json').write_text(json.dumps(docs['nfl_roster.json']))
            self.assertFalse(H.audit(root, NOW, changed=['data/nfl_roster.json'])['publication_ready'])

    def test_rewritten_injury_envelope_cannot_refresh_source_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); docs = fixtures(root)
            docs['injury_context.json']['source_content_at'] = '2026-10-08T10:00:00Z'
            (root / 'data/injury_context.json').write_text(json.dumps(docs['injury_context.json']))
            self.assertFalse(H.audit(root, NOW, changed=['data/injury_context.json'])['publication_ready'])

    def test_changed_consumer_corruption_and_failed_component_are_excluded_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixtures(root)
            p = root / 'data/opportunities.json'
            for text in ('{broken', '{"probability": NaN}', '{"probability": 1e999}',
                         '{"probability": -1e999}', '{"count":' + '9' * 1000 + '}', '42'):
                with self.subTest(text=text):
                    p.write_text(text)
                    report = H.audit(root, NOW, {'validate_models': 'failure', 'nfl': 'failure', 'roster_public': 'success'},
                                     ['data/opportunities.json', 'data/nfl_betting.json', 'data/nfl_roster.json'])
                    self.assertFalse(report['healthy'])
                    self.assertFalse(report['publication_ready'])
                    self.assertEqual(report['publication_paths'], ['data/nfl_roster.json'])
                    self.assertEqual(set(report['excluded_publication_paths']), {'data/opportunities.json', 'data/nfl_betting.json'})

    def test_actual_model_fault_blocks_dependent_outputs_but_not_valid_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixtures(root)
            report = H.audit(root, NOW, {'validate_projection_logic': 'failure'},
                             ['data/history.json', 'data/nfl_betting.json', 'data/nfl_roster.json'])
            self.assertEqual(report['publication_paths'], ['data/nfl_betting.json', 'data/nfl_roster.json'])
            self.assertEqual(report['excluded_publication_paths'], ['data/history.json'])
            self.assertEqual(report['test_failures'], ['workflow step validate_projection_logic: failure'])

    def test_gzip_shards_validate_and_invalid_sibling_keeps_manifest_group_unpublished(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixtures(root); (root / 'data/charts').mkdir()
            shard = root / 'data/charts/fixture.json.gz'; shard.write_bytes(gzip.compress(b'{"rows":[]}'))
            index = root / 'data/charts/index.json'; index.write_text('{"shards":["fixture.json.gz"]}')
            changed = ['data/charts/fixture.json.gz', 'data/charts/index.json', 'data/nfl_roster.json']
            self.assertEqual(H.audit(root, NOW, changed=changed)['publication_paths'], sorted(changed))
            shard.write_bytes(gzip.compress(b'{"rows":[NaN]}'))
            report = H.audit(root, NOW, changed=changed)
            self.assertEqual(report['publication_paths'], ['data/nfl_roster.json'])
            self.assertEqual(set(report['excluded_publication_paths']), set(changed[:2]))

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
