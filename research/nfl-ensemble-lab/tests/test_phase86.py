import unittest

import numpy as np
import pandas as pd

from lab import tracking86 as T


class TestPhase86(unittest.TestCase):
    def test_arrival_separation_uses_last_frame_and_nearest_defender(self):
        inp = pd.DataFrame({"game_id": 1, "play_id": 1, "nfl_id": [10, 20, 30],
                            "player_side": ["Offense", "Defense", "Defense"],
                            "player_role": ["Targeted Receiver", "Defensive Coverage", "Defensive Coverage"]})
        out = pd.DataFrame({"game_id": 1, "play_id": 1, "nfl_id": [10, 20, 30, 10, 20, 30], "frame_id": [1, 1, 1, 2, 2, 2],
                            "x": [0, 0.5, 9, 10, 13, 10], "y": [0, 0, 0, 0, 4, 1]})
        s = T.arrival_separation(inp, out)
        self.assertAlmostEqual(s["sep"].iloc[0], 1.0)          # frame 2: defender 30 at 1 yd beats defender 20 at 5 yd

    def test_play_without_tracked_defender_is_dropped(self):
        inp = pd.DataFrame({"game_id": 1, "play_id": 1, "nfl_id": [10], "player_side": ["Offense"], "player_role": ["Targeted Receiver"]})
        out = pd.DataFrame({"game_id": 1, "play_id": 1, "nfl_id": [10], "frame_id": [1], "x": [0.0], "y": [0.0]})
        self.assertTrue(T.arrival_separation(inp, out).empty)

    def test_edges_are_as_of_with_minimum_prior_games(self):
        rows = []
        for w in range(1, 7):
            sep = 9.0 if w == 5 else 2.0                       # week 5 is extreme and must not affect week 5's own edge
            rows += [{"week": w, "game_id": w, "off": "KC", "def": "DEN", "sep": sep},
                     {"week": w, "game_id": w, "off": "DEN", "def": "KC", "sep": 1.0}]
        e, _ = T.team_edges(pd.DataFrame(rows))
        e = e.set_index(["team", "week"])["E"]
        self.assertTrue(np.isnan(e[("KC", 3)]))                # only 2 earlier games
        self.assertAlmostEqual(e[("KC", 4)], 1.0)
        self.assertAlmostEqual(e[("KC", 5)], 1.0)
        self.assertAlmostEqual(e[("KC", 6)], (2 * 4 + 9) / 5 - 1.0)


if __name__ == "__main__":
    unittest.main()
