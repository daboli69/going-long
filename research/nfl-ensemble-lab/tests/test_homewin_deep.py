"""Deep home-win model unit tests (synthetic; the real-data leakage check runs inside the pipeline)."""
import numpy as np
import pandas as pd
import pytest

from lab import homewin_deep as h
from lab import homewin_eval as ev


def test_ridge_recovers_ratings_and_shrinks_to_prior():
    rng = np.random.default_rng(1)
    teams = list("ABCDEFGH")
    o = dict(zip(teams, rng.normal(0, 0.1, 8)))
    d = dict(zip(teams, rng.normal(0, 0.1, 8)))
    rows = []
    for _ in range(400):
        t, u = rng.choice(teams, 2, replace=False)
        rows.append({"team": t, "opp": u, "home_sign": 1, "n_pass": 35, "pass_epa": 0.02 + o[t] + d[u] + 0.03 + rng.normal(0, 0.01)})
    fit = h._ridge(pd.DataFrame(rows), "pass_epa", teams, None)
    est = np.array([fit[t][0] for t in teams])
    assert np.corrcoef(est, [o[t] for t in teams])[0, 1] > 0.95
    empty = h._ridge(pd.DataFrame(columns=["team", "opp", "home_sign", "n_pass", "pass_epa"]), "pass_epa", teams,
                     {"A": (0.2, -0.1)})
    assert empty["A"] == pytest.approx((h.RIDGE_RHO * 0.2, h.RIDGE_RHO * -0.1))


def _quotes(rows):
    q = pd.DataFrame(rows, columns=["home", "away", "commence_time", "book", "side", "price", "quote_time", "committed_at"])
    for c in ("commence_time", "quote_time", "committed_at"):
        q[c] = pd.to_datetime(q[c], utc=True)
    return q


def test_market_uses_only_quotes_seen_before_cutoff():
    k = pd.Timestamp("2026-10-04 17:00", tz="UTC")
    early = [("A", "B", k, "bk", "home", -150, "2026-10-03 12:00", "2026-10-03 12:05"),
             ("A", "B", k, "bk", "away", 130, "2026-10-03 12:00", "2026-10-03 12:05")]
    late_commit = [("A", "B", k, "bk", "home", -400, "2026-10-03 13:00", "2026-10-04 18:00"),
                   ("A", "B", k, "bk", "away", 320, "2026-10-03 13:00", "2026-10-04 18:00")]
    q = _quotes(early + late_commit)
    p = h.market_probability(q, "A", "B", k, k)
    ph, pa = 150 / 250, 100 / 230
    assert p["p_home"] == pytest.approx(ph / (ph + pa))
    assert np.isnan(h.market_probability(q, "A", "B", k, pd.Timestamp("2026-10-03 12:01", tz="UTC"))["p_home"])


def test_platt_needs_history_and_stats_are_sane():
    p = np.array([0.6, 0.7])
    assert np.array_equal(h.platt(np.full(10, 0.5), np.ones(10), p), p)
    rng = np.random.default_rng(0)
    d = rng.normal(-0.01, 0.05, 2000)
    cl = np.repeat(np.arange(200), 10)
    lo, hi = ev.cluster_boot(d, cl, 0.05)
    assert lo < d.mean() < hi
    assert ev.dm_test(np.zeros(2000) + rng.normal(0, 1e-9, 2000), cl, np.arange(2000))["p"] > 0.01
