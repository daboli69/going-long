"""Tails Amendment 2: the ladder fitter recovers a known width and tail weight, handles tick censoring and non-monotone prices."""
import numpy as np
import pytest

from lab import tails_ladder as T


def ladder(mu, sigma, df, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    x = np.arange(-24.5, 25, 1.0)
    F = np.clip(np.round(T.tcdf(x, mu, sigma, df) + rng.normal(0, noise, len(x)), 2), 0.01, 0.99)
    return x, F


def test_fit_recovers_location_and_scale():
    x, F = ladder(3.0, 12.0, 30.0)
    f = T.fit_ladder(x, F)
    assert f["mu"] == pytest.approx(3.0, abs=0.3) and f["sigma"] == pytest.approx(12.0, rel=0.05)


def test_fit_separates_heavy_from_light_tails():
    heavy = T.fit_ladder(*ladder(0.0, 11.0, 4.0))
    light = T.fit_ladder(*ladder(0.0, 12.5, 60.0))
    assert heavy["df"] < 10 < light["df"]


def test_a_thin_ladder_is_dropped_not_guessed():
    assert T.fit_ladder(np.array([-3.5, 0.5, 3.5]), np.array([0.3, 0.5, 0.7])) is None


def test_isotonic_step_counts_violations_and_still_fits():
    x, F = ladder(0.0, 12.0, 20.0)
    F = F.copy()
    F[20], F[21] = F[21], F[20] - 0.03          # break monotonicity
    f = T.fit_ladder(x, F)
    assert f is not None and f["violations"] >= 1


def test_t_mean_absolute_deviation_matches_simulation():
    rng = np.random.default_rng(1)
    assert np.abs(rng.standard_t(8, 400000)).mean() == pytest.approx(T.tmad(8), rel=0.01)


def test_archive_is_write_once(tmp_path, monkeypatch):
    import pandas as pd
    monkeypatch.setattr(T, "ARCHIVE", tmp_path / "ladders")
    monkeypatch.setattr(T.tails, "OUT", tmp_path)
    p = T.ARCHIVE
    p.mkdir(parents=True)
    (p / "2026_w09.json").write_text('{"week": 9, "sha256": "x", "rungs": []}')
    assert T.archive_ladders(9)["sha256"] == "x"        # an existing file is returned untouched, no network used
