"""Inference service exposing the Phase 7-10 readmission model.

The service converts a validated 17-field clinical input into a calibrated
probability of early (<30-day) readmission using the frozen artifacts:

* ``models/preprocessor.joblib`` (fitted ColumnTransformer) for feature
  encoding;
* ``models/selected_model_v1.joblib`` for the raw logistic-regression
  probability;
* ``models/selected_model_calibrator_v1.joblib`` and
  ``models/model_validation_v1.json`` for Platt calibration and the prototype
  review threshold.

Artifacts are loaded once per worker and cached in read-only memory. No
clinical input vectors or model internals are logged or returned to callers.
"""

from functools import lru_cache

import numpy as np
import pandas as pd

from app.ml import compare, preprocessing, validate
from app.ml.config import FEATURES

SAFETY_MESSAGE = (
    "Estimated probability of early (<30-day) readmission based on the "
    "evaluated dataset. Decision-support for clinician review only; not a "
    "diagnosis, prescription, or treatment recommendation."
)

CATEGORICAL_FEATURES = {
    "race",
    "gender",
    "age",
    "admission_type_id",
    "admission_source_id",
    "max_glu_serum",
    "A1Cresult",
    "diabetesMed",
    "change",
}


class InferenceError(RuntimeError):
    """Base failure for the inference service (maps to HTTP 503)."""


class InsufficientInputError(InferenceError):
    """Raised when required model inputs are missing (maps to HTTP 422)."""


class ModelArtifactError(InferenceError):
    """Raised when a required model artifact cannot be loaded."""


@lru_cache(maxsize=1)
def _load_preprocessor():
    return preprocessing.load_preprocessor()


@lru_cache(maxsize=1)
def _load_model():
    return compare.load_selected_model()


@lru_cache(maxsize=1)
def _load_calibrator():
    return validate.load_calibrator()


@lru_cache(maxsize=1)
def _load_validation_config():
    return validate.load_validation_config()


def clear_artifact_cache() -> None:
    """Clear in-memory artifact cache (tests, artifact refresh)."""
    for loader in (_load_preprocessor, _load_model, _load_calibrator, _load_validation_config):
        loader.cache_clear()


def _load_safely(loader, message: str):
    try:
        return loader()
    except Exception as exc:
        raise ModelArtifactError(message) from exc


def _build_raw_frame(features: dict) -> pd.DataFrame:
    """Build a one-row DataFrame in the exact Phase 7 feature order."""
    missing = [col for col in FEATURES if features.get(col) is None]
    if missing:
        raise InsufficientInputError(
            "Insufficient model inputs; missing required input(s): "
            + ", ".join(missing)
        )
    row = {col: features[col] for col in FEATURES}
    frame = pd.DataFrame([row], columns=FEATURES)
    for col in CATEGORICAL_FEATURES:
        frame[col] = frame[col].astype(str)
    return frame


def predict_parts(features: dict) -> dict:
    """Run the full pipeline and return all intermediate values.

    Exposes the encoded features, feature names, raw log-odds, raw probability
    and calibrated probability so explanation layers can reuse the exact same
    preprocessing/model/calibration path as :func:`predict` (single source of
    truth, no duplicated loading or transformation logic).
    """
    preprocessor = _load_safely(
        _load_preprocessor, "Model preprocessing artifacts are temporarily unavailable."
    )
    model = _load_safely(_load_model, "Model artifacts are temporarily unavailable.")
    calibrator = _load_safely(
        _load_calibrator, "Calibration artifacts are temporarily unavailable."
    )
    config = _load_safely(
        _load_validation_config, "Validation configuration is temporarily unavailable."
    )

    frame = _build_raw_frame(features)
    encoded = preprocessing.apply_preprocessor(preprocessor, frame)
    encoded_array = encoded.to_numpy("float64")
    logit = float(model.decision_function(encoded_array)[0])
    raw = float(compare.baseline.predict_probabilities(model, encoded_array)[0])

    method = config["calibration"]["method"]
    if method == "none":
        probability = float(raw)
    else:
        calibrated = validate.calibrate_probabilities(
            np.asarray([raw]), calibrator, method
        )
        probability = float(calibrated[0])
    return {
        "encoded": encoded,
        "encoded_array": encoded_array,
        "encoded_feature_names": list(encoded.columns),
        "logit": logit,
        "raw_probability": raw,
        "probability": probability,
        "config": config,
    }


def predict_probability(features: dict) -> float:
    """Return the calibrated probability of early readmission in [0, 1]."""
    return predict_parts(features)["probability"]


def predict(features: dict) -> dict:
    """Run inference on a validated feature dict and return the API payload."""
    parts = predict_parts(features)
    config = parts["config"]
    probability = parts["probability"]
    threshold = float(config["threshold"]["selected"])
    model_version = str(compare.load_selected_metadata()["model"]["version"])
    return {
        "model_version": model_version,
        "probability": round(probability, 6),
        "threshold": threshold,
        "review_required": bool(probability >= threshold),
        "calibration": {
            "method": str(config["calibration"]["method"]),
            "version": str(config["artifact"]["version"]),
        },
        "safety_message": SAFETY_MESSAGE,
    }