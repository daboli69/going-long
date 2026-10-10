"""Synthetic same-date games; no external, licensed or historical inputs."""
import sys
from pathlib import Path
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from first_td_quote_summary import summarize_quotes


class FirstTdQuoteSummaryTests(unittest.TestCase):
    def setUp(self):
        self.games = pd.DataFrame([dict(game_id='g1', gameday='2026-10-04', home_team='BUF', away_team='MIA'),
                                   dict(game_id='g2', gameday='2026-10-04', home_team='DAL', away_team='NYG')])
        self.first = pd.DataFrame([dict(game_id='g1', td_player_id='p1'), dict(game_id='g2', td_player_id='p2')])
        self.quotes = pd.DataFrame([dict(gameday='2026-10-04', home='BUF', away='MIA', pid='p1', book='test', over=300, upd='2026-10-04T16:00:00Z'),
                                    dict(gameday='2026-10-04', home='DAL', away='NYG', pid='p2', book='test', over=400, upd='2026-10-04T16:00:00Z')])

    def test_two_games_on_one_date_have_two_game_denominators(self):
        rows, coverage = summarize_quotes(self.quotes, self.games, self.first)
        self.assertEqual(coverage, dict(quoted_games=2, outcome_games=2, scorer_covered_games=2, scorer_coverage=1))
        self.assertEqual(rows.groupby('game_id').imp.sum().to_dict(), {'g1': .25, 'g2': .2})

    def test_player_from_another_game_cannot_be_a_winner(self):
        self.quotes.loc[1, 'pid'] = 'p1'
        rows, coverage = summarize_quotes(self.quotes, self.games, self.first)
        self.assertEqual(int(rows.hit.sum()), 1)
        self.assertEqual(coverage['scorer_coverage'], .5)

    def test_names_are_mapped_and_unknown_games_are_excluded(self):
        self.quotes.loc[0, 'home'] = 'Buffalo Bills'
        self.quotes.loc[1, 'home'] = 'UNKNOWN'
        rows, coverage = summarize_quotes(self.quotes, self.games, self.first, {'Buffalo Bills': 'BUF'})
        self.assertEqual(rows.game_id.tolist(), ['g1'])
        self.assertEqual(coverage['quoted_games'], 1)
        self.assertEqual(coverage['scorer_coverage'], .5)

    def test_ambiguous_schedule_is_rejected(self):
        with self.assertRaises(ValueError):
            summarize_quotes(self.quotes, pd.concat([self.games, self.games.iloc[:1]]), self.first)

    def test_no_outcomes_have_no_coverage_estimate(self):
        rows, coverage = summarize_quotes(self.quotes, self.games, self.first.iloc[:0])
        self.assertTrue(rows.empty)
        self.assertIsNone(coverage['scorer_coverage'])


if __name__ == '__main__':
    unittest.main()
