"""Focused tests for the Phase 8 baseline Logistic Regression model.

Covers the Phase 8 checklist: prepared data loads, correct target, training
succeeds, binary predictions, probabilities, reload equivalence, feature
dimension match, metrics can be computed, and no test data participates in
training.
"""

import numpy as np
import pytest

from app.ml import train
from app.ml.config import (
    MODEL_FILE,
    MODEL_METADATA_FILE,
    RANDOM_SEED,
    SPLIT_FILES,
)

ENCODED_FEATURE_COUNT = 55


@pytest.fixture(scope="module")
def processed():
    """Load all processed splits once."""
    splits = {}
    for name in SPLIT_FILES:
        splits[name] = train.load_split(name)
    return splits


@pytest.fixture(scope="module")
def fitted_model(processed):
    X_train, y_train, _ = processed["train"]
    return train.train_logistic_regression(X_train, y_train, seed=RANDOM_SEED)


@pytest.fixture(scope="module")
def baseline_summary():
    return train.train_baseline(seed=RANDOM_SEED)


class TestPreparedData:
    def test_splits_load(self, processed):
        for name in ("train", "validation", "test"):
            X, y, identifiers = processed[name]
            assert X.shape[1] == ENCODED_FEATURE_COUNT
            assert len(X) == len(y) == len(identifiers)
            assert identifiers.columns.tolist() == ["encounter_id", "patient_nbr"]

    def test_correct_target_used(self, processed):
        for name in ("train", "validation", "test"):
            _, y, _ = processed[name]
            assert set(np.unique(y)).issubset({0, 1})
            assert y.dtype == np.int64
            assert 0.08 < y.mean() < 0.15  # imbalanced positive class


class TestTraining:
    def test_model_trains_successfully(self, fitted_model):
        assert hasattr(fitted_model, "coef_")
        assert fitted_model.coef_.shape == (1, ENCODED_FEATURE_COUNT)

    def test_feature_dimensions_match(self, fitted_model):
        assert fitted_model.n_features_in_ == ENCODED_FEATURE_COUNT
        metadata = train.load_dataset_metadata()
        assert metadata["encoded_feature_count"] == fitted_model.n_features_in_

    def test_model_produces_binary_predictions(self, fitted_model, processed):
        X_test, y_test, _ = processed["test"]
        predictions = fitted_model.predict(X_test)
        assert predictions.shape == y_test.shape
        assert set(np.unique(predictions)).issubset({0, 1})

    def test_model_produces_probabilities(self, fitted_model, processed):
        X_test, y_test, _ = processed["test"]
        proba = train.predict_probabilities(fitted_model, X_test)
        assert proba.shape == y_test.shape
        assert not np.isnan(proba).any() and not np.isinf(proba).any()
        assert (proba >= 0.0).all() and (proba <= 1.0).all()
        rows = fitted_model.predict_proba(X_test)
        assert np.allclose(rows.sum(axis=1), 1.0)

    def test_metrics_can_be_calculated(self, fitted_model, processed):
        X_test, y_test, _ = processed["test"]
        metrics = train.evaluate_model(fitted_model, X_test, y_test)
        for key in (
            "accuracy",
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "average_precision",
        ):
            assert key in metrics
            assert np.isfinite(metrics[key])
        cm = metrics["confusion_matrix"]
        assert set(cm) == {"true_positive", "true_negative", "false_positive", "false_negative"}
        assert cm["true_positive"] + cm["false_negative"] == int(y_test.sum())
        assert cm["true_negative"] + cm["false_positive"] == int((y_test == 0).sum())


class TestArtifact:
    def test_model_saved_and_reloads(self, baseline_summary):
        assert MODEL_FILE.exists()
        assert MODEL_METADATA_FILE.exists()
        reloaded = train.load_model()
        assert reloaded.n_features_in_ == ENCODED_FEATURE_COUNT

    def test_reloaded_model_equivalent(self, baseline_summary, processed):
        X_test, _, _ = processed["test"]
        first = train.load_model()
        second = train.load_model()
        proba_first = train.predict_probabilities(first, X_test)
        proba_second = train.predict_probabilities(second, X_test)
        assert proba_first.shape == (X_test.shape[0],)
        assert np.allclose(proba_first, proba_second, rtol=1e-12, atol=0)
        assert not np.isnan(proba_first).any()

    def test_saved_model_reproduces_recorded_metrics(self, baseline_summary, processed):
        X_test, y_test, _ = processed["test"]
        model = train.load_model()
        metadata = train.load_model_metadata()
        train.verify_saved_model(model, metadata, X_test, y_test)
        recorded = metadata["metrics"]["test"]
        recomputed = train.evaluate_model(model, X_test, y_test)
        for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"):
            assert recomputed[key] == recorded[key]


class TestNoLeakage:
    def test_training_depends_only_on_train(self, processed):
        X_train, y_train, _ = processed["train"]
        model_a = train.train_logistic_regression(X_train, y_train, seed=RANDOM_SEED)
        model_b = train.train_logistic_regression(X_train, y_train, seed=RANDOM_SEED)
        assert np.allclose(model_a.coef_, model_b.coef_)
        assert np.allclose(model_a.intercept_, model_b.intercept_)

    def test_training_api_takes_no_test_data(self):
        import inspect

        signature = inspect.signature(train.train_logistic_regression)
        assert "X" in signature.parameters and "y" in signature.parameters
        assert not any(
            name in signature.parameters
            for name in ("X_test", "y_test", "test")
        )

    def test_model_was_fit_on_train_size(self, baseline_summary, processed):
        X_train, y_train, _ = processed["train"]
        model = train.load_model()
        assert model.n_features_in_ == X_train.shape[1]
        # Training metrics are defined on the training partition.
        assert baseline_summary["train_metrics"]["positive_prevalence"] == pytest.approx(
            float(y_train.mean()), abs=1e-6
        )