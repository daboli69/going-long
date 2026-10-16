"""P5-1/P5-2/P5-3: frozen protocols, lag/leakage guards, archive audit on a synthetic archive, and aggregate-only committed results."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'tests'))

from trend_research import experiments14 as e14, ledger, protocol_p5  # noqa: E402
import archive_game_line_audit as audit  # noqa: E402
from test_missions_history_export import MissionsHistoryExportTests  # noqa: E402


def team_frame(points, seasons=(2025,)):
    rows = []
    for season in seasons:
        for week, pf in enumerate(points, start=1):
            rows.append({'team': 'KC', 'season': season, 'week': week, 'pf': pf, 'pa': 20.0, 'nfl_plays': 60.0, 'nfl_pass': 0.6, 'fp_snaps': np.nan, 'fp_pass': np.nan, 'fp_neutral': np.nan,
                         'kick': pd.Timestamp('2025-09-07T17:00:00Z') + pd.Timedelta(days=7 * week)})
    return pd.DataFrame(rows)


class LagTests(unittest.TestCase):
    def test_a_games_own_result_and_future_games_never_enter_its_features(self):
        a = e14.add_lagged(team_frame([10, 20, 30, 40, 50, 60]))
        b = e14.add_lagged(team_frame([10, 20, 30, 999, 888, 777]))
        # week 4 uses weeks 1-3 only, so changing week 4+ results leaves week 4's feature untouched
        self.assertEqual(a.loc[a.week == 4, 'r_pf'].item(), b.loc[b.week == 4, 'r_pf'].item())
        self.assertAlmostEqual(a.loc[a.week == 4, 'r_pf'].item(), 20.0)
        self.assertNotEqual(a.loc[a.week == 5, 'r_pf'].item(), b.loc[b.week == 5, 'r_pf'].item())

    def test_early_season_needs_three_prior_games_and_nothing_crosses_seasons(self):
        out = e14.add_lagged(team_frame([10, 20, 30, 40], seasons=(2024, 2025)))
        week = lambda s, w: out[(out.season == s) & (out.week == w)]
        for w in (1, 2, 3):
            self.assertTrue(np.isnan(week(2025, w).r_pf.item()), f'week {w} has fewer than 3 prior same-season games')
        self.assertFalse(np.isnan(week(2025, 4).r_pf.item()))
        self.assertAlmostEqual(week(2025, 4).r_pf.item(), 20.0)  # the 2024 games are not borrowed

    def test_missing_fantasy_points_weeks_are_never_imputed(self):
        out = e14.add_lagged(team_frame([10, 20, 30, 40, 50]))
        self.assertTrue(out.r_fp_snaps.isna().all())  # no 2024-style export -> NaN, so the FP models skip these games

    def test_asof_is_the_latest_prior_kickoff(self):
        out = e14.add_lagged(team_frame([10, 20, 30]))
        self.assertEqual(out.loc[out.week == 3, 'prior_kick'].item(), out.loc[out.week == 2, 'kick'].item())


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.book = json.loads((REPO / 'research' / 'trend-intelligence' / 'ledger.json').read_text(encoding='utf-8'))['experiments']

    def test_protocols_match_their_registered_hashes_and_decision_rules_are_fixed(self):
        for exp_id, spec in protocol_p5.SPECS.items():
            self.assertEqual(self.book[exp_id]['spec_sha256'], ledger.spec_hash(spec), exp_id)
            self.assertIn('decision_rule', spec)
        self.assertIn('no_retrospective_change', protocol_p5.SPECS['P5-1']['decision_rule'])

    def test_results_are_aggregate_only_and_cover_every_registered_protocol(self):
        for exp_id in protocol_p5.SPECS:
            result = self.book[exp_id]['result']
            self.assertIsNotNone(result, exp_id)
            text = json.dumps(result)
            self.assertNotIn('"player_id"', text)
            self.assertNotIn('00-00', text)
            self.assertNotIn('quotes', text)
        self.assertIn('independent_score_unavailable', self.book['P5-3']['result'])

    def test_2024_fantasy_points_gap_is_reported_not_filled(self):
        cov = self.book['P5-2']['result']['coverage']
        self.assertEqual(cov['by_season']['2024']['with_fp_pace'], 0)
        self.assertEqual(cov['by_season']['2024']['excluded_from_fp_models'], cov['by_season']['2024']['records'])
        self.assertEqual(self.book['P5-2']['result']['timestamps']['forecast_asof_after_snapshot'], 0)

    def test_original_e13_e14_results_are_unchanged_by_this_work(self):
        self.assertEqual(self.book['E13']['status'], 'REJECTED')
        self.assertEqual(self.book['E14']['status'], 'REJECTED')
        self.assertEqual(self.book['E14']['result']['outcomes']['passing yards/g']['PRESSURE']['pooled']['n'], 78)


class AuditTests(MissionsHistoryExportTests):
    def games_csv(self, root, home=27, away=24):
        path = Path(root) / 'games.csv'
        with path.open('w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['game_id', 'home_team', 'away_team', 'home_score', 'away_score', 'gameday', 'gametime'])
            w.writerow(['2025_06_BUF_KC', 'KC', 'BUF', home, away, '2025-10-12', '13:00'])
        return path

    def run_audit(self, **kw):
        with tempfile.TemporaryDirectory() as root:
            results = self.fixture(root)
            return audit.audit(root, self.games_csv(root, **kw), results)

    def test_clean_synthetic_archive_passes_every_check(self):
        out = self.run_audit()
        self.assertEqual(out['violations'], {})
        self.assertEqual(out['status'], 'PASS')
        self.assertEqual(out['pairs']['book_pairs_not_reproduced_from_raw'], 0)
        self.assertEqual(out['scope']['player_null_market_keys'], ['h2h', 'spreads', 'totals'])
        self.assertLess(out['timestamps']['snapshot_minutes_before_actual_kickoff']['max'], 31)
        self.assertGreaterEqual(out['timestamps']['seconds_between_quote_at_and_snapshot_at']['min'], 0)

    def test_a_disagreeing_independent_score_is_a_violation(self):
        out = self.run_audit(home=30, away=10)
        self.assertGreater(out['violations'].get('score_mismatch_vs_nflverse', 0), 0)
        self.assertEqual(out['status'], 'FAIL')

    def test_missing_independent_score_is_reported_and_fails_the_one_percent_rule(self):
        out = self.run_audit(home=float('nan'), away=float('nan'))
        self.assertEqual(out['independent_score_unavailable']['games'], 1)
        self.assertEqual(out['status'], 'FAIL')
        self.assertEqual(out['violations'], {})


if __name__ == '__main__':
    unittest.main()
