"""Fusion: the fit recovers planted book noise and bias, and the fused line shrugs off a stale outlier better than a plain mean."""
import numpy as np

from lab import fusion as F


def planted(rng, P=1500, B=8):
    book = np.tile(np.arange(B), P)
    prop = np.repeat(np.arange(P), B)
    age = rng.uniform(0, 12, P * B)
    beta = rng.normal(0, 0.01, B); beta -= np.median(beta)
    sig = 0.04 * 3.0 ** rng.uniform(-1, 1, B)
    mu = rng.uniform(np.log(30), np.log(250), P)
    s = np.sqrt(sig[book] ** 2 + 1e-4 * age)
    ly = mu[prop] + beta[book] + rng.standard_t(4, P * B) * s
    return F.Obs(ly, book, prop, age, B), beta, sig, mu


def test_fit_recovers_noise_and_bias():
    rng = np.random.default_rng(1)
    o, beta, sig, _ = planted(rng)
    par = F.fit(o, iters=20)
    assert np.corrcoef(par["sigma"], sig)[0, 1] > 0.9
    assert np.sqrt(np.mean((par["beta"] - np.median(par["beta"]) - beta) ** 2)) < 0.005


def test_fused_line_resists_one_stale_quote():
    rng = np.random.default_rng(2)
    o, beta, sig, mu = planted(rng, P=400)
    par = F.fit(o, iters=15)
    ly = o.ly.copy(); ly[::8] += 0.20          # book 0 is stale by 20 percent on every prop
    o2 = F.Obs(ly, o.book, o.prop, o.age, o.B)
    m, _ = F.fused(o2, par)
    mean_est = np.bincount(o.prop, weights=ly - par["beta"][o.book]) / np.bincount(o.prop)
    assert np.mean(np.abs(m - mu)) < np.mean(np.abs(mean_est - mu))
