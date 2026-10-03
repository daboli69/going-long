"""Offline regression checks for the audit's evidence boundaries."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('ncaa_recency_audit', HERE / 'audit.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.as_of = '2026-10-03T12:00:00Z'
        self.history = {'betting': {
            'generated_at': '2026-10-03T01:00:00Z', 'window': 12, 'minimum_games': 5,
            'sources': {'sportsdataverse': 'loaded'},
            'games': {'ncaa': [{'season': 2026, 'model': {'margin_mean': 3, 'season_evidence': {
                'home_current_games': 2, 'away_current_games': 3,
                'home_current_weight': .8, 'away_current_weight': .8}}}]},
            'validation': {'ncaa': {'margin': {'n': 123, 'rmse': 18}}},
            'features': {'generated_at': '2026-10-03T01:01:00Z', 'sources': {'ncaa': {'2026': 'loaded'}},
                         'ncaa': {'teams': {'old': {'last_game': '2024-08-30'}, 'new': {'last_game': '2026-09-27'}},
                                  'players': {}, 'defenses': {}, 'defense_coverage': {},
                                  'eligible_snaps': 1000, 'neutral_snaps': 300}}
        }}
        self.results = {'games': {'ncaa|a': {'homeScore': 30}, 'nfl|b': {'homeScore': 20}}}
        self.quotes = {'generated_at': '2026-10-03T01:00:00Z', 'games_raw': [{}], 'feed_status': 'FRESH'}
        for name in MODULE.MODEL_SOURCES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('source fixture\n', encoding='utf-8')
        self.save()

    def save(self):
        for name, document in zip(MODULE.PUBLIC_INPUTS, (self.history, self.quotes, self.results)):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document), encoding='utf-8')

    def test_fresh_build_does_not_make_old_team_current(self):
        report = MODULE.audit(self.root, self.as_of)
        self.assertEqual(report['ncaa_features']['team_latest_observation_years'], {'2024': 1, '2026': 1})
        self.assertEqual(report['production']['age_hours'], 11)

    def test_missing_current_sample_stays_unknown(self):
        del self.history['betting']['games']['ncaa'][0]['model']['season_evidence']
        self.save()
        report = MODULE.audit(self.root, self.as_of)
        self.assertEqual(report['production']['unknown_current_game_counts'], 1)
        self.assertEqual(report['production']['current_games_minimum_per_matchup'], {})

    def test_results_without_publication_times_cannot_be_replay(self):
        report = MODULE.audit(self.root, self.as_of)
        self.assertEqual(report['outcomes']['ncaa_results_rows'], 1)
        self.assertEqual(report['outcomes']['known_publication_timestamp_rows'], 0)
        self.assertEqual(report['experiment_status'], 'BLOCKED_DATA_NOT_FITTED')

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            MODULE.audit(self.root, '2026-10-03T12:00:00')

    def test_audit_does_not_read_ranking_or_write_inputs(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        # Any accidental read of this directory as a file would fail.
        (self.root / 'research' / 'today-ranking').mkdir(parents=True)
        MODULE.audit(self.root, self.as_of)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_provenance_hash_changes_with_source_bytes(self):
        first = MODULE.audit(self.root, self.as_of)
        path = self.root / MODULE.MODEL_SOURCES[0]
        path.write_text('changed source\n', encoding='utf-8')
        second = MODULE.audit(self.root, self.as_of)
        self.assertNotEqual(first['file_sha256'][MODULE.MODEL_SOURCES[0]], second['file_sha256'][MODULE.MODEL_SOURCES[0]])

    def test_registration_is_future_full_season_and_has_no_fitted_result(self):
        protocol = json.loads((HERE / 'protocol.json').read_text(encoding='utf-8'))
        self.assertEqual(protocol['status'], 'BLOCKED_DATA_NOT_FITTED')
        self.assertEqual(protocol['holdout']['season'], 2027)
        self.assertEqual(protocol['scope'].split(';')[-1].strip(), 'NFL excluded')
        self.assertGreater(MODULE.stamp(protocol['holdout']['kickoff_start_inclusive']), MODULE.stamp(protocol['data_cutoff']))


if __name__ == '__main__':
    unittest.main()
