import joblib
import numpy as np
import pytest

from lab import config, ensemble as ens, metrics as M, models, training


@pytest.fixture(scope="module")
def xy():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(400, 6))
    X[rng.random(X.shape) < 0.05] = np.nan
    logit = 1.2 * np.nan_to_num(X[:, 0]) - 0.8 * np.nan_to_num(X[:, 1])
    y = (rng.random(400) < 1 / (1 + np.exp(-logit))).astype(float)
    margin = 7 * logit + rng.normal(0, 5, 400)
    return X, y, margin


def test_chronological_protocol_constants():
    assert max(config.DEV_SEASONS) < min(config.VALIDATION_SEASONS) < min(config.TEST_SEASONS) < config.PROSPECTIVE_FROM
    assert set(config.TUNING_FOLDS) <= set(config.DEV_SEASONS)
    assert [training.split_of(s) for s in (2017, 2023, 2025, 2026)] == ["development", "validation", "test", "prospective"]


@pytest.mark.parametrize("key", ens.MODEL_KEYS)
def test_each_classifier_trains_and_serializes(key, xy, tmp_path):
    X, y, _ = xy
    m = models.make("clf", key, models.grid("clf", key)[0]).fit(X[:300], y[:300])
    p = m.predict_proba(X[300:])[:, 1]
    assert p.shape == (100,) and np.all((p >= 0) & (p <= 1))
    joblib.dump(m, tmp_path / "m.joblib")
    np.testing.assert_allclose(joblib.load(tmp_path / "m.joblib").predict_proba(X[300:])[:, 1], p)


@pytest.mark.parametrize("key", ens.MODEL_KEYS)
def test_each_margin_model_trains(key, xy):
    X, _, margin = xy
    m = models.make("reg", key, models.grid("reg", key)[0]).fit(X[:300], margin[:300])
    pred = m.predict(X[300:])
    assert pred.shape == (100,) and np.isfinite(pred).all()
    assert M.margin_summary(margin[300:], pred)["mae"] < np.mean(np.abs(margin[300:] - margin[:300].mean())) * 1.2


def test_preprocessing_fit_on_training_rows_only(xy):
    X, y, _ = xy
    m = models.make("clf", "logreg", {"C": 1.0}).fit(X[:200], y[:200])
    med = np.nanmedian(X[:200], axis=0)
    np.testing.assert_allclose(m.named_steps["impute"].statistics_, med)
    filled = np.where(np.isnan(X[:200]), med, X[:200])
    np.testing.assert_allclose(m.named_steps["scale"].mean_, filled.mean(axis=0))


@pytest.mark.parametrize("kind", ["clf", "reg"])
def test_neural_network_reproducible(kind, xy):
    X, y, margin = xy
    target = y if kind == "clf" else margin
    a = models.make(kind, "mlp", models.grid(kind, "mlp")[0]).fit(X, target)
    b = models.make(kind, "mlp", models.grid(kind, "mlp")[0]).fit(X, target)
    fa = a.predict_proba(X)[:, 1] if kind == "clf" else a.predict(X)
    fb = b.predict_proba(X)[:, 1] if kind == "clf" else b.predict(X)
    np.testing.assert_array_equal(fa, fb)


def test_single_layer_is_linear_logistic_family(xy):
    X, y, _ = xy
    m = models.make("clf", "single_layer", {"weight_decay": 1e-3}).fit(X, y)
    w, b = m.named_steps["model"].linear_weights()
    Xs = m.named_steps["scale"].transform(m.named_steps["impute"].transform(X))
    np.testing.assert_allclose(1 / (1 + np.exp(-(Xs @ w + b))), m.predict_proba(X)[:, 1], rtol=1e-5)
    lr = models.make("clf", "logreg", {"C": 1.0}).fit(X, y)
    assert np.corrcoef(lr.predict_proba(X)[:, 1], m.predict_proba(X)[:, 1])[0, 1] > 0.95


@pytest.mark.parametrize("method", ["platt", "isotonic"])
def test_calibration_repairs_overconfidence(method):
    rng = np.random.default_rng(3)
    true = rng.uniform(0.2, 0.8, 4000)
    y = (rng.random(4000) < true).astype(float)
    over = 1 / (1 + np.exp(-3 * np.log(true / (1 - true))))  # overconfident
    cal = training.Calibrator(method).fit(over[:3000], y[:3000])
    out = cal.transform(over[3000:])
    assert np.all((out >= 0) & (out <= 1))
    assert M.log_loss(y[3000:], out) < M.log_loss(y[3000:], over[3000:])
    assert np.array_equal(training.Calibrator("none").fit(over, y).transform(over), over)


def test_metrics_known_values():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.8, 0.2, 0.6, 0.4])
    assert M.accuracy(y, p) == 1.0
    assert M.brier(y, p) == pytest.approx((0.04 + 0.04 + 0.16 + 0.16) / 4)
    assert M.log_loss(y, np.full(4, 0.5)) == pytest.approx(np.log(2))
    lo, hi = M.bootstrap_ci(M.brier, y, p, n_boot=200)
    assert lo <= M.brier(y, p) <= hi
    assert M.calibration_table(y, p)["n"].sum() == 4
