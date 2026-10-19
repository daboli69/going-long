import numpy as np
import pandas as pd
import pytest

from lab.models import TorchRegressor
from lab.props.ensemble.production import completed_cutoff, season_weight_map
from lab.props.models import recency_resample_games


def test_last_completed_week_excludes_partial_and_later_weeks():
    games = pd.DataFrame({"season": 2026, "game_type": "REG", "week": [1, 1, 2, 2, 3],
        "completed": [True, True, True, False, True], "gameday": ["2026-09-01"] * 5,
        "kickoff_utc": pd.to_datetime(["2026-09-01T12:00Z"] * 5)})
    assert completed_cutoff(games, pd.Timestamp("2026-10-01T00:00Z"))["training_last_completed_week"] == 1
    assert season_weight_map([2026, 2025, 2024, 2020]) == {2026: 1., 2025: .6, 2024: .35, 2020: .35}


def test_weighted_structural_resampling_preserves_whole_games():
    plays = pd.DataFrame({"game_id": ["a"] * 3 + ["b"] * 2, "play_id": [1, 2, 3, 1, 2],
                           "season": [2020] * 3 + [2021] * 2})
    sample = recency_resample_games(plays, {2020: .35, 2021: 1.})
    assert sample["game_id"].nunique() == 2
    for game, d in sample.groupby("game_id"):
        original = plays[plays["game_id"] == game.split("__phase10_")[0]]
        assert d["play_id"].tolist() == original["play_id"].tolist()


def test_torch_default_is_unchanged_and_sample_weights_are_used():
    X = np.zeros((4, 1))
    y = np.array([0., 0., 10., 10.])
    params = dict(hidden=(), dropout=0, max_epochs=30, weight_decay=0, lr=.05, seed=1)
    a = TorchRegressor(**params).fit(X, y)
    b = TorchRegressor(**params).fit(X, y, sample_weight=None)
    np.testing.assert_array_equal(a.predict(X), b.predict(X))
    weighted = TorchRegressor(**params).fit(X, y, sample_weight=[.1, .1, 1, 1])
    assert weighted.predict(X).mean() > a.predict(X).mean()
    with pytest.raises(ValueError, match="Invalid sample weights"):
        TorchRegressor(**params).fit(X, y, sample_weight=[1, 2])
