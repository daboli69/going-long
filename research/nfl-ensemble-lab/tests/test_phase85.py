import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from lab import upsets85 as U


def _sheet(path: Path):
    rows = [["Notes: odds are decimal", None, None, None, None, None, None, None, None, None, None, None],
            ["Date", "Home Team", "Away Team", "Home Score", "Away Score", "Home Odds Open", "Away Odds Open",
             "Home Odds Close", "Away Odds Close", "Home Line Open", "Home Line Close", "Total Score Open"],
            ["2010-09-12", "St. Louis Rams", "Arizona Cardinals", 13, 17, 2.6, 1.55, 2.4, 1.62, 3.5, 2.5, 39],
            ["2021-09-12", "Washington Football Team", "Los Angeles Chargers", 16, 20, 1.95, 1.9, 2.0, 1.85, -1.0, 1.0, 44]]
    pd.DataFrame(rows).to_excel(path, header=False, index=False)


class TestPhase85(unittest.TestCase):
    def test_asb_parse_names_and_match(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "nfl.xlsx"
            _sheet(p)
            a = U.load_asb(p)
        self.assertEqual(a["home"].tolist(), ["LA", "WAS"])
        self.assertEqual(a["away"].tolist(), ["ARI", "LAC"])
        self.assertAlmostEqual(a["asb_home_line_open"].iloc[0], 3.5)
        g = pd.DataFrame({"game_id": ["2010_01_ARI_STL", "2021_01_LAC_WAS"], "season": [2010, 2021],
                          "gameday": ["2010-09-12", "2021-09-13"], "home_team": ["STL", "WAS"], "away_team": ["ARI", "LAC"]})
        m = U.match_asb(a, g)
        self.assertEqual(sorted(m["game_id"]), ["2010_01_ARI_STL", "2021_01_LAC_WAS"])   # second one matched at +1 day

    def test_ratings_are_as_of(self):
        def fake(season):
            rows = []
            for i, gd in enumerate(pd.date_range(f"{season}-09-10", periods=5, freq="7D")):
                gid = f"{season}_{i}"
                epa = 1.0 if i < 4 else 9.0          # only the last game is extreme
                rows += [{"game_id": gid, "game_date": gd, "posteam": "KC", "defteam": "DEN", "epa": epa},
                         {"game_id": gid, "game_date": gd, "posteam": "DEN", "defteam": "KC", "epa": -epa}]
            return pd.DataFrame(rows)
        with mock.patch.object(U, "_pbp", side_effect=fake):
            r = U.team_ratings([2010]).set_index(["game_id", "team"])
        self.assertAlmostEqual(r.loc[("2010_0", "KC"), "R"], 0.0)            # no earlier games, no previous season
        self.assertAlmostEqual(r.loc[("2010_4", "KC"), "R"], 4 * 2.0 / 8)     # the 9.0 game is never used for itself

    def test_confirmation_refuses_without_frozen_carry_list(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(U, "OUT", Path(d)):
            with self.assertRaises(FileNotFoundError):
                U.confirm(pd.DataFrame(), [], n_perm=0)

    def test_discovery_writes_carry_list_before_confirmation(self):
        rng = np.random.default_rng(0)
        rows = []
        for s in list(range(2006, 2016)) + list(range(2016, 2026)):
            for _ in range(150):
                p = rng.uniform(0.5, 0.85)
                rows.append({"season": s, "p_close_fav": p, "fav_won": float(rng.random() < p), "dog_close_decimal": 2.5,
                             **{a: rng.normal() for a in U.FAMILIES["EM"] + U.FAMILIES["ES"]}, "C1": np.nan, "C2": np.nan, "C3": np.nan, "cfav_won": float(rng.random() < p), "cp_close_fav": p, "cdog_close_decimal": 2.5})
        df = pd.DataFrame(rows)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(U, "OUT", Path(d)):
            r = U.discover(df, list(range(2006, 2026)), True)
            c = json.loads((Path(d) / "carried.json").read_text())
            self.assertEqual(c["carried"], r["carried"])
            conf = U.confirm(df, list(range(2006, 2026)), n_perm=0, log=lambda m: None)
            self.assertEqual(set(conf.get("ES", {})), set(r["carried"]["ES"]))   # only carried angles are scored

    def test_holm(self):
        h = U._holm({"a": 0.01, "b": 0.04, "c": 0.03})
        self.assertAlmostEqual(h["a"], 0.03)
        self.assertAlmostEqual(h["c"], 0.06)
        self.assertAlmostEqual(h["b"], 0.06)


if __name__ == "__main__":
    unittest.main()
