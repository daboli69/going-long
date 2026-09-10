import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from parlay_feed import normalize_props, normalize_periods


class ParlayTests(unittest.TestCase):
    def test_period_duplicates_and_first_td_alias(self):
        q=dict(match_id='a',source='book',market='total',period_key='1H',side='over',line=20.5,price=-110,age_seconds=4)
        rows=normalize_periods([q,dict(q,age_seconds=1,price=110),dict(q,period_key='Q1'),dict(q,line=21.5)])
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['price'],110)
        self.assertTrue(rows[0]['inPlay'])
        first=normalize_props([dict(player='P',bookmaker='book',market_key='player_first_td',line=None,over_price=500)])
        self.assertEqual(first[0]['market'],'first_td')
        self.assertEqual(first[0]['line'],.5)

    def test_thresholds_missing_prices_and_dfs(self):
        quote = dict(player='Josh Allen', bookmaker='draftkings', market_key='player_anytime_td',
                     line=1.5, over_price=600, under_price=None, commence_time='2030-09-01T00:00:00Z')
        rows = normalize_props([quote, {**quote, 'line': 0},
                                {**quote, 'bookmaker': 'prizepicks', 'dfs_normalized': True}],
                               datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual([r['line'] for r in rows], [1.5, .5, 1.5])
        self.assertIsNone(rows[0]['underOdds'])
        self.assertIsNone(rows[2]['overOdds'])

    def test_started_invalid_and_unsupported_rows(self):
        quote = dict(player='Puka Nacua', bookmaker='a', market_key='player_receiving_yards', line=80.5)
        rows = normalize_props([quote, {**quote, 'commence_time': 'invalid'},
                                {**quote, 'commence_time': '2020-01-01T00:00:00Z'},
                                {**quote, 'market_key': 'player_longest_reception'}])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]['kickoff'])


if __name__ == '__main__':
    unittest.main()
