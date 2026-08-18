"""Focused tests for the Phase 9 model comparison.

Covers the Phase 9 checklist: every comparison model trains, predictions are
binary, probabilities are valid, metrics are calculated correctly, feature
dimensions are consistent, the same dataset split is used, test data is not
used during training/model selection, the saved selected model reloads and
reproduces equivalent predictions, metadata is complete, and the Phase 8
baseline artifact remains intact.
"""

import inspect

import numpy as np
import pytest

from app.ml import compare
from app.ml.config import (
    MODEL_FILE,
    MODEL_METADATA_FILE,
    RANDOM_SEED,
    SELECTED_MODEL_FILE,
    SELECTED_MODEL_METADATA_FILE,
    SELECTED_MODEL_VERSION,
    SPLIT_FILES,
)

ENCODED_FEATURE_COUNT = 55


@pytest.fixture(scope="module")
def processed():
    """Load all processed splits once (exact Phase 7 data)."""
    splits = {}
    for name in SPLIT_FILES:
        splits[name] = compare.baseline.load_split(name)
    return splits


@pytest.fixture(scope="module")
def trained_models(processed):
    """Train each model family on the training partition only."""
    X_train, y_train, _ = processed["train"]
    return {
        "logistic_regression": compare.train_logistic_regression(
            X_train, y_train, seed=RANDOM_SEED
        ),
        "random_forest": compare.train_random_forest(
            X_train, y_train, seed=RANDOM_SEED
        ),
        "gradient_boosting": compare.train_gradient_boosting(
            X_train, y_train, seed=RANDOM_SEED
        ),
    }


class TestCandidateTraining:
    def test_every_model_trains(self, trained_models):
        assert set(trained_models) == {
            "logistic_regression",
            "random_forest",
            "gradient_boosting",
        }
        for model in trained_models.values():
            assert hasattr(model, "predict")
            assert hasattr(model, "predict_proba")
            assert hasattr(model, "n_features_in_")

    def test_feature_dimensions_consistent(self, trained_models, processed):
        X_train, _, _ = processed["train"]
        assert X_train.shape[1] == ENCODED_FEATURE_COUNT
        for model in trained_models.values():
            assert model.n_features_in_ == ENCODED_FEATURE_COUNT

    def test_predictions_are_binary(self, trained_models, processed):
        X_val, y_val, _ = processed["validation"]
        for model in trained_models.values():
            predictions = model.predict(X_val)
            assert predictions.shape == y_val.shape
            assert set(np.unique(predictions)).issubset({0, 1})

    def test_probabilities_are_valid(self, trained_models, processed):
        X_val, y_val, _ = processed["validation"]
        for model in trained_models.values():
            proba = compare.baseline.predict_probabilities(model, X_val)
            assert proba.shape == y_val.shape
            assert not np.isnan(proba).any() and not np.isinf(proba).any()
            assert (proba >= 0.0).all() and (proba <= 1.0).all()
            rows = model.predict_proba(X_val)
            assert np.allclose(rows.sum(axis=1), 1.0)

    def test_metrics_calculated_correctly(self, trained_models, processed):
        X_val, y_val, _ = processed["validation"]
        for model in trained_models.values():
            metrics = compare.baseline.evaluate_model(model, X_val, y_val)
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
            assert cm["true_positive"] + cm["false_negative"] == int(y_val.sum())
            assert cm["true_negative"] + cm["false_positive"] == int(
                (y_val == 0).sum()
            )


class TestSelection:
    def _minimal_results(self):
        return {
            "low_pr": {
                "family": "logistic_regression",
                "display_name": "Low PR",
                "train_metrics": {"roc_auc": 0.60, "average_precision": 0.10},
                "validation_metrics": {
                    "roc_auc": 0.60,
                    "average_precision": 0.10,
                    "precision": 0.1,
                    "recall": 0.4,
                    "f1": 0.16,
                },
            },
            "high_pr": {
                "family": "gradient_boosting",
                "display_name": "High PR",
                "train_metrics": {"roc_auc": 0.90, "average_precision": 0.30},
                "validation_metrics": {
                    "roc_auc": 0.65,
                    "average_precision": 0.15,
                    "precision": 0.1,
                    "recall": 0.5,
                    "f1": 0.16,
                },
            },
        }

    def test_selection_prefers_validation_pr_auc(self):
        selected, rationale = compare.select_model(self._minimal_results())
        assert selected == "high_pr"
        assert "PR-AUC" in rationale

    def test_selection_never_uses_test_data(self):
        signature = inspect.signature(compare.select_model)
        assert "results" in signature.parameters
        assert not any(
            name in signature.parameters for name in ("X_test", "y_test", "test")
        )

    def test_evaluate_candidates_takes_no_test_argument(self):
        signature = inspect.signature(compare.evaluate_candidates)
        assert not any(
            name in signature.parameters for name in ("X_test", "y_test", "test")
        )

    def test_saved_selection_matches_validation_ranking(self):
        metadata = compare.load_selected_metadata()
        ranking = metadata["selection"]["ranking"]
        pr_scores = [row["validation_average_precision"] for row in ranking]
        assert pr_scores == sorted(pr_scores, reverse=True)
        assert metadata["selection"]["selected"] == ranking[0]["candidate"]


class TestSavedArtifact:
    def test_selected_model_saved_and_reloads(self):
        assert SELECTED_MODEL_FILE.exists()
        assert SELECTED_MODEL_METADATA_FILE.exists()
        model = compare.load_selected_model()
        assert model.n_features_in_ == ENCODED_FEATURE_COUNT

    def test_reloaded_model_produces_equivalent_predictions(self, processed):
        X_test, _, _ = processed["test"]
        first = compare.load_selected_model()
        second = compare.load_selected_model()
        proba_first = compare.baseline.predict_probabilities(first, X_test)
        proba_second = compare.baseline.predict_probabilities(second, X_test)
        assert proba_first.shape == (X_test.shape[0],)
        assert np.allclose(proba_first, proba_second, rtol=1e-12, atol=0)

    def test_reloaded_model_reproduces_recorded_test_metrics(self, processed):
        X_test, y_test, _ = processed["test"]
        model = compare.load_selected_model()
        metadata = compare.load_selected_metadata()
        compare.verify_saved_selected_model(model, metadata, X_test, y_test)
        recorded = metadata["metrics"]["test"]
        recomputed = compare.baseline.evaluate_model(model, X_test, y_test)
        for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"):
            assert recomputed[key] == recorded[key]

    def test_metadata_contains_required_fields(self):
        metadata = compare.load_selected_metadata()
        assert metadata["model"]["version"] == SELECTED_MODEL_VERSION
        assert metadata["dataset"]["preprocessing_version"] == "1.0.0"
        assert metadata["dataset"]["feature_count"] == ENCODED_FEATURE_COUNT
        assert metadata["training"]["hyperparameters"]
        assert metadata["training"]["hyperparameters"]["random_state"] == RANDOM_SEED
        assert "validation" in metadata["metrics"]
        assert "test" in metadata["metrics"]
        assert metadata["selection"]["rationale"]
        assert metadata["selection"]["criterion"]

    def test_metadata_contains_no_patient_data(self):
        metadata = compare.load_selected_metadata()
        serialized = repr(metadata)
        assert "patient_nbr" not in serialized
        assert "encounter_id" not in serialized
        for value in metadata["dataset"]["feature_order"]:
            assert isinstance(value, str)  # aggregate feature names only


class TestPhase8Intact:
    def test_baseline_artifact_still_present(self):
        assert MODEL_FILE.exists()
        assert MODEL_METADATA_FILE.exists()
        metadata = compare.baseline.load_model_metadata()
        assert metadata["model"]["version"] == "baseline-logistic-v1"
        assert metadata["metrics"]["test"]["roc_auc"] == 0.635038

    def test_baseline_model_still_loads(self):
        model = compare.baseline.load_model()
        assert model.n_features_in_ == ENCODED_FEATURE_COUNT