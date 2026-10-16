import numpy as np
import pytest

from lab import ensemble as ens


def P(*ps):
    return dict(zip(ens.MODEL_KEYS, ps))


def test_vote_counts_and_majority():
    v = ens.vote(P(0.6, 0.7, 0.55, 0.4, 0.45, 0.8))
    assert (v["home_votes"], v["away_votes"], v["winner"], v["tie"], v["unanimous"]) == (4, 2, "home", False, False)
    assert v["label"] == "4-2"


def test_unanimous_is_not_certainty():
    v = ens.vote(P(0.51, 0.52, 0.53, 0.51, 0.52, 0.55))
    assert v["unanimous"] and v["label"] == "6-0"
    assert np.mean([0.51, 0.52, 0.53, 0.51, 0.52, 0.55]) < 0.6  # probability stays modest


def test_three_three_tie_broken_by_average_and_flagged():
    v = ens.vote(P(0.9, 0.8, 0.7, 0.45, 0.4, 0.45))
    assert v["tie"] and v["home_votes"] == v["away_votes"] == 3
    assert v["winner"] == "home" and v["label"] == "3-3 tie"
    v2 = ens.vote(P(0.55, 0.51, 0.52, 0.1, 0.2, 0.3))
    assert v2["tie"] and v2["winner"] == "away"


def test_missing_model_is_not_counted():
    v = ens.vote(P(0.6, np.nan, 0.6, 0.6, 0.4, 0.4))
    assert v["n_models"] == 5 and v["home_votes"] == 3


def test_equal_and_weighted_average():
    Pm = np.array([[0.6, 0.8], [0.2, 0.4]])
    np.testing.assert_allclose(ens.equal_average(Pm), [0.7, 0.3])
    np.testing.assert_allclose(ens.weighted_average(Pm, np.array([1.0, 0.0])), [0.6, 0.2])


def test_skill_weights():
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.5).astype(float)
    good = np.clip(y * 0.7 + (1 - y) * 0.3, 0, 1)
    coin = np.full(500, 0.5)
    w = ens.skill_weights(np.column_stack([good, coin]), y)
    assert w.sum() == pytest.approx(1.0) and w[0] == pytest.approx(1.0)
    bad = np.column_stack([1 - good, coin])
    np.testing.assert_allclose(ens.skill_weights(bad, y), [0.5, 0.5])


def test_stacker_outputs_probabilities():
    rng = np.random.default_rng(0)
    y = (rng.random(300) < 0.5).astype(float)
    Pm = np.clip(np.column_stack([y * 0.6 + 0.2 + rng.normal(0, .1, 300) for _ in range(6)]), 0.01, 0.99)
    p = ens.stack_predict(ens.fit_stacker(Pm, y), Pm)
    assert np.all((p > 0) & (p < 1))
