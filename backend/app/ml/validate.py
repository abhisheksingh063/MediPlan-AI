"""Phase 10 validation and calibration for the Phase 9 selected model.

The selected Logistic Regression model (``models/selected_model_v1.joblib``)
is validated against the Phase 7 validation partition: probability thresholds
are analysed and a prototype review threshold is selected, and probability
calibration (Platt/sigmoid vs isotonic) is assessed. Every decision is made on
training + validation data only; the Phase 7 test partition is evaluated
exactly once, after the configuration is frozen, and the resulting
configuration is persisted to ``models/model_validation_v1.json``.

The model estimates P(early (<30-day) readmission) for a diabetes-coded
encounter. It is a research/prototype risk estimator — not a diagnosis,
prescription or treatment decision, and no clinical validity is claimed.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix

from app.ml import compare
from app.ml.config import (
    DATASET_NAME,
    DATASET_URL,
    PREPROCESSING_VERSION,
    SELECTED_CALIBRATOR_FILE,
    SELECTED_MODEL_FILE,
    SELECTED_MODEL_METADATA_FILE,
    SELECTED_MODEL_VERSION,
    TARGET_DERIVED,
    VALIDATION_CONFIG_FILE,
    VALIDATION_CONFIG_VERSION,
)

PREDICTION_THRESHOLD = compare.PREDICTION_THRESHOLD
NUMERIC_TOLERANCE = compare.NUMERIC_TOLERANCE

# Validation-only default thresholds (finer range than the Phase 10 example).
DEFAULT_THRESHOLDS = np.round(np.arange(0.05, 0.90, 0.05), 2).tolist()
CALIBRATION_BINS = 10
CALIBRATION_IMPROVEMENT_TOLERANCE = 1e-4


class ValidationError(RuntimeError):
    """Raised when a validation/calibration sanity check fails."""


def metrics_at_threshold(
    y: np.ndarray, proba: np.ndarray, threshold: float
) -> dict:
    """Compute classification metrics for one decision threshold."""
    if proba.shape[0] != y.shape[0]:
        raise ValidationError("Probability/target length mismatch.")
    if np.isnan(proba).any() or np.isinf(proba).any():
        raise ValidationError("Probabilities contain NaN/inf.")
    if (proba < 0.0).any() or (proba > 1.0).any():
        raise ValidationError("Probabilities outside [0, 1].")
    predictions = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": round(float((tp + tn) / (tp + tn + fp + fn)), 6),
        "precision": round(float(precision), 6),
        "recall": round(float(recall), 6),
        "f1": round(float(f1), 6),
        "specificity": round(float(specificity), 6),
        "false_positive_rate": round(float(fpr), 6),
        "false_negative_rate": round(float(fnr), 6),
        "confusion_matrix": {
            "true_positive": int(tp),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
        },
    }


def threshold_analysis(
    y: np.ndarray, proba: np.ndarray, thresholds=None
) -> list[dict]:
    """Evaluate the precision/recall trade-off across a threshold range."""
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    return [
        metrics_at_threshold(y, proba, float(threshold)) for threshold in thresholds
    ]


def select_threshold(rows: list[dict], compare_default: bool = True) -> tuple[float, str]:
    """Select a prototype review threshold from validation-only results.

    Criterion: best precision/recall balance (maximum F1), preferring a higher
    threshold as a tie-break. This is a prototype review threshold, not a
    clinically optimised boundary: no clinical cost model for false negatives
    vs false positives is available. ``compare_default`` adds the 0.50 default
    as a reference row when the scores are on the original model scale.
    """
    by_f1 = sorted(rows, key=lambda row: (row["f1"], row["threshold"]), reverse=True)
    best = by_f1[0]
    default_note = ""
    if compare_default:
        default = next(
            (row for row in rows if abs(row["threshold"] - PREDICTION_THRESHOLD) < 1e-9),
            None,
        )
        if default is not None:
            default_note = (
                f" The Phase 8/9 default 0.50 threshold (validation F1 "
                f"{default['f1']}, recall {default['recall']}, precision "
                f"{default['precision']}) is reported alongside for comparison."
            )
    rationale = (
        f"Selected prototype review threshold {best['threshold']} (validation F1 "
        f"{best['f1']}, recall {best['recall']}, precision {best['precision']}, "
        f"specificity {best['specificity']}). Criterion: best precision/recall "
        "balance (maximum F1) on the validation partition, preferring a higher "
        "threshold as a tie-break. This is a prototype review threshold, not a "
        "clinically optimised decision boundary: no clinical cost model for "
        "false negatives vs false positives is available, so it must not be "
        "presented as clinically optimal." + default_note
    )
    return best["threshold"], rationale


def _bin_curve(y: np.ndarray, proba: np.ndarray, n_bins: int) -> list[dict]:
    """Uniform 10-bin calibration curve with per-bin counts (identical edges to
    sklearn's calibration_curve 'uniform' strategy, computed here to avoid
    NaNs on empty bins)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    indices = np.clip(np.digitize(proba, edges[1:-1]), 0, n_bins - 1)
    rows = []
    for i in range(n_bins):
        mask = indices == i
        count = int(mask.sum())
        if count == 0:
            pred, obs = 0.0, 0.0
        else:
            pred = float(proba[mask].mean())
            obs = float(y[mask].mean())
        rows.append(
            {
                "bin": i + 1,
                "bin_edge_lo": float(edges[i]),
                "bin_edge_hi": float(edges[i + 1]),
                "mean_predicted_probability": round(pred, 6),
                "observed_frequency": round(obs, 6),
                "count": count,
            }
        )
    return rows


def expected_calibration_error(
    y: np.ndarray, proba: np.ndarray, n_bins: int = CALIBRATION_BINS
) -> float:
    """Weighted mean absolute calibration error across uniform bins."""
    rows = _bin_curve(y, proba, n_bins)
    total = int(y.shape[0])
    ece = (
        sum(
            row["count"]
            * abs(row["observed_frequency"] - row["mean_predicted_probability"])
            for row in rows
        )
        / total
    )
    return round(float(ece), 6)


def calibration_analysis(
    y: np.ndarray, proba: np.ndarray, n_bins: int = CALIBRATION_BINS
) -> dict:
    """Brier score, expected calibration error and the calibration curve."""
    return {
        "brier_score": round(float(brier_score_loss(y, proba)), 6),
        "expected_calibration_error": expected_calibration_error(y, proba, n_bins),
        "n_bins": n_bins,
        "calibration_curve": _bin_curve(y, proba, n_bins),
    }


def _logit(p: np.ndarray) -> np.ndarray:
    """Log-odds transform with numerical clipping (used for Platt scaling)."""
    clipped = np.clip(p, 1e-15, 1.0 - 1e-15)
    return np.log(clipped / (1.0 - clipped))


def fit_calibrator(proba_cal: np.ndarray, y_cal: np.ndarray, method: str):
    """Fit a post-hoc calibrator on training-set scores (never test data).

    Sigmoid = Platt scaling: a logistic regression on the logit-transformed
    scores. Isotonic = monotone isotonic regression with clipping.
    """
    if method == "sigmoid":
        calibrator = LogisticRegression()
        calibrator.fit(_logit(proba_cal).reshape(-1, 1), y_cal)
        return calibrator
    if method == "isotonic":
        calibrator = IsotonicRegression(out_of_bounds="clip")
        calibrator.fit(proba_cal, y_cal)
        return calibrator
    raise ValidationError(f"Unknown calibration method: {method}")


def calibrate_probabilities(proba: np.ndarray, calibrator, method: str) -> np.ndarray:
    """Apply a fitted calibrator to predicted probabilities."""
    if method == "sigmoid":
        calibrated = calibrator.predict_proba(_logit(proba).reshape(-1, 1))[:, 1]
    elif method == "isotonic":
        calibrated = calibrator.predict(proba)
    else:
        raise ValidationError(f"Unknown calibration method: {method}")
    calibrated = np.asarray(calibrated, dtype="float64")
    if np.isnan(calibrated).any() or np.isinf(calibrated).any():
        raise ValidationError("Calibrated probabilities contain NaN/inf.")
    return np.clip(calibrated, 0.0, 1.0)


def assess_calibration_methods(
    y_train: np.ndarray,
    proba_train: np.ndarray,
    y_val: np.ndarray,
    proba_val: np.ndarray,
    n_bins: int = CALIBRATION_BINS,
) -> dict:
    """Fit candidate calibrators on train scores and assess them on validation.

    Returns the validation Brier/ECE for the uncalibrated model and each method,
    plus the fitted calibrators (for saving if one is selected).
    """
    results = {"uncalibrated": calibration_analysis(y_val, proba_val, n_bins)}
    calibrators = {}
    for method in ("sigmoid", "isotonic"):
        calibrator = fit_calibrator(proba_train, y_train, method)
        calibrated_val = calibrate_probabilities(proba_val, calibrator, method)
        results[method] = calibration_analysis(y_val, calibrated_val, n_bins)
        calibrators[method] = calibrator
    return {"results": results, "calibrators": calibrators}


def _choose_calibration(results: dict) -> tuple[str | None, str]:
    """Pick the calibration method only if it materially improves validation Brier."""
    uncalibrated_brier = results["uncalibrated"]["brier_score"]
    best_method = None
    best_brier = uncalibrated_brier
    for method in ("sigmoid", "isotonic"):
        brier = results[method]["brier_score"]
        if brier < best_brier - CALIBRATION_IMPROVEMENT_TOLERANCE:
            best_brier = brier
            best_method = method
    if best_method is None:
        rationale = (
            "Calibration was not applied: neither sigmoid nor isotonic calibration "
            "materially improved the validation Brier score (uncalibrated "
            f"{uncalibrated_brier:.6f}; sigmoid {results['sigmoid']['brier_score']:.6f}; "
            f"isotonic {results['isotonic']['brier_score']:.6f}), so the original "
            "Logistic Regression probabilities are retained."
        )
        return None, rationale
    rationale = (
        f"Calibration was applied using {best_method} calibration: validation "
        f"Brier score improved from {uncalibrated_brier:.6f} (uncalibrated) to "
        f"{best_brier:.6f}, and expected calibration error from "
        f"{results['uncalibrated']['expected_calibration_error']:.6f} to "
        f"{results[best_method]['expected_calibration_error']:.6f}."
    )
    return best_method, rationale


def _config_block(
    *,
    model_name: str,
    model_file: str,
    model_version: str,
    dataset_version: str,
    feature_count: int,
    selected_threshold: float,
    threshold_rationale: str,
    calibration_method: str | None,
    calibration_rationale: str,
    calibration_assessment: dict,
    threshold_table: list[dict],
    validation_metrics: dict,
    test_metrics_selected: dict,
    test_metrics_default: dict,
    date_stamp: str,
) -> dict:
    """Assemble the validation configuration (aggregate stats only)."""
    return {
        "artifact": {
            "version": VALIDATION_CONFIG_VERSION,
            "created": date_stamp,
            "description": (
                "Frozen inference configuration for the selected model: prototype "
                "review threshold and calibration method, decided on validation data "
                "only. Not a clinically validated configuration."
            ),
        },
        "model": {
            "name": model_name,
            "version": model_version,
            "file": model_file,
            "target": TARGET_DERIVED,
        },
        "dataset": {
            "name": DATASET_NAME,
            "source_url": DATASET_URL,
            "dataset_version": dataset_version,
            "preprocessing_version": PREPROCESSING_VERSION,
            "feature_count": feature_count,
        },
        "threshold": {
            "selected": selected_threshold,
            "label": "prototype review threshold",
            "clinically_validated": False,
            "rationale": threshold_rationale,
            "analysis_table": threshold_table,
        },
        "calibration": {
            "method": calibration_method if calibration_method is not None else "none",
            "calibrator_file": (
                str(SELECTED_CALIBRATOR_FILE) if calibration_method is not None else None
            ),
            "rationale": calibration_rationale,
            "assessment": calibration_assessment,
            "clinical_calibration": False,
        },
        "metrics": {
            "validation": validation_metrics,
            "test": {
                "at_selected_threshold": test_metrics_selected,
                "at_default_0_50_threshold": test_metrics_default,
                "notes": (
                    "test_at_selected_threshold uses the frozen configuration "
                    "(selected threshold and, if applied, calibrated probabilities); "
                    "test_at_default_0_50_threshold uses the raw model probabilities "
                    "at 0.50 for continuity with Phases 8/9."
                ),
            },
        },
    }


def save_validation_config(config: dict) -> None:
    """Persist the validation configuration atomically under ``models/``."""
    VALIDATION_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = VALIDATION_CONFIG_FILE.with_name(f".{VALIDATION_CONFIG_FILE.name}.tmp")
    try:
        temp.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(VALIDATION_CONFIG_FILE)
    finally:
        temp.unlink(missing_ok=True)


def load_validation_config() -> dict:
    """Load the saved validation configuration."""
    if not VALIDATION_CONFIG_FILE.exists():
        raise ValidationError(
            f"Validation config not found at {VALIDATION_CONFIG_FILE}."
        )
    return json.loads(VALIDATION_CONFIG_FILE.read_text(encoding="utf-8"))


def run_validation() -> dict:
    """Run threshold + calibration analysis on validation, freeze the config, then
    evaluate the frozen configuration once on the test partition."""
    model = compare.load_selected_model()
    model_metadata = compare.load_selected_metadata()

    X_train, y_train, _ = compare.baseline.load_split("train")
    X_val, y_val, _ = compare.baseline.load_split("validation")
    X_test, y_test, _ = compare.baseline.load_split("test")

    proba_train = compare.baseline.predict_probabilities(model, X_train)
    proba_val = compare.baseline.predict_probabilities(model, X_val)
    proba_test = compare.baseline.predict_probabilities(model, X_test)

    # --- Threshold analysis (validation only) ---
    threshold_rows = threshold_analysis(y_val, proba_val)
    selected_threshold, threshold_rationale = select_threshold(threshold_rows)

    # --- Calibration analysis (fit on train scores, assess on validation) ---
    calibration = assess_calibration_methods(
        y_train, proba_train, y_val, proba_val
    )
    calibration_method, calibration_rationale = _choose_calibration(
        calibration["results"]
    )

    if calibration_method is not None:
        calibrator = calibration["calibrators"][calibration_method]
        _save_calibrator(calibrator, calibration_method)
        # Re-derive the threshold on the calibrated validation probabilities.
        proba_val_effective = calibrate_probabilities(
            proba_val, calibrator, calibration_method
        )
        threshold_rows_effective = threshold_analysis(y_val, proba_val_effective)
        selected_threshold, threshold_rationale = select_threshold(
            threshold_rows_effective, compare_default=False
        )
    else:
        proba_val_effective = proba_val
        threshold_rows_effective = threshold_rows

    validation_metrics = metrics_at_threshold(
        y_val, proba_val_effective, selected_threshold
    )

    # --- Test evaluation exactly once, after the config is frozen ---
    if calibration_method is not None:
        proba_test_effective = calibrate_probabilities(
            proba_test, calibrator, calibration_method
        )
    else:
        proba_test_effective = proba_test

    test_metrics_selected = metrics_at_threshold(
        y_test, proba_test_effective, selected_threshold
    )
    test_metrics_default = metrics_at_threshold(y_test, proba_test, PREDICTION_THRESHOLD)

    config = _config_block(
        model_name=model_metadata["model"]["name"],
        model_file=str(SELECTED_MODEL_FILE),
        model_version=model_metadata["model"]["version"],
        dataset_version=model_metadata["dataset"]["dataset_version"],
        feature_count=model_metadata["dataset"]["feature_count"],
        selected_threshold=selected_threshold,
        threshold_rationale=threshold_rationale,
        calibration_method=calibration_method,
        calibration_rationale=calibration_rationale,
        calibration_assessment=calibration["results"],
        threshold_table=threshold_rows_effective,
        validation_metrics=validation_metrics,
        test_metrics_selected=test_metrics_selected,
        test_metrics_default=test_metrics_default,
        date_stamp=date.today().isoformat(),
    )
    save_validation_config(config)

    return {
        "artifact_version": VALIDATION_CONFIG_VERSION,
        "config_file": str(VALIDATION_CONFIG_FILE),
        "selected_threshold": selected_threshold,
        "threshold_rationale": threshold_rationale,
        "calibration_method": calibration_method,
        "calibration_rationale": calibration_rationale,
        "calibration_assessment": calibration["results"],
        "validation_metrics": validation_metrics,
        "test_metrics_at_selected_threshold": test_metrics_selected,
        "test_metrics_at_default_0_50": test_metrics_default,
    }


def _save_calibrator(calibrator, method: str) -> None:
    """Persist a fitted calibrator (aggregate-only transform; no patient data)."""
    SELECTED_CALIBRATOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = SELECTED_CALIBRATOR_FILE.with_name(f".{SELECTED_CALIBRATOR_FILE.name}.tmp")
    try:
        joblib.dump(calibrator, temp)
        temp.replace(SELECTED_CALIBRATOR_FILE)
    finally:
        temp.unlink(missing_ok=True)


def load_calibrator():
    """Load the saved calibrator if present."""
    if not SELECTED_CALIBRATOR_FILE.exists():
        raise ValidationError(
            f"Calibrator artifact not found at {SELECTED_CALIBRATOR_FILE}."
        )
    return joblib.load(SELECTED_CALIBRATOR_FILE)


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(run_validation(), indent=2, sort_keys=True))
