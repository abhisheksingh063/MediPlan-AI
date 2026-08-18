"""Phase 9 model comparison: Logistic Regression vs Random Forest vs Gradient
Boosting.

All candidates are trained on the exact Phase 7 training partition and
assessed on the Phase 7 validation partition. Model selection is made from
validation metrics only; the untouched Phase 7 test partition is evaluated
exactly once, after selection, for the chosen model.

The selected model estimates P(early (<30-day) readmission) for a
diabetes-coded encounter. It is a research/prototype risk estimator, not a
diagnosis, prescription or treatment-decision system.
"""

from __future__ import annotations

import json
from datetime import date

import joblib
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier

from app.ml import train as baseline
from app.ml.config import (
    DATASET_NAME,
    DATASET_URL,
    PREPROCESSING_VERSION,
    RANDOM_SEED,
    SELECTED_MODEL_FILE,
    SELECTED_MODEL_METADATA_FILE,
    SELECTED_MODEL_VERSION,
    TARGET_DERIVED,
)

PREDICTION_THRESHOLD = baseline.PREDICTION_THRESHOLD
NUMERIC_TOLERANCE = baseline.NUMERIC_TOLERANCE
ENCODED_FEATURE_COUNT = 55

MODEL_KEYS = ("logistic_regression", "random_forest", "gradient_boosting")

MODEL_DISPLAY_NAMES = {
    "logistic_regression": "Logistic Regression (baseline)",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting (HistGradientBoosting)",
}

# Fixed, defensible defaults per family (documented in the Phase 9 report).
FAMILY_DEFAULTS = {
    "logistic_regression": {
        "C": 1.0,
        "class_weight": "balanced",
        "max_iter": 1000,
        "solver": "lbfgs",
    },
    "random_forest": {
        "n_estimators": 300,
        "class_weight": "balanced",
        "n_jobs": -1,
    },
    "gradient_boosting": {
        "class_weight": "balanced",
        "max_iter": 300,
        "learning_rate": 0.1,
        "max_leaf_nodes": 31,
        "early_stopping": False,
    },
}

# Small, defensible configuration set. Logistic Regression is kept fixed as the
# Phase 8 baseline (no tuning: it is the unchanged baseline for comparison).
def build_candidates() -> dict:
    return {
        "logistic_regression": {
            "family": "logistic_regression",
            "params": {},
        },
        "random_forest_default": {
            "family": "random_forest",
            "params": {},
        },
        "random_forest_regularized": {
            "family": "random_forest",
            "params": {"max_depth": 40, "min_samples_leaf": 25},
        },
        "gradient_boosting_default": {
            "family": "gradient_boosting",
            "params": {},
        },
        "gradient_boosting_regularized": {
            "family": "gradient_boosting",
            "params": {"l2_regularization": 1.0, "min_samples_leaf": 40},
        },
    }


class ComparisonError(RuntimeError):
    """Raised when a comparison sanity check fails."""


def train_logistic_regression(
    X, y, seed: int = RANDOM_SEED, **params
):
    """Fit the Phase 8 Logistic Regression candidate (reuses Phase 8 code)."""
    if params:
        raise ComparisonError(
            "The Logistic Regression baseline is fixed and not tuned."
        )
    return baseline.train_logistic_regression(X, y, seed=seed)


def train_random_forest(X, y, seed: int = RANDOM_SEED, **params):
    """Fit a Random Forest candidate on training data only."""
    config = dict(FAMILY_DEFAULTS["random_forest"])
    config["random_state"] = seed
    config.update(params)
    model = RandomForestClassifier(**config)
    model.fit(X, y)
    return model


def train_gradient_boosting(X, y, seed: int = RANDOM_SEED, **params):
    """Fit a Gradient Boosting (HistGradientBoosting) candidate on train only."""
    config = dict(FAMILY_DEFAULTS["gradient_boosting"])
    config["random_state"] = seed
    config.update(params)
    model = HistGradientBoostingClassifier(**config)
    model.fit(X, y)
    return model


TRAIN_FUNCTIONS = {
    "logistic_regression": train_logistic_regression,
    "random_forest": train_random_forest,
    "gradient_boosting": train_gradient_boosting,
}


def _recorded_hyperparameters(family: str, params: dict, seed: int) -> dict:
    merged = dict(FAMILY_DEFAULTS[family])
    merged["random_state"] = seed
    merged.update(params)
    return merged


def evaluate_candidates(
    X_train, y_train, X_val, y_val, seed: int = RANDOM_SEED, candidates=None
) -> dict:
    """Fit every candidate on training data and record train/validation metrics.

    Validation data is used only for assessment; no test data is passed in.
    """
    candidates = candidates or build_candidates()
    results = {}
    for key, spec in candidates.items():
        family = spec["family"]
        train_fn = TRAIN_FUNCTIONS[family]
        model = train_fn(X_train, y_train, seed=seed, **spec["params"])
        baseline.sanity_check_model(model, X_val, y_val)
        if int(model.n_features_in_) != ENCODED_FEATURE_COUNT:
            raise ComparisonError(
                f"{key}: expected {ENCODED_FEATURE_COUNT} features, "
                f"got {model.n_features_in_}."
            )
        results[key] = {
            "family": family,
            "display_name": MODEL_DISPLAY_NAMES[family],
            "hyperparameters": _recorded_hyperparameters(family, spec["params"], seed),
            "n_features_in": int(model.n_features_in_),
            "train_metrics": baseline.evaluate_model(model, X_train, y_train),
            "validation_metrics": baseline.evaluate_model(model, X_val, y_val),
        }
    return results


def ranking_rows(results: dict) -> list[dict]:
    """Build a JSON-serializable ranking table from candidate results."""
    rows = []
    for key, result in results.items():
        val = result["validation_metrics"]
        tr = result["train_metrics"]
        rows.append(
            {
                "candidate": key,
                "family": result["family"],
                "display_name": result["display_name"],
                "train_roc_auc": tr["roc_auc"],
                "train_average_precision": tr["average_precision"],
                "validation_roc_auc": val["roc_auc"],
                "validation_average_precision": val["average_precision"],
                "validation_precision": val["precision"],
                "validation_recall": val["recall"],
                "validation_f1": val["f1"],
                "generalization_gap_roc_auc": round(
                    tr["roc_auc"] - val["roc_auc"], 6
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row["validation_average_precision"],
            row["validation_roc_auc"],
            row["validation_f1"],
            -row["generalization_gap_roc_auc"],
        ),
        reverse=True,
    )
    return rows


def select_model(results: dict) -> tuple[str, str]:
    """Select a candidate from validation metrics only (never test data).

    Criterion: highest validation PR-AUC (average precision), then ROC-AUC,
    then F1, then the smaller train-vs-validation ROC-AUC gap as a tie-break.
    """
    rows = ranking_rows(results)
    best = rows[0]
    baseline_row = next(
        (row for row in rows if row["candidate"] == "logistic_regression"), None
    )
    if baseline_row is None:
        rationale = (
            f"Selected {best['display_name']} ({best['candidate']}) on the validation "
            f"partition. Criterion: highest validation PR-AUC "
            f"({best['validation_average_precision']}), then ROC-AUC "
            f"({best['validation_roc_auc']}), then F1 ({best['validation_f1']}), "
            "with a smaller train-vs-validation ROC-AUC gap as tie-break. No fixed "
            "baseline candidate was present."
        )
    else:
        delta = best["validation_average_precision"] - baseline_row[
            "validation_average_precision"
        ]
        rationale = (
            f"Selected {best['display_name']} ({best['candidate']}) on the validation "
            f"partition. Criterion: highest validation PR-AUC ({best['validation_average_precision']}), "
            f"then ROC-AUC ({best['validation_roc_auc']}), then F1 "
            f"({best['validation_f1']}), with a smaller train-vs-validation ROC-AUC gap "
            f"({best['generalization_gap_roc_auc']:+}) as tie-break. "
            f"Baseline Logistic Regression validation PR-AUC was "
            f"{baseline_row['validation_average_precision']}; selected-model improvement "
            f"{delta:+.4f}."
        )
    return best["candidate"], rationale


def build_selected_metadata(
    model,
    *,
    selected_key: str,
    results: dict,
    ranking: list[dict],
    rationale: str,
    feature_order: list[str],
    train_rows: int,
    validation_rows: int,
    test_rows: int,
    test_metrics: dict,
    seed: int,
) -> dict:
    """Assemble metadata for the selected model (aggregate stats only)."""
    selected = results[selected_key]
    return {
        "model": {
            "name": selected["display_name"],
            "version": SELECTED_MODEL_VERSION,
            "target": TARGET_DERIVED,
            "task": (
                "Estimate probability of early (<30-day) readmission for a "
                "diabetes-coded encounter."
            ),
            "family": selected["family"],
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
            "hyperparameters": selected["hyperparameters"],
            "fit_time_no_leakage": (
                "Model fit exclusively on the training partition produced by "
                "Phase 7; validation/test used only for evaluation."
            ),
        },
        "selection": {
            "criterion": (
                "Highest validation PR-AUC, then validation ROC-AUC, then F1, "
                "then smaller train-vs-validation ROC-AUC gap; validation only, "
                "never test."
            ),
            "candidates_tested": list(results.keys()),
            "ranking": ranking,
            "selected": selected_key,
            "rationale": rationale,
        },
        "metrics": {
            "train": results[selected_key]["train_metrics"],
            "validation": results[selected_key]["validation_metrics"],
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


def save_selected_model(model, metadata: dict) -> None:
    """Persist the selected model and its metadata under ``models/``."""
    SELECTED_MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_model = SELECTED_MODEL_FILE.with_name(f".{SELECTED_MODEL_FILE.name}.tmp")
    try:
        joblib.dump(model, temp_model)
        temp_model.replace(SELECTED_MODEL_FILE)
    finally:
        temp_model.unlink(missing_ok=True)

    temp_meta = SELECTED_MODEL_METADATA_FILE.with_name(
        f".{SELECTED_MODEL_METADATA_FILE.name}.tmp"
    )
    try:
        temp_meta.write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )
        temp_meta.replace(SELECTED_MODEL_METADATA_FILE)
    finally:
        temp_meta.unlink(missing_ok=True)


def load_selected_model():
    """Load the saved selected model."""
    if not SELECTED_MODEL_FILE.exists():
        raise ComparisonError(
            f"Selected model artifact not found at {SELECTED_MODEL_FILE}."
        )
    return joblib.load(SELECTED_MODEL_FILE)


def load_selected_metadata() -> dict:
    """Load the saved selected-model metadata."""
    if not SELECTED_MODEL_METADATA_FILE.exists():
        raise ComparisonError(
            f"Selected model metadata not found at {SELECTED_MODEL_METADATA_FILE}."
        )
    return json.loads(SELECTED_MODEL_METADATA_FILE.read_text(encoding="utf-8"))


def verify_saved_selected_model(model, metadata: dict, X, y) -> None:
    """Recompute test metrics on the reloaded model and compare with the record."""
    recorded = metadata["metrics"]["test"]
    recomputed = baseline.evaluate_model(model, X, y)
    for key in ("accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"):
        if abs(recomputed[key] - recorded[key]) > NUMERIC_TOLERANCE:
            raise ComparisonError(
                f"Reloaded selected model reproduces a different test {key}: "
                f"{recomputed[key]} vs recorded {recorded[key]}."
            )


def run_comparison(seed: int = RANDOM_SEED) -> dict:
    """Evaluate candidates on validation, select, then evaluate the selected
    model once on the untouched test partition and persist it."""
    X_train, y_train, _ = baseline.load_split("train")
    X_val, y_val, _ = baseline.load_split("validation")
    X_test, y_test, _ = baseline.load_split("test")

    results = evaluate_candidates(X_train, y_train, X_val, y_val, seed=seed)
    ranking = ranking_rows(results)
    selected_key, rationale = select_model(results)

    # Fit the selected configuration on train and evaluate the test set once.
    selected = results[selected_key]
    spec = build_candidates()[selected_key]
    train_fn = TRAIN_FUNCTIONS[spec["family"]]
    model = train_fn(X_train, y_train, seed=seed, **spec["params"])
    baseline.sanity_check_model(model, X_test, y_test)
    test_metrics = baseline.evaluate_model(model, X_test, y_test)

    feature_order = list(baseline.load_dataset_metadata()["encoded_feature_order"])
    metadata = build_selected_metadata(
        model,
        selected_key=selected_key,
        results=results,
        ranking=ranking,
        rationale=rationale,
        feature_order=feature_order,
        train_rows=int(len(X_train)),
        validation_rows=int(len(X_val)),
        test_rows=int(len(X_test)),
        test_metrics=test_metrics,
        seed=seed,
    )
    save_selected_model(model, metadata)

    reloaded = load_selected_model()
    verify_saved_selected_model(reloaded, load_selected_metadata(), X_test, y_test)

    return {
        "model_version": SELECTED_MODEL_VERSION,
        "model_file": str(SELECTED_MODEL_FILE),
        "metadata_file": str(SELECTED_MODEL_METADATA_FILE),
        "selected": selected_key,
        "selected_display_name": selected["display_name"],
        "selection_rationale": rationale,
        "ranking": ranking,
        "train_metrics": results[selected_key]["train_metrics"],
        "validation_metrics": results[selected_key]["validation_metrics"],
        "test_metrics": test_metrics,
    }


if __name__ == "__main__":  # pragma: no cover
    summary = run_comparison()
    print(json.dumps(summary, indent=2, sort_keys=True))
