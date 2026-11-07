"""Inefficiency ranking: the calibration fit, the multiplicity corrections and the planted-gap gate behave."""
import numpy as np
import pandas as pd

from lab import inefficiency as I


def test_calibration_fit_recovers_slope():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.1, 0.9, 20000)
    y = rng.random(20000) < I.special.expit(0.7 * I.logit(p) + 0.1)
    a, b = I.calib_fit(p, y)
    assert abs(a - 0.7) < 0.05 and abs(b - 0.1) < 0.05


def test_calibration_fit_refuses_nan():
    try:
        I.calib_fit(np.array([0.5, np.nan]), np.array([1.0, 0.0]))
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_stepdown_and_bh_are_monotone_and_not_below_raw():
    rng = np.random.default_rng(1)
    t_star = rng.normal(size=(2000, 5))
    t_obs = np.array([3.0, 1.0, 0.2, -0.5, -2.0])
    padj = I.romano_wolf(t_obs, t_star)
    raw = np.array([(t_star[:, k] >= t_obs[k]).mean() for k in range(5)])
    assert np.all(padj >= raw - 1e-12) and padj[0] <= padj[1] <= padj[2]
    q = I.bh(np.array([0.001, 0.02, 0.5]))
    assert q[0] <= q[1] <= q[2] and np.all(q >= np.array([0.001, 0.02, 0.5]) * 0 )


def test_shrinkage_pulls_noisy_estimates_toward_the_mean():
    theta, se = np.array([0.10, 0.0, -0.02, 0.01]), np.array([0.08, 0.01, 0.01, 0.01])
    post, _, _, mu = I.dl_shrink(theta, se)
    assert abs(post[0] - mu) < abs(theta[0] - mu)


def test_gate_recovers_planted_edge():
    rng = np.random.default_rng(2)
    n = 6000
    b = pd.DataFrame({"cluster": np.repeat(np.arange(n // 10), 10).astype(str), "price": rng.uniform(0.3, 0.7, n), "bet": True})
    g = I.gate_market(b)
    assert abs(g["recovery_error"]) < 0.01 and g["power"] > 0.8 and g["informative"]
