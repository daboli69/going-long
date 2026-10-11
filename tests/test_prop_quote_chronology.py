"""Public synthetic quotes only; no licensed cache, network or outcomes access."""
import importlib.util
from pathlib import Path
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prop_build_quotes', ROOT / 'research' / 'prop-lines' / 'build_quotes.py')
QUOTES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUOTES)


def quote(**changes):
    return dict(player='Synthetic QB', market='pass_yds', book='fixture', line=250.5,
                over=-110, under=-110, dfs=False, home='BUF', away='MIA',
                kickoff='2026-10-04T17:00:00Z', updated='2026-10-04T16:00:00Z',
                commit_time='2026-10-04T16:05:00Z') | changes


class PropQuoteChronologyTests(unittest.TestCase):
    def collapse(self, *rows):
        return QUOTES.collapse_quotes(pd.DataFrame(rows))[0]

    def test_final_one_sided_row_does_not_borrow_an_older_opposite_price(self):
        rows = self.collapse(quote(), quote(over=-130, under=None, updated='2026-10-04T16:01:00Z'))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.iloc[0].over, -130)
        self.assertTrue(pd.isna(rows.iloc[0].under))
        self.assertEqual(rows.iloc[0].n_upd, 2)

    def test_final_complete_quote_preserves_paired_prices(self):
        rows = self.collapse(quote(), quote(over=-130, under=110, updated='2026-10-04T16:01:00Z'))
        self.assertEqual((rows.iloc[0].over, rows.iloc[0].under), (-130, 110))

    def test_stale_vendor_timestamp_does_not_make_postkickoff_observation_pregame(self):
        self.assertTrue(self.collapse(quote(commit_time='2026-10-04T20:00:00Z')).empty)
        rows = self.collapse(quote(), quote(over=-150, updated='2026-10-04T16:30:00Z',
                                          commit_time='2026-10-04T20:00:00Z'))
        self.assertEqual(rows.iloc[0].over, -110)
        self.assertEqual(rows.iloc[0].n_upd, 1)

    def test_invalid_and_contradictory_receipts_fail_closed(self):
        for field in ('commit_time', 'updated', 'kickoff'):
            for value in (None, 'malformed'):
                with self.subTest(field=field, value=value):
                    self.assertTrue(self.collapse(quote(**{field: value})).empty)
        self.assertTrue(self.collapse(quote(commit_time='2026-10-04T15:59:00Z')).empty)
        missing = quote()
        del missing['commit_time']
        self.assertTrue(self.collapse(missing).empty)

    def test_both_clocks_must_be_strictly_before_kickoff(self):
        self.assertTrue(self.collapse(quote(commit_time='2026-10-04T17:00:00Z')).empty)
        self.assertTrue(self.collapse(quote(updated='2026-10-04T17:00:00Z',
                                          commit_time='2026-10-04T17:00:00Z')).empty)

    def test_one_sided_td_is_preserved_but_dfs_and_unpriced_rows_are_excluded(self):
        rows = self.collapse(quote(market='atd', line=None, over=250, under=None),
                             quote(dfs=True), quote(over=None, under=None))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.iloc[0].market, 'atd')
        self.assertTrue(pd.isna(rows.iloc[0].under))

    def test_et_calendar_date_uses_winter_offset(self):
        rows = self.collapse(quote(kickoff='2026-12-01T04:30:00Z', updated='2026-12-01T02:00:00Z',
                                   commit_time='2026-12-01T02:05:00Z'))
        self.assertEqual(rows.iloc[0].gameday, '2026-11-30')

    def test_equal_vendor_timestamp_uses_latest_proven_observation(self):
        rows = self.collapse(quote(commit_time='2026-10-04T16:06:00Z', under=None, over=-140), quote())
        self.assertEqual(rows.iloc[0].over, -140)
        self.assertTrue(pd.isna(rows.iloc[0].under))

    def test_same_name_on_distinct_matchups_does_not_collapse(self):
        rows = self.collapse(quote(), quote(home='NYG', away='NYJ'))
        self.assertEqual(len(rows), 2)

    def test_ambiguous_normalized_name_outcomes_are_not_arbitrarily_selected(self):
        names = {'synthetic qb': {'p1', 'p2'}}
        results = {'p1|2026-10-04': {'pass_yds': 200}, 'p2|2026-10-04': {'pass_yds': 300}}
        self.assertEqual(QUOTES.lookup_outcome(names, results, 'Synthetic QB', '2026-10-04'), (None, None))
        del results['p2|2026-10-04']
        self.assertEqual(QUOTES.lookup_outcome(names, results, 'Synthetic QB', '2026-10-04'),
                         ('p1', {'pass_yds': 200}))


if __name__ == '__main__':
    unittest.main()
