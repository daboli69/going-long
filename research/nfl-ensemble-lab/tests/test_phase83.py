import numpy as np
import pandas as pd

from lab import upsets83 as U


def test_signed_orientation_positive_favours_underdog():
    x = pd.DataFrame({"p_weighted_average": [0.7, 0.3], "home_win": [1.0, 1.0], "season": [2020, 2020], "game_id": ["a", "b"],
                      **{f"{s}_m{i}": [0.0, 0.0] for s in ("h", "a") for i in (1, 2, 3, 4, 5, 6, 7, 9)}, "m8": [12.0, 12.0]})
    x.loc[0, "h_m1"], x.loc[0, "a_m1"] = 0.2, 0.0          # game a: home favourite has been lucky
    x.loc[1, "a_m5"] = 1.0                                   # game b: away favourite coming off a blowout win
    x.loc[0, "a_m9"], x.loc[0, "h_m9"] = 0.8, 0.4           # game a: underdog (away) more aggressive
    s = U.signed(x)
    assert s.loc[0, "M1_pythag_luck"] == 0.2 and s.loc[1, "M5_letdown"] == 1.0 and abs(s.loc[0, "M9_aggressiveness"] - 0.4) < 1e-12
    assert s["p_fav"].tolist() == [0.7, 0.7] and s["fav_won"].tolist() == [1.0, 0.0]


def test_metrics_are_as_of(monkeypatch):
    k = pd.Timestamp("2024-09-08", tz="UTC")
    games = pd.DataFrame({"game_id": [f"g{i}" for i in range(5)], "season": 2024, "week": range(1, 6),
                          "kickoff_utc": [k + pd.Timedelta(days=7 * i) for i in range(5)], "home_team": ["A", "B", "A", "B", "A"],
                          "away_team": ["B", "A", "B", "A", "B"], "home_score": [30, 10, 24, 17, None], "away_score": [10, 31, 20, 20, None],
                          "completed": [True, True, True, True, False], "div_game": [1, 1, 1, 1, 1], "source_game_id": [f"g{i}" for i in range(5)]})
    empty = pd.DataFrame(columns=["game_id", "team", "giveaways", "takeaways", "fum_recovered", "fum_total", "fourth_att", "fourth_go"])
    monkeypatch.setattr(U, "team_game_stats", lambda g: (empty.copy(), pd.DataFrame({"gid": [], "penalties": [], "old_game_id": []})))
    monkeypatch.setattr(U, "referees", lambda g, r: (pd.DataFrame(columns=["game_id", "penalties", "old_game_id", "referee"]),
                                                      pd.DataFrame(columns=["old_game_id", "referee"])))
    monkeypatch.setattr(U, "OUT", __import__("pathlib").Path(__import__("tempfile").mkdtemp()))
    a = U.build(games).set_index("game_id")
    g2 = games.copy()
    g2.loc[3, ["home_score", "away_score"]] = [50, 0]       # change a LATER result
    b = U.build(g2).set_index("game_id")
    pd.testing.assert_frame_equal(a.loc[["g0", "g1", "g2", "g3"]], b.loc[["g0", "g1", "g2", "g3"]])   # earlier games unaffected
    assert a.loc["g3", "h_m1"] == a.loc["g3", "h_m1"]       # 3 prior games -> Pythagorean luck defined at week 4
    assert np.isnan(a.loc["g2", "h_m1"])                     # only 2 prior games -> missing, never imputed
    assert a.loc["g1", "a_m5"] == 1.0                        # A won week 1 by 20 -> letdown flag next game
