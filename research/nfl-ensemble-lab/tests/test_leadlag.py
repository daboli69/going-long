"""Tails Amendment 3: consensus needs at least three books, stale quotes are dropped, the loading estimator and the power gate behave."""
import numpy as np
import pandas as pd

from lab import leadlag as L


def quotes(rows):
    return pd.DataFrame(rows, columns=["gid", "book", "market", "side", "price", "point", "qt"]).assign(qt=lambda d: pd.to_datetime(d["qt"], utc=True))


def test_consensus_is_a_median_over_at_least_three_books_and_ignores_stale_or_later_quotes():
    T = pd.Timestamp("2026-11-08 12:00", tz="UTC")
    r = []
    for i, (b, pt) in enumerate([("a", -3.5), ("b", -3.0), ("c", -4.0)]):
        r.append(("g", b, "spreads", "home", -110, pt, "2026-11-08 10:00"))
    r.append(("g", "d", "spreads", "home", -110, -9.0, "2026-11-08 12:30"))      # after T: ignored
    r.append(("g", "e", "spreads", "home", -110, -9.0, "2026-11-08 03:00"))      # older than 6 hours: ignored
    out = L.book_at(quotes(r), "g", T)
    assert out["spread"] == 3.5 and out["books"] == 3                          # expected home margin is minus the home point
    assert "spread" not in L.book_at(quotes(r[:2]), "g", T)                     # two books are not enough


def test_h2h_is_devigged_before_the_median():
    T = pd.Timestamp("2026-11-08 12:00", tz="UTC")
    r = []
    for b in "abc":
        r += [("g", b, "h2h", "home", -150, None, "2026-11-08 11:00"), ("g", b, "h2h", "away", 130, None, "2026-11-08 11:00")]
    p = L.book_at(quotes(r), "g", T)["winner"]
    assert abs(p - (0.6 / (0.6 + 100 / 230))) < 1e-9


def test_loading_estimator_recovers_a_known_slope_and_power_gate_flags_thin_samples():
    rng = np.random.default_rng(4)
    gap = rng.normal(0, 2, 400)
    assert abs(L.slope(gap, 0.3 * gap + rng.normal(0, 1, 400)) - 0.3) < 0.05
    n = 12
    t = pd.DataFrame({"market": "spread", "h": 24, "stage": "confirm", "usable": True, "gap": rng.normal(0, 1, n), "dB": rng.normal(0, 2, n), "dK": rng.normal(0, 2, n)})
    out = L.power_table(t, np.random.default_rng(1), B=300)
    assert out["spread_24h_confirm"]["informative"] is False                     # 12 games cannot see a loading of 0.15
