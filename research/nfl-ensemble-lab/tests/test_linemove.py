"""Linemove: the drift coefficient is the correlation of move and error, the spread scale is recovered, the gate flags small samples."""
import numpy as np
import pandas as pd

from lab import linemove as L


def frame(n, slope, rng):
    m = rng.normal(0, 6, n)
    mv = rng.normal(0, 1, n)
    e = slope * mv + rng.normal(0, 13, n)
    t = rng.normal(45, 4, n)
    return pd.DataFrame({"m_close": m, "M": mv, "E": e, "Mt": mv, "Et": e, "R": np.abs(rng.normal(1, 1, n)), "Total Score Close": t,
                         "home_win": (m + rng.normal(0, 12, n) > 0).astype(float), "p_ml": 1 / (1 + np.exp(-m / 6))})


def test_t1_coefficient_matches_planted_correlation_and_zero_when_none():
    rng = np.random.default_rng(1)
    assert abs(L.coef("T1", frame(20000, 3.0, rng), 12.0) - 3.0 / np.sqrt(9 + 169)) < 0.02
    assert abs(L.coef("T1", frame(20000, 0.0, rng), 12.0)) < 0.02


def test_sigma_fit_recovers_scale_and_gate_flags_small_samples():
    rng = np.random.default_rng(2)
    d = frame(6000, 0.0, rng)
    assert abs(L.sigma_fit(d) - 12.0) < 1.2
    g = L.gate(frame(150, 0.0, rng), 12.0, np.random.default_rng(3))
    assert not g["T1"]["informative"]
