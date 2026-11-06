"""Coherence: the ladder median interpolates, team points use the favorite's margin, the reconciliation slope recovers a planted value."""
import numpy as np
import pandas as pd

from lab import coherence as C
from lab import coherence_lag as B


def test_crossing_interpolates_and_rejects_ladders_that_do_not_bracket_half():
    s = np.array([40.0, 50.0, 60.0])
    assert abs(B.crossing(s, np.array([0.9, 0.5, 0.1])) - 50.0) < 1e-9
    assert abs(B.crossing(s, np.array([0.8, 0.6, 0.2])) - 52.5) < 1e-9
    assert B.crossing(s, np.array([0.9, 0.8, 0.7])) is None
    assert B.crossing(s[:2], np.array([0.9, 0.1])) is None


def test_team_points_favorite_gets_the_larger_share():
    m = pd.DataFrame({"gid": ["2026_01_AAA_BBB"] * 2, "series": ["KXNFLTOTAL", "KXNFLSPREAD"], "team": [None, "BBB"], "pid": [None, None], "h": [24, 24], "med": [48.0, 6.0]})
    t = B.team_points(m).set_index("team")["tp"]
    assert t["BBB"] == 27.0 and t["AAA"] == 21.0


def test_reconciliation_slope_recovers_planted_value():
    rng = np.random.default_rng(5)
    n = 3000
    tg = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "team": "A", "season": 2022, "fQ": rng.uniform(150, 300, n), "k": 4})
    tg["Rf"] = tg["fQ"] * 0.7 + rng.normal(0, 25, n)
    share = {k: 0.2 for k in C.K_BUCKETS}
    c = C.incoherence(tg, share)
    tg["yQ"] = tg["fQ"] - 0.4 * c + rng.normal(0, 30, n)
    tg["Ry"] = tg["yQ"] * 0.8
    r = pd.DataFrame({"game_id": tg["game_id"], "team": "A", "season": 2022, "f": tg["Rf"], "Rf": tg["Rf"], "y": tg["Rf"] + 0.4 * c + rng.normal(0, 30, n)})
    b = C.fit_slopes(tg, r, share)
    assert abs(b["b_Q"] + 0.4) < 0.06 and abs(b["b_R"] - 0.4) < 0.06


def test_pick_snaps_needs_three_distinct_snapshots_within_tolerance():
    from lab import coherence_book as K
    kick = pd.Timestamp("2026-11-08 18:00", tz="UTC")
    mk = lambda hrs: {"gk": "A@B2026-11-08", "snap": kick - pd.Timedelta(hours=hrs), "kick": kick, "home": "A", "away": "B", "home_spread": -3.0, "total": 45.0}
    ok = K.pick_snaps(pd.DataFrame([mk(41), mk(24), mk(15.5), mk(2)]))
    assert len(ok) == 1
    assert K.pick_snaps(pd.DataFrame([mk(41), mk(24), mk(10)])).empty
