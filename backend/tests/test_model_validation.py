"""Focused tests for the Phase 10 model validation and calibration.

Covers the Phase 10 checklist: threshold metrics calculate correctly, the
threshold range is handled correctly, threshold selection uses only crafted
rows (no test labels) and is reproducible, calibration metrics calculate
correctly, the Brier score is valid, calibrated probabilities stay in [0, 1],
and the saved validation configuration can be loaded.
"""

import inspect
import json

import numpy as np
import pytest
from sklearn.metrics import brier_score_loss

from app.ml import validate
from app.ml.config import (
    SELECTED_CALIBRATOR_FILE,
    VALIDATION_CONFIG_FILE,
    VALIDATION_CONFIG_VERSION,
)


@pytest.fixture(scope="module")
def y_proba():
    y = np.array([0, 0, 0, 1, 1, 0, 1, 0, 1, 1, 0, 0])
    proba = np.array(
        [0.05, 0.2, 0.3, 0.1, 0.55, 0.7, 0.45, 0.15, 0.9, 0.25, 0.6, 0.35]
    )
    return y, proba


class TestThresholdMetrics:
    def test_metrics_at_threshold_correct(self):
        y = np.array([0, 0, 1, 1])
        proba = np.array([0.1, 0.6, 0.7, 0.9])
        metrics = validate.metrics_at_threshold(y, proba, 0.5)
        # predictions: 0,1,1,1 -> TP=2 (labels 1), FP=1, TN=1, FN=0
        assert metrics["confusion_matrix"] == {
            "true_positive": 2,
            "true_negative": 1,
            "false_positive": 1,
            "false_negative": 0,
        }
        assert metrics["precision"] == pytest.approx(2 / 3)
        assert metrics["recall"] == pytest.approx(1.0)
        assert metrics["f1"] == pytest.approx(0.8)
        assert metrics["specificity"] == pytest.approx(0.5)
        assert metrics["false_positive_rate"] == pytest.approx(0.5)
        assert metrics["false_negative_rate"] == pytest.approx(0.0)

    def test_metrics_consistency_with_sklearn_confusion_matrix(self, y_proba):
        y, proba = y_proba
        for threshold in (0.1, 0.25, 0.5, 0.8):
            metrics = validate.metrics_at_threshold(y, proba, threshold)
            predictions = (proba >= threshold).astype(int)
            tn, fp, fn, tp = (
                validate.confusion_matrix(y, predictions, labels=[0, 1]).ravel()
            )
            assert metrics["confusion_matrix"] == {
                "true_positive": int(tp),
                "true_negative": int(tn),
                "false_positive": int(fp),
                "false_negative": int(fn),
            }

    def test_threshold_range_handled(self, y_proba):
        y, proba = y_proba
        rows = validate.threshold_analysis(y, proba)
        thresholds = [row["threshold"] for row in rows]
        assert thresholds == sorted(thresholds)
        assert thresholds[0] == pytest.approx(0.05)
        assert thresholds[-1] == pytest.approx(0.85)
        for row in rows:
            for key in (
                "precision",
                "recall",
                "f1",
                "specificity",
                "false_positive_rate",
                "false_negative_rate",
                "confusion_matrix",
            ):
                assert key in row

    def test_probability_range_validated(self):
        with pytest.raises(validate.ValidationError):
            validate.metrics_at_threshold(
                np.zeros(3), np.array([0.5, 1.2, 0.3]), 0.5
            )


class TestThresholdSelection:
    def _row(self, threshold, f1=0.0, recall=0.0, precision=0.0, specificity=1.0):
        return {
            "threshold": threshold,
            "f1": f1,
            "recall": recall,
            "precision": precision,
            "specificity": specificity,
        }

    def test_selection_picks_max_f1_and_prefers_higher_tiebreak(self):
        rows = [
            self._row(0.1, f1=0.20, recall=0.7, precision=0.12, specificity=0.5),
            self._row(0.2, f1=0.25, recall=0.4, precision=0.20, specificity=0.8),
            self._row(0.3, f1=0.25, recall=0.3, precision=0.25, specificity=0.9),
            self._row(0.5, f1=0.15, recall=0.1, precision=0.50, specificity=0.99),
        ]
        selected, rationale = validate.select_threshold(rows)
        assert selected == 0.3  # max F1 (0.25) with higher-threshold tie-break
        assert "prototype review threshold" in rationale

    def test_selection_is_reproducible(self, y_proba):
        y, proba = y_proba
        rows = validate.threshold_analysis(y, proba)
        first, _ = validate.select_threshold(rows)
        second, _ = validate.select_threshold(rows)
        assert first == second

    def test_selection_takes_no_test_attributes(self):
        signature = inspect.signature(validate.select_threshold)
        assert "rows" in signature.parameters
        assert not any(
            name in signature.parameters for name in ("X_test", "y_test", "test")
        )
        sig_analysis = inspect.signature(validate.threshold_analysis)
        assert "X_test" not in sig_analysis.parameters
        assert "y_test" not in sig_analysis.parameters


class TestCalibration:
    def test_brier_score_valid(self, y_proba):
        y, proba = y_proba
        analysis = validate.calibration_analysis(y, proba)
        assert 0.0 <= analysis["brier_score"] <= 1.0
        assert np.isfinite(analysis["brier_score"])
        assert analysis["brier_score"] == pytest.approx(
            float(brier_score_loss(y, proba)), abs=1e-6
        )

    def test_ece_valid(self, y_proba):
        y, proba = y_proba
        ece = validate.expected_calibration_error(y, proba, n_bins=10)
        assert 0.0 <= ece <= 1.0
        assert np.isfinite(ece)

    def test_calibration_curve_valid(self, y_proba):
        y, proba = y_proba
        analysis = validate.calibration_analysis(y, proba, n_bins=10)
        curve = analysis["calibration_curve"]
        assert len(curve) == 10
        assert sum(row["count"] for row in curve) == len(y)
        for row in curve:
            assert 0.0 <= row["mean_predicted_probability"] <= 1.0
            assert 0.0 <= row["observed_frequency"] <= 1.0

    def test_calibrated_probabilities_stay_in_unit_interval(self, y_proba):
        y, proba = y_proba
        for method in ("sigmoid", "isotonic"):
            calibrator = validate.fit_calibrator(proba, y, method)
            calibrated = validate.calibrate_probabilities(proba, calibrator, method)
            assert calibrated.shape == proba.shape
            assert not np.isnan(calibrated).any()
            assert not np.isinf(calibrated).any()
            assert (calibrated >= 0.0).all() and (calibrated <= 1.0).all()


class TestSavedConfig:
    def test_config_saved_and_loads(self):
        assert VALIDATION_CONFIG_FILE.exists()
        config = validate.load_validation_config()
        assert config["artifact"]["version"] == VALIDATION_CONFIG_VERSION

    def test_config_contains_frozen_fields(self):
        config = validate.load_validation_config()
        assert config["threshold"]["clinically_validated"] is False
        assert config["threshold"]["label"] == "prototype review threshold"
        assert config["calibration"]["method"] in ("none", "sigmoid", "isotonic")
        assert config["model"]["version"] == "selected-model-v1"
        assert config["metrics"]["validation"]["threshold"] == pytest.approx(
            config["threshold"]["selected"]
        )
        assert config["metrics"]["test"]["at_selected_threshold"]
        assert config["metrics"]["test"]["at_default_0_50_threshold"]

    def test_frozen_threshold_and_calibration_reproducible(self):
        config = validate.load_validation_config()
        assert config["threshold"]["selected"] == 0.1
        assert config["calibration"]["method"] == "sigmoid"
        assert config["metrics"]["test"]["at_selected_threshold"]["f1"] == pytest.approx(
            0.241006, abs=1e-6
        )

    def test_test_evaluated_after_selection_invariant(self):
        config = validate.load_validation_config()
        # The same frozen threshold is recorded in the validation block and the
        # single test evaluation block.
        validation = config["metrics"]["validation"]
        test = config["metrics"]["test"]["at_selected_threshold"]
        assert validation["threshold"] == test["threshold"]

    def test_config_contains_no_patient_data(self):
        config = validate.load_validation_config()
        serialized = json.dumps(config)
        assert "patient_nbr" not in serialized
        assert "encounter_id" not in serialized

    def test_calibrator_artifact_loads(self):
        assert SELECTED_CALIBRATOR_FILE.exists()
        calibrator = validate.load_calibrator()
        assert hasattr(calibrator, "predict_proba") or hasattr(calibrator, "predict")