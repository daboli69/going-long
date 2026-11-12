import tempfile, unittest
from pathlib import Path
import numpy as np
import pandas as pd
from lab import halftime as H


def play(game, qtr, left, posteam, hs, as_, **kw):
    row = dict(game_id=game, season=2024, week=1, season_type='REG', qtr=qtr, game_seconds_remaining=left, posteam=posteam,
               home_team='HOM', away_team='AWY', total_home_score=hs, total_away_score=as_, home_score=27, away_score=20,
               spread_line=3.0, total_line=44.5, pass_attempt=0, rush_attempt=0, qb_kneel=0, complete_pass=0, sack=0,
               yards_gained=0, receiving_yards=np.nan, rushing_yards=np.nan, receiver_player_id=None, rusher_player_id=None,
               receiver_player_name=None, rusher_player_name=None, epa=0.0)
    row.update(kw)
    return row


def catch(game, qtr, left, team, hs, as_, who, yards):
    return play(game, qtr, left, team, hs, as_, pass_attempt=1, complete_pass=1, yards_gained=yards, receiving_yards=yards,
                receiver_player_id=who, receiver_player_name=who)


def plays():
    return pd.DataFrame([
        catch('g', 1, 3000, 'HOM', 7, 0, 'wr1', 20), catch('g', 2, 2000, 'HOM', 10, 3, 'wr1', 15),
        play('g', 2, 1900, 'AWY', 10, 3, rush_attempt=1, yards_gained=4, rushing_yards=4, rusher_player_id='rb1', rusher_player_name='rb1'),
        play('g', 3, 1800, 'AWY', 10, 3),  # away receives the second-half kickoff
        catch('g', 3, 1500, 'HOM', 17, 3, 'wr1', 30), catch('g', 4, 300, 'HOM', 20, 20, 'wr2', 9),
        catch('g', 5, 0, 'HOM', 27, 20, 'wr1', 25),  # overtime counts as second half
    ])


class Tables(unittest.TestCase):
    def setUp(self):
        self.games = H.game_rows(plays())
        self.players = H.player_rows(plays(), self.games).set_index('player_id')

    def test_game_row_uses_halftime_score_and_overtime(self):
        g = self.games.iloc[0]
        self.assertEqual((g.h1_home, g.h1_away, g.h1_total, g.h1_margin), (10, 3, 13, 7))
        self.assertEqual((g.h2_total, g.h2_margin), (34, 0))
        self.assertEqual(g.home_receives_h2, 0.0)

    def test_player_row_splits_halves(self):
        w = self.players.loc['wr1']
        self.assertEqual((w.h1_tgt, w.h1_rec_yds, w.h2_rec_yds, w.h2_rec), (2, 35, 55, 2))
        self.assertEqual(w.h1_since_touch, 200)
        self.assertEqual((w.team_h1_margin, w.team_spread, w.receives_h2), (7, 3, 0))
        r = self.players.loc['rb1']
        self.assertEqual((r.h1_car, r.h1_rush_yds, r.team_h1_margin, r.receives_h2), (1, 4, -7, 1))

    def test_player_without_first_half_touch_is_left_out(self):
        self.assertNotIn('wr2', self.players.index)

    def test_first_game_has_no_history(self):
        self.assertTrue(np.isnan(self.players.loc['wr1'].pre_rec_yds))
        self.assertEqual(self.players.loc['wr1'].pre_games, 0)

    def test_trailing_average_excludes_current_game(self):
        two = pd.concat([plays(), plays().assign(game_id='g2', week=2)])
        rows = H.player_rows(two, H.game_rows(two))
        later = rows[(rows.player_id == 'wr1') & (rows.week == 2)].iloc[0]
        self.assertEqual((later.pre_rec_yds, later.pre_h2_rec_yds, later.pre_games), (90, 55, 1))


class Prices(unittest.TestCase):
    def test_implied(self):
        np.testing.assert_allclose(H.implied([-110, 150]), [110 / 210, 0.4])

    def test_prob_over_game_and_player(self):
        model = {'targets': {'h2_total': {'kind': 'game', 'residuals': np.array([-10., -5., 0., 5., 10.])},
                             'h2_rec': {'kind': 'rec', 'edges': np.array([2.0]), 'pools': [(np.array([0., 1., 2., 3.]), 1.5), (np.array([2., 4., 6., 8.]), 5.0)]}}}
        np.testing.assert_allclose(H.prob_over(model, 'h2_total', [20, 20], [22.5, 5]), [0.4, 1.0])
        # forecast 2.5 falls in the upper pool; outcomes are scaled by 2.5 / 5
        np.testing.assert_allclose(H.prob_over(model, 'h2_rec', [2.5], [2.5]), [0.5])

    def test_no_line_files_gives_empty_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(list(H.load_lines(tmp).columns), H.LINE_COLS)
            self.assertTrue(H.load_lines(tmp).empty)

    def test_line_file_missing_columns_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'a.csv').write_text('game_id,line\ng,3.5\n')
            with self.assertRaises(ValueError):
                H.load_lines(tmp)


if __name__ == '__main__':
    unittest.main()
