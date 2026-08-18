"""Phase 8 baseline model: regularised Logistic Regression.

Consumes the Phase 7 processed splits directly (``data/processed/{train,
validation,test}.csv``) — these already carry the exact feature representation
produced by the Phase 7 ``preprocessor.joblib`` — so no preprocessing is
refit here and no validation/test information can influence training.

The baseline estimates P(early (<30-day) readmission) for a diabetes-coded
encounter. It is a research/prototype risk estimator, not a diagnosis,
prescription or treatment-decision system.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.config import (
    DATASET_NAME,
    DATASET_URL,
    METADATA_FILE,
    MODEL_FILE,
    MODEL_METADATA_FILE,
    MODEL_VERSION,
    PREPROCESSING_VERSION,
    RANDOM_SEED,
    SPLIT_FILES,
    TARGET_DERIVED,
)

PREDICTION_THRESHOLD = 0.5
MAX_ITER = 1000
NUMERIC_TOLERANCE = 1e-8


class BaselineError(RuntimeError):
    """Raised when a sanity check fails during training or reload."""


def load_dataset_metadata() -> dict:
    """Load the Phase 7 dataset metadata (feature order, versions, splits)."""
    return json.loads(METADATA_FILE.read_text(encoding="utf-8"))


def load_split(split_name: str) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Load a processed split as (features, target, identifiers)."""
    if split_name not in SPLIT_FILES:
        raise ValueError(f"Unknown split: {split_name}")
    path = SPLIT_FILES[split_name]
    if not path.exists():
        raise BaselineError(
            f"Processed split not found at {path}. "
            "Run:  python scripts/prepare_dataset.py"
        )
    frame = pd.read_csv(path)
    meta = load_dataset_metadata()
    features = list(meta["encoded_feature_order"])
    missing = [feature for feature in features if feature not in frame.columns]
    if missing:
        raise BaselineError(f"Missing encoded features in {path}: {missing}")
    X = frame[features].to_numpy(dtype="float64")
    y = frame[TARGET_DERIVED].to_numpy(dtype="int64")
    identifiers = frame[["encounter_id", "patient_nbr"]]
    return X, y, identifiers


def train_logistic_regression(
    X: np.ndarray, y: np.ndarray, seed: int = RANDOM_SEED
) -> LogisticRegression:
    """Fit the baseline classifier on training data only.

    ``class_weight='balanced'`` rebalances the loss for the ~11% positive
    class; sklearn derives the weights from ``y`` (train) frequencies, so no
    validation/test information is used. ``lbfgs`` is deterministic for a
    fixed input.
    """
    model = LogisticRegression(
        max_iter=MAX_ITER,
        class_weight="balanced",
        random_state=seed,
    )
    model.fit(X, y)
    return model


def predict_probabilities(model, X: np.ndarray) -> np.ndarray:
    """Return P(positive class) for each row."""
    return model.predict_proba(X)[:, 1]


def evaluate_model(
    model,
    X: np.ndarray,
    y: np.ndarray,
    threshold: float = PREDICTION_THRESHOLD,
) -> dict:
    """Compute classification and ranking metrics at the documented threshold."""
    proba = predict_probabilities(model, X)
    predictions = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "positive_prevalence": round(float(y.mean()), 6),
        "accuracy": round(float(accuracy_score(y, predictions)), 6),
        "precision": round(float(precision_score(y, predictions, zero_division=0)), 6),
        "recall": round(float(recall_score(y, predictions, zero_division=0)), 6),
        "f1": round(float(f1_score(y, predictions, zero_division=0)), 6),
        "roc_auc": round(float(roc_auc_score(y, proba)), 6),
        "average_precision": round(
            float(average_precision_score(y, proba)), 6
        ),
        "confusion_matrix": {
            "true_positive": int(tp),
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
        },
    }


def sanity_check_model(model, X: np.ndarray, y: np.ndarray) -> None:
    """Fail loudly if the model output is not well-formed."""
    proba = predict_probabilities(model, X)
    predictions = model.predict(X)
    if proba.shape[0] != X.shape[0]:
        raise BaselineError("Probability output shape mismatch.")
    if predictions.shape[0] != X.shape[0]:
        raise BaselineError("Prediction output shape mismatch.")
    if np.isnan(proba).any() or np.isinf(proba).any():
        raise BaselineError("Predictions contain NaN/inf values.")
    if (proba < 0.0).any() or (proba > 1.0).any():
        raise BaselineError("Positive-class probabilities outside [0, 1].")
    if not set(np.unique(predictions)).issubset({0, 1}):
        raise BaselineError("Binary predictions contain unexpected values.")


def build_model_metadata(
    model: LogisticRegression,
    *,
    train_metrics: dict,
    validation_metrics: dict,
    test_metrics: dict,
    feature_order: list[str],
    train_rows: int,
    validation_rows: int,
    test_rows: int,
    seed: int,
) -> dict:
    """Assemble model metadata (aggregate stats only; no patient data)."""
    return {
        "model": {
            "name": "Logistic Regression baseline (regularised)",
            "version": MODEL_VERSION,
            "target": TARGET_DERIVED,
            "task": (
                "Estimate probability of early (<30-day) readmission for a "
                "diabetes-coded encounter."
            ),
            "class_weight_strategy": (
                "balanced: inverse train-class frequencies applied by sklearn "
                "to counter the ~11% positive-class prevalence; fitted on train "
                "labels only, so no validation/test leakage."
            ),
            "prediction_threshold": PREDICTION_THRESHOLD,
            "threshold_note": (
                "Threshold is the default 0.5 decision boundary for reporting "
                "threshold-dependent metrics; it is not claimed to be clinically "
                "optimal."
            ),
        },
        "dataset": {
            "name": DATASET_NAME,
            "source_url": DATASET_URL,
            "dataset_version": f"phase7-preprocessing-v{PREPROCESSING_VERSION}",
            "preprocessing_version": PREPROCESSING_VERSION,
            "random_seed": seed,
            "feature_count": len(feature_order),
            "feature_order": feature_order,
            "split_row_counts": {
                "train": train_rows,
                "validation": validation_rows,
                "test": test_rows,
            },
        },
        "training": {
            "date": date.today().isoformat(),
            "hyperparameters": {
                key: value
                for key, value in model.get_params().items()
                if key in {"C", "class_weight", "max_iter", "solver", "random_state"}
            },
            "fit_time_no_leakage": (
                "Model fit exclusively on the training partition produced by "
                "Phase 7; validation/test used only for evaluation."
            ),
        },
        "metrics": {
            "train": train_metrics,
            "validation": validation_metrics,
            "test": test_metrics,
        },
        "limitations": [
            "Research/prototype risk estimate only; not a diagnosis, prescription "
            "or treatment decision, and it does not replace a clinician.",
            "Cohort is diabetes-coded US hospital encounters (1999-2008), not a "
            "clinically validated Type 2-only cohort (Phase 7 gate remains open).",
            "No prospective validation; retrospective dataset; possible dataset "
            "bias and generalisation limits to newer/non-US populations.",
            "Imbalanced positive class (~11%); threshold-dependent metrics use a "
            "0.5 decision boundary that is not clinically optimised.",
        ],
    }


def save_model(model: LogisticRegression, metadata: dict) -> None:
    """Persist the fitted model and its metadata under ``models/``."""
    MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_model = MODEL_FILE.with_name(f".{MODEL_FILE.name}.tmp")
    try:
        joblib.dump(model, temp_model)
        temp_model.replace(MODEL_FILE)
    finally:
        temp_model.unlink(missing_ok=True)

    temp_meta = MODEL_METADATA_FILE.with_name(f".{MODEL_METADATA_FILE.name}.tmp")
    try:
        temp_meta.write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        temp_meta.replace(MODEL_METADATA_FILE)
    finally:
        temp_meta.unlink(missing_ok=True)


def load_model() -> LogisticRegression:
    """Load the saved baseline model."""
    if not MODEL_FILE.exists():
        raise BaselineError(f"Model artifact not found at {MODEL_FILE}.")
    return joblib.load(MODEL_FILE)


def load_model_metadata() -> dict:
    """Load the saved model metadata."""
    if not MODEL_METADATA_FILE.exists():
        raise BaselineError(f"Model metadata not found at {MODEL_METADATA_FILE}.")
    return json.loads(MODEL_METADATA_FILE.read_text(encoding="utf-8"))


def verify_saved_model(
    model, metadata: dict, X: np.ndarray, y: np.ndarray
) -> None:
    """Recompute metrics on the loaded model and compare with the record."""
    recorded = metadata["metrics"]["test"]
    recomputed = evaluate_model(model, X, y)
    for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"):
        if abs(recomputed[key] - recorded[key]) > NUMERIC_TOLERANCE:
            raise BaselineError(
                f"Reloaded model reproduces a different test {key}: "
                f"{recomputed[key]} vs recorded {recorded[key]}."
            )


def train_baseline(seed: int = RANDOM_SEED) -> dict:
    """Train, evaluate and persist the baseline model. Returns a summary."""
    X_train, y_train, _ = load_split("train")
    X_val, y_val, _ = load_split("validation")
    X_test, y_test, _ = load_split("test")

    model = train_logistic_regression(X_train, y_train, seed=seed)

    train_metrics = evaluate_model(model, X_train, y_train)
    validation_metrics = evaluate_model(model, X_val, y_val)
    test_metrics = evaluate_model(model, X_test, y_test)

    sanity_check_model(model, X_test, y_test)

    feature_order = list(load_dataset_metadata()["encoded_feature_order"])
    metadata = build_model_metadata(
        model,
        train_metrics=train_metrics,
        validation_metrics=validation_metrics,
        test_metrics=test_metrics,
        feature_order=feature_order,
        train_rows=int(len(X_train)),
        validation_rows=int(len(X_val)),
        test_rows=int(len(X_test)),
        seed=seed,
    )
    save_model(model, metadata)

    # Confirm the saved artifact reloads and reproduces the recorded result.
    reloaded = load_model()
    verify_saved_model(reloaded, load_model_metadata(), X_test, y_test)

    return {
        "model_version": MODEL_VERSION,
        "model_file": str(MODEL_FILE),
        "metadata_file": str(MODEL_METADATA_FILE),
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
    }


if __name__ == "__main__":  # pragma: no cover
    summary = train_baseline()
    print(json.dumps(summary, indent=2, sort_keys=True))