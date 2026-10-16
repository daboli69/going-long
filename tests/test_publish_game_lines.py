"""Game lines publish independently of degraded props, and only when the odds source itself is fresh. Synthetic boards; no provider request."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'tests'))

import publish_game_lines as P  # noqa: E402
import refresh_health as H  # noqa: E402
from test_refresh_health import NOW, fixtures  # noqa: E402

T = datetime(2026, 10, 16, 1, 0, tzinfo=timezone.utc)


def board(odds='FRESH', props='DEGRADED', observed=None, extra=None):
    observed = observed or (T - timedelta(minutes=20)).isoformat()
    doc = {'provider': 'parlay', 'sport': 'nfl', 'feed_status': 'FALLBACK', 'refresh_status': 'FALLBACK',
           'source_states': {'odds': odds, 'props': props, 'derivatives': 'DEGRADED', 'periods': 'FRESH'},
           'source_observed_at': {'odds': observed, 'props': observed},
           'props': [{'player': 'SECRET-PROP-ROW'}],
           'games': [{'game_id': '2026_07_AAA_BBB', 'season': 2026, 'week': 7, 'away': 'AAA', 'home': 'BBB', 'kickoff': '2026-10-25T17:00:00+00:00', 'gametime': '13:00', 'spread': -2.5,
                      'total': 44.5, 'away_ml': 120, 'home_ml': -140, 'over_odds': -110, 'under_odds': -110, 'away_spread_odds': -110, 'home_spread_odds': -110,
                      'away_score': None, 'home_score': None, 'completed': False, 'internal_note': 'must not be copied'}]}
    doc.update(extra or {})
    return doc


class BuildTests(unittest.TestCase):
    def test_fresh_odds_publish_even_when_props_and_derivatives_are_degraded(self):
        out = P.build(board(), T)
        self.assertEqual(out['props_state'], 'DEGRADED')
        self.assertEqual(out['games'][0]['total'], 44.5)
        self.assertNotIn('props', out)
        self.assertNotIn('SECRET-PROP-ROW', json.dumps(out))
        self.assertNotIn('internal_note', out['games'][0])

    def test_generated_at_is_the_odds_observation_not_the_publish_time(self):
        observed = (T - timedelta(hours=2)).isoformat()
        self.assertEqual(P.build(board(observed=observed), T)['generated_at'], observed)

    def test_every_non_fresh_stale_missing_or_future_odds_source_is_refused(self):
        for state in ('STALE', 'FAILED', 'DEGRADED', 'FALLBACK', 'UNKNOWN'):
            with self.subTest(state=state), self.assertRaises(P.Refused):
                P.build(board(odds=state), T)
        with self.assertRaises(P.Refused):
            P.build(board(observed=(T - timedelta(hours=6, minutes=1)).isoformat()), T)
        with self.assertRaises(P.Refused):
            P.build(board(observed='not a time'), T)
        with self.assertRaises(P.Refused):
            P.build(board(observed='2026-10-16T00:40:00'), T)  # no timezone
        with self.assertRaises(P.Refused):
            P.build(board(observed=(T + timedelta(hours=2)).isoformat()), T)
        with self.assertRaises(P.Refused):
            P.build({**board(), 'games': []}, T)
        with self.assertRaises(P.Refused):
            P.build({**board(), 'sport': 'ncaa'}, T)

    def test_a_retained_old_board_is_never_republished_as_fresh(self):
        # FALLBACK from a total provider outage keeps the previous odds state STALE and the old observation time
        with self.assertRaises(P.Refused):
            P.build(board(odds='STALE', observed=(T - timedelta(hours=30)).isoformat()), T)


class PublishTests(unittest.TestCase):
    def test_written_once_unchanged_afterwards_and_nothing_written_on_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / 'nfl_betting.json', Path(d) / 'out' / 'nfl_game_lines.json'
            src.write_text(json.dumps(board()))
            self.assertEqual(P.publish(src, dst, T), 'written')
            first = dst.read_bytes()
            self.assertEqual(P.publish(src, dst, T + timedelta(minutes=5)), 'unchanged')
            self.assertEqual(dst.read_bytes(), first)
            src.write_text(json.dumps(board(odds='FAILED')))
            with self.assertRaises(P.Refused):
                P.publish(src, dst, T + timedelta(minutes=10))
            self.assertEqual(dst.read_bytes(), first)  # the previous valid snapshot is untouched, and keeps its own older timestamp


class HealthIntegrationTests(unittest.TestCase):
    def test_degraded_props_keep_the_full_board_unhealthy_and_withheld_while_game_lines_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures(root)
            (root / 'data' / 'nfl_game_lines.json').write_text(json.dumps(P.build(board(), T)))
            report = H.audit(root, NOW, {'validate_models': 'success', 'nfl': 'failure', 'game_lines': 'success'}, ['data/nfl_betting.json', 'data/nfl_game_lines.json'])
            self.assertFalse(report['healthy'])  # strictness is not relaxed
            self.assertIn('data/nfl_game_lines.json', report['publication_paths'])
            self.assertIn('data/nfl_betting.json', report['excluded_publication_paths'])

    def test_a_failed_game_lines_step_blocks_only_its_own_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures(root)
            (root / 'data' / 'nfl_game_lines.json').write_text('{}')
            report = H.audit(root, NOW, {'validate_models': 'success', 'nfl': 'success', 'game_lines': 'failure'}, ['data/nfl_betting.json', 'data/nfl_game_lines.json'])
            self.assertIn('data/nfl_game_lines.json', report['excluded_publication_paths'])
            self.assertIn('data/nfl_betting.json', report['publication_paths'])

    def test_workflow_runs_the_step_after_the_nfl_build_and_before_the_integrity_gate(self):
        text = (REPO / '.github' / 'workflows' / 'data.yml').read_text(encoding='utf-8')
        at = lambda i: text.index('id: ' + i)
        self.assertLess(at('nfl'), at('game_lines'))
        self.assertLess(at('game_lines'), at('data_integrity'))
        self.assertIn('python scripts/publish_game_lines.py', text)


if __name__ == '__main__':
    unittest.main()
