import numpy as np
import pandas as pd
import pytest

from lab import ingame as G
from lab import ingame2 as I2


def test_role_groups_split_by_position_and_rank():
    assert I2.group_of("rec", "WR", 1) == "WR1" and I2.group_of("rec", "WR", 7) == "WR3" and I2.group_of("rec", "TE", 2) == "TE2"
    assert I2.group_of("rush", "QB", 1) == "QB1" and I2.group_of("rush", "RB", 3) == "RB2" and I2.group_of("pass", "QB", 1) == "QB"


def test_calibrated_share_uses_the_group_and_falls_back_for_an_unseen_one():
    h = {"groups": {"WR1": {"a": 0.0, "b": 1.0, "kappa": 12.0}, "TE1": {"a": 0.0, "b": 1.0, "kappa": 30.0}}}
    s, k = I2.calibrated_share(h, "WR1", 0.25)
    assert s == pytest.approx(0.25, abs=1e-6) and k == 12.0            # a = 0, b = 1 leaves the share where it was
    s2, k2 = I2.calibrated_share(h, "RB9", 0.25)
    assert s2 == 0.25 and k2 == 21.0                                     # unseen group: raw share, median strength
    h["groups"]["WR1"]["a"] = 1.0
    assert I2.calibrated_share(h, "WR1", 0.25)[0] > 0.25


def test_the_win_model_frame_is_from_the_home_side_and_drops_overtime():
    plays = pd.DataFrame({"game_id": ["g"] * 3, "season": 2025, "qtr": [1, 4, 5], "posteam": ["H", "A", "H"], "home_team": "H", "total_home_score": [0, 7, 7],
                          "total_away_score": [0, 10, 10], "game_seconds_remaining": [3500.0, 100.0, 300.0], "down": [1, 3, 1], "ydstogo": [10, 4, 10],
                          "yardline_100": [75.0, 30.0, 50.0], "posteam_timeouts_remaining": [3, 1, 3], "defteam_timeouts_remaining": [3, 2, 3], "spread_line": 3.0,
                          "result": 4.0, "home_wp": [0.6, 0.2, 0.5]})
    f = I2.wp_frame(plays)
    assert len(f) == 2 and list(f["margin"]) == [0, -3] and list(f["poss_home"]) == [1, 0] and (f["y"] == 1).all()
    assert f["secs"].iloc[1] == 100.0 and f["t"].iloc[1] == G.GAME - 100.0
