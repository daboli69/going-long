import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from lab import phase15 as P
from lab.sequential import cs_upper, monitor_summary


class TestPhase15(unittest.TestCase):
    def test_windows_sunday_game(self):
        w = P.windows(pd.Timestamp("2021-10-17 17:00", tz="UTC"))            # Sunday 1 pm ET
        self.assertEqual(w["open"].tz_convert(P.ET).strftime("%a %Y-%m-%d %H"), "Sun 2021-10-10 20")
        self.assertEqual(w["mid"].tz_convert(P.ET).strftime("%a %Y-%m-%d %H"), "Wed 2021-10-13 12")

    def test_windows_thursday_and_monday_games(self):
        th = P.windows(pd.Timestamp("2021-10-15 00:20", tz="UTC"))           # Thursday 8:20 pm ET
        self.assertEqual(th["open"].tz_convert(P.ET).strftime("%a %d"), "Sun 10")
        self.assertEqual(th["mid"].tz_convert(P.ET).strftime("%a %d"), "Wed 13")
        mo = P.windows(pd.Timestamp("2021-10-19 00:15", tz="UTC"))           # Monday 8:15 pm ET
        self.assertEqual(mo["open"].tz_convert(P.ET).strftime("%a %d"), "Sun 10")

    def test_capture_before_respects_72_hours(self):
        idx = pd.Series(pd.to_datetime(["2021-10-01 00:00", "2021-10-08 00:00"], utc=True), index=["a", "b"])
        self.assertEqual(P.capture_before(idx, pd.Timestamp("2021-10-09", tz="UTC")), "b")
        self.assertIsNone(P.capture_before(idx, pd.Timestamp("2021-10-12", tz="UTC")))

    def test_parse_both_espn_layouts(self):
        import tempfile
        old = "<table><tr><td>Arizona Cardinals</td><td></td><td></td></tr><tr><td>NAME</td><td>STATUS</td><td>DATE</td></tr>" \
              "<tr><td>Josh Rosen, QB</td><td>Out</td><td>Oct 14</td></tr></table>"
        new = "<table><thead><tr><th>NAME</th><th>POS</th><th>EST. RETURN DATE</th><th>STATUS</th><th>COMMENT</th></tr></thead>" \
              "<tbody><tr><td>Kyler Murray</td><td>QB</td><td>Oct 19</td><td>Questionable</td><td>x</td></tr></tbody></table>"
        with tempfile.TemporaryDirectory() as d:
            for name, html, who, st in (("o.html", old, "josh rosen", "out"), ("n.html", new, "kyler murray", "questionable")):
                f = Path(d) / name
                f.write_text("<html><body>" + html + "</body></html>")
                r = P.parse_capture(f)
                self.assertTrue(((r["name"] == who) & (r["status"] == st)).any())

    def test_pit_delta_zeroes_unknown_changes(self):
        x = pd.DataFrame({"home_change": [True, True], "away_change": [False, True], "delta_home_team": [-5.0, -5.0],
                          "delta_away_team": [0.0, -3.0], "home_open": [True, False], "away_open": [True, True]})
        np.testing.assert_allclose(P.pit_delta(x, "open"), [-5.0, 3.0])

    def test_deming_recovers_slope(self):
        rng = np.random.default_rng(3)
        t = rng.normal(0, 3, 4000)
        x, y = t + rng.normal(0, 1, 4000), 0.5 * t + rng.normal(0, 1, 4000)
        b, _ = P.deming(x, y, 1.0)
        self.assertAlmostEqual(b, 0.5, delta=0.05)

    def test_futility_bound(self):
        self.assertTrue(monitor_summary(np.full(20000, -0.05), 0.005)["futile"])     # sigma=1 bound is conservative
        self.assertFalse(monitor_summary(np.full(30, 0.0), 0.005)["futile"])     # too few games to call it
        self.assertGreater(cs_upper(np.zeros(100)), 0.0)


if __name__ == "__main__":
    unittest.main()
