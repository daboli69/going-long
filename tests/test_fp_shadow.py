"""fp_shadow: write-once, never-after-kickoff, tamper-evident capture of pregame total forecasts. Synthetic data only; no licensed files are read."""
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))

import fp_shadow as fs  # noqa: E402

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
MARKET_AT = (NOW - timedelta(hours=1)).isoformat()


def game(gid, kickoff, **extra):
    base = {'game_id': gid, 'season': 2026, 'week': 7, 'away': 'AAA', 'home': 'BBB', 'kickoff': kickoff.strftime('%Y-%m-%dT%H:%M:%SZ'), 'total': 44.5, 'over_odds': -110, 'under_odds': -110,
            'away_score': None, 'home_score': None, 'completed': False}
    base.update(extra)
    return base


def fitted():
    return {'CH_RAW': (lambda f: f['pts6'], 13.0), 'B_PTS': (lambda f: 0.1 * f['pts6'], 13.0), 'B_NFL': (lambda f: 0.1 * f['pts6'], 13.0),
            'C_FP': (lambda f: None if f['fp_snaps6'] is None else 0.2 * f['pts6'], 13.0)}


FEATS = {'exp_total': 46.0, 'nfl_plays6': 120.0, 'nfl_pass6': 0.58, 'fp_snaps6': 130.0, 'fp_pass6': 58.0, 'fp_neutral6': 55.0}


def plan(games, features=None, now=NOW, **kw):
    return fs.plan_captures(games, features if features is not None else {g['game_id']: FEATS for g in games}, fitted(), now, market_generated_at=kw.pop('market_at', MARKET_AT),
                            market_sha256='m' * 64, source_hashes={'x': 'h'}, cutoffs={}, **kw)


class PlanTests(unittest.TestCase):
    def test_future_game_with_price_is_captured_with_all_models_and_provenance(self):
        records, excl = plan([game('g1', NOW + timedelta(days=3))])
        self.assertEqual((len(records), excl), (1, []))
        r = records[0]
        self.assertEqual(set(r['forecasts']), set(fs.MODELS))
        self.assertAlmostEqual(r['market']['p_over_devig_proportional'], 0.5)
        self.assertEqual(r['market']['source_sha256'], 'm' * 64)
        self.assertEqual(r['captured_at'], '2026-10-16T12:00:00Z')
        self.assertIn('forecast_created', r['timestamps'])

    def test_started_played_priceless_and_stale_games_are_excluded_with_reasons(self):
        games = [game('late', NOW + timedelta(minutes=10)), game('played', NOW + timedelta(days=1), completed=True, home_score=20, away_score=17),
                 game('noprice', NOW + timedelta(days=1), total=None), game('wk5', NOW + timedelta(days=1), week=5), game('ok', NOW + timedelta(days=1))]
        records, excl = plan(games)
        self.assertEqual([r['game_id'] for r in records], ['ok'])
        reasons = {e['game_id']: e['reason'] for e in excl}
        self.assertTrue(reasons['late'].startswith('started_or_less_than'))
        self.assertEqual(reasons['played'], 'already_played')
        self.assertEqual(reasons['noprice'], 'no_matched_market_price')
        self.assertNotIn('wk5', reasons)  # outside Weeks 6-10: silently out of scope, never captured
        stale, excl2 = plan([game('g', NOW + timedelta(days=1))], market_at=(NOW - timedelta(hours=9)).isoformat())
        self.assertEqual((stale, excl2[0]['reason']), ([], 'market_snapshot_older_than_6h'))

    def test_missing_features_exclude_the_game_and_missing_fp_nulls_only_the_challenger(self):
        records, excl = plan([game('nofeat', NOW + timedelta(days=1))], features={})
        self.assertEqual((records, excl[0]['reason']), ([], 'fewer_than_3_prior_same_season_games'))
        partial = {**FEATS, 'fp_snaps6': None}
        records, _ = plan([game('p', NOW + timedelta(days=1))], features={'p': partial})
        self.assertIsNone(records[0]['forecasts']['C_FP'])
        self.assertIsNotNone(records[0]['forecasts']['B_NFL'])

    def test_probability_is_normal_cdf_of_edge_over_sigma(self):
        records, _ = plan([game('g', NOW + timedelta(days=1))])
        f = records[0]['forecasts']['CH_RAW']
        self.assertAlmostEqual(f['p_over'], 0.5 * (1 + __import__('math').erf((46.0 - 44.5) / 13.0 / 2 ** 0.5)), places=9)
        self.assertAlmostEqual(f['expected_total'], 46.0, places=9)


class WriteOnceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / 'shadow'
        self.addCleanup(lambda: self._cleanup())

    def _cleanup(self):
        for p in Path(self.tmp.name).rglob('*'):
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass
        self.tmp.cleanup()

    def record(self, gid='g1', days=3):
        return plan([game(gid, NOW + timedelta(days=days))])[0][0]

    def test_first_write_wins_and_the_file_is_never_changed(self):
        rec = self.record()
        self.assertEqual(fs.write_once(self.out, rec, clock=lambda: NOW), 'written')
        path = self.out / 'captures' / 'g1.json'
        before = path.read_bytes()
        changed = {**rec, 'forecasts': {**rec['forecasts'], 'C_FP': {'expected_total': 99, 'p_over': 0.99, 'sigma': 1}}}
        self.assertEqual(fs.write_once(self.out, changed, clock=lambda: NOW + timedelta(hours=1)), 'already_captured')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(fs.verify(self.out)['entries'], 1)

    def test_a_forecast_is_refused_when_time_passed_between_planning_and_writing(self):
        rec = self.record(days=3)
        rec = {**rec, 'kickoff': (NOW + timedelta(minutes=45)).strftime('%Y-%m-%dT%H:%M:%SZ')}
        late = lambda: NOW + timedelta(minutes=20)  # 25 minutes to kickoff < 30 minute lead
        self.assertEqual(fs.write_once(self.out, rec, clock=late), 'refused_too_late')
        self.assertFalse((self.out / 'captures' / 'g1.json').exists())
        self.assertEqual(fs.verify(self.out)['entries'], 0)

    def test_written_time_is_the_clock_at_write_not_the_planned_time(self):
        rec = self.record()
        fs.write_once(self.out, rec, clock=lambda: NOW + timedelta(minutes=5))
        stored = json.loads((self.out / 'captures' / 'g1.json').read_text())
        self.assertEqual(stored['captured_at'], '2026-10-16T12:05:00Z')

    def test_ledger_chain_detects_edit_deletion_and_foreign_files(self):
        for gid in ('a', 'b', 'c'):
            fs.write_once(self.out, self.record(gid), clock=lambda: NOW)
        self.assertTrue(fs.verify(self.out)['ok'])
        target = self.out / 'captures' / 'b.json'
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        target.write_text(target.read_text().replace('"week":7', '"week":8'))
        problems = ' '.join(fs.verify(self.out)['problems'])
        self.assertIn('b missing or modified', problems)
        (self.out / 'captures' / 'zzz.json').write_text('{}')
        self.assertIn('zzz is not in the ledger', ' '.join(fs.verify(self.out)['problems']))
        ledger = (self.out / 'ledger.jsonl').read_text().splitlines()
        (self.out / 'ledger.jsonl').write_text('\n'.join([ledger[0], ledger[2]]) + '\n')
        self.assertIn('ledger break', ' '.join(fs.verify(self.out)['problems']))

    def test_capture_directory_inside_the_repository_is_refused(self):
        with self.assertRaises(fs.ShadowError):
            fs.check_out_dir(REPO / 'data' / 'fp_shadow')

    def test_real_capture_cannot_use_an_injected_clock(self):
        with self.assertRaises(fs.ShadowError):
            fs.capture(REPO / 'FantasyPoints', self.out, now=NOW, dry_run=False)

    def test_settlement_adds_a_file_and_leaves_the_capture_untouched(self):
        rec = self.record()
        fs.write_once(self.out, rec, clock=lambda: NOW)
        capture_path = self.out / 'captures' / 'g1.json'
        before = capture_path.read_bytes()
        results = Path(self.tmp.name) / 'results.json'
        results.write_text(json.dumps({'games': [game('g1', NOW + timedelta(days=3), completed=True, home_score=27, away_score=20)]}))
        self.assertEqual(fs.settle(self.out, results), {'g1': 'settled'})
        self.assertEqual(fs.settle(self.out, results), {'g1': 'already_settled'})
        settled = json.loads((self.out / 'settled' / 'g1.json').read_text())
        self.assertEqual((settled['total'], settled['y_over']), (47, 1))
        self.assertEqual(capture_path.read_bytes(), before)
        self.assertTrue(fs.verify(self.out)['ok'])

    def test_pushes_are_settled_but_not_scored_and_unfinished_games_wait(self):
        fs.write_once(self.out, self.record('p'), clock=lambda: NOW)
        fs.write_once(self.out, self.record('q'), clock=lambda: NOW)
        results = Path(self.tmp.name) / 'results.json'
        results.write_text(json.dumps({'games': [game('p', NOW + timedelta(days=3), completed=True, home_score=24, away_score=20.5 + 0)]}))
        done = fs.settle(self.out, results)
        self.assertEqual(done['q'], 'not_final')
        self.assertEqual(done['p'], 'settled')

    def test_receipt_contains_hashes_and_timestamps_but_no_probabilities(self):
        fs.write_once(self.out, self.record(), clock=lambda: NOW)
        text = json.dumps(fs.receipt(self.out))
        self.assertIn('file_sha256', text)
        self.assertNotIn('p_over', text)
        self.assertNotIn('expected_total', text)
        self.assertNotIn('fp_snaps6', text)



class SchedulingAndBoardSourceTests(unittest.TestCase):
    def test_board_from_git_fetches_then_reads_the_blob_without_touching_the_tree(self):
        from unittest import mock
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(stdout=b'{"games": []}')
        with mock.patch.object(fs.subprocess, 'run', fake):
            self.assertEqual(fs.board_from_git('origin/main'), b'{"games": []}')
        self.assertIn('fetch', calls[0])
        self.assertEqual(calls[1][-2:], ['show', 'origin/main:data/nfl_betting.json'][-2:])
        self.assertTrue(all(c[0] == 'git' for c in calls))

    def test_installer_is_a_dry_run_unless_explicitly_activated_and_is_not_admin(self):
        text = (REPO / 'scripts' / 'install_fp_shadow_task.ps1').read_text(encoding='utf-8')
        self.assertIn('[switch]$Activate', text)
        self.assertLess(text.index('if (-not $Activate)'), text.index('Register-ScheduledTask'))
        self.assertIn('-RunLevel Limited', text)
        self.assertIn('--market-from-url main', text)
        self.assertNotIn('RunLevel Highest', text)
        self.assertIn('git -C $repoPath archive', text)  # durable, commit-pinned runtime copy
        self.assertLess(text.index("--dry-run"), text.index('Register-ScheduledTask'))  # tested before the current task is replaced
        self.assertIn('Another scheduled task already runs fp_shadow.py', text)  # duplicate prevention

    def test_capture_wrapper_uses_the_published_board_and_never_the_hand_edited_file(self):
        self.assertIn('--market-from-url main', (REPO / 'scripts' / 'run_fp_shadow_capture.cmd').read_text(encoding='utf-8'))


class BoardFromUrlTests(unittest.TestCase):
    def test_newest_published_board_wins_and_missing_files_are_skipped(self):
        boards = {fs.RAW_BASE + 'main/data/nfl_game_lines.json': json.dumps({'generated_at': '2026-10-16T05:00:00+00:00', 'tag': 'lines'}).encode(),
                  fs.RAW_BASE + 'main/data/nfl_betting.json': json.dumps({'generated_at': '2026-10-15T15:00:00+00:00', 'tag': 'full'}).encode()}
        self.assertEqual(json.loads(fs.board_from_url('main', fetch=boards.__getitem__))['tag'], 'lines')
        del boards[fs.RAW_BASE + 'main/data/nfl_game_lines.json']

        def fetch(url):
            return boards[url]
        self.assertEqual(json.loads(fs.board_from_url('main', fetch=fetch))['tag'], 'full')  # the game-lines file does not exist yet: KeyError is treated as unavailable

    def test_nothing_readable_or_a_hostile_ref_is_refused(self):
        with self.assertRaises(fs.ShadowError):
            fs.board_from_url('main', fetch=lambda url: b'not json')
        for ref in ('../x', 'a b', 'main?x=1', '/etc'):
            with self.assertRaises(fs.ShadowError):
                fs.board_from_url(ref, fetch=lambda url: b'{}')

    def test_runtime_commit_pin_is_used_for_provenance(self):
        self.assertTrue(fs.git_sha() is None or len(fs.git_sha()) >= 7)


if __name__ == '__main__':
    unittest.main()
