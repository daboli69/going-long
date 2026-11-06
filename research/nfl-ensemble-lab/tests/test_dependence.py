"""Dependence test: copula fits recover a planted correlation, the copula beats independence when dependence exists and does not when it does not."""
import numpy as np
import pandas as pd
from scipy import stats

from lab import dependence as D


def planted(n, rho, rng):
    z = rng.standard_normal((n, 2))
    z[:, 1] = rho * z[:, 0] + np.sqrt(1 - rho ** 2) * z[:, 1]
    return stats.norm.cdf(z[:, 0]), stats.norm.cdf(z[:, 1]), z


def test_gaussian_fit_recovers_planted_correlation_and_is_chosen():
    u, v, _ = planted(4000, 0.3, np.random.default_rng(1))
    f = D.fit_all(u, v)
    assert abs(f["gaussian"]["par"][0] - 0.3) < 0.04
    assert f["chosen"] in ("gaussian", "t")


def test_clayton_logpdf_integrates_to_one_and_sampler_matches_its_dependence():
    g = (np.arange(400) + 0.5) / 400
    u, v = np.meshgrid(g, g)
    assert abs(np.exp(D.logpdf("clayton", (2.0,), u.ravel(), v.ravel())).mean() - 1) < 0.03
    z = D.sample("clayton", (2.0,), 3000, 4, np.random.default_rng(2)).reshape(-1, 2)
    tau = stats.kendalltau(z[:, 0], z[:, 1])[0]
    assert abs(tau - 2.0 / (2.0 + 2)) < 0.03


def test_scores_prefer_the_true_dependence_and_not_independence_when_none_exists():
    rng = np.random.default_rng(3)
    for rho, should_win in ((0.5, True), (0.0, False)):
        u, v, _ = planted(1500, rho, rng)
        _, _, zt = planted(800, rho, rng)
        ev = D.evaluate(u, v, zt, np.arange(800), rng, 200)
        t, p = D.dm_p(ev["g_es"])
        assert (p < 0.01) == should_win


def test_scale_structure_and_planted_z_shapes():
    s = pd.DataFrame({"game_id": ["g1", "g1", "g2"], "team": ["A", "B", "A"], "n": [2, 3, 1]})
    s2 = D.scale_structure(s, 3)
    assert s2["game_id"].nunique() == 6
    z, g = D.planted_z(s, 0.2, np.random.default_rng(4))
    assert z.shape == (6, 2) and len(g) == 6
