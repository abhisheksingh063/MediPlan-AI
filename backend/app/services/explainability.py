"""SHAP explainability layer for the Phase 7-10 readmission model.

Local (per-request) SHAP values explain the underlying selected Logistic
Regression in its raw log-odds output space (the decision function). The Phase
10 sigmoid calibrator is a monotonic post-processing step applied after the
model output; it is **not** explained here. SHAP therefore describes what
moved the underlying model estimate, not the calibrated probability curve and
never a patient's biological risk.

Encoded (transformed) contributions are aggregated back to the original
clinical input fields using the structure of the fitted preprocessor
(e.g. the one-hot dummies of ``race`` are summed into a single ``race``
contribution). Only original feature names and their raw input values are
exposed to callers.

Artifacts (background sample, feature grouping, explainer) are built once per
worker and cached in read-only memory; nothing is retrained or refit at
request time.
"""

from functools import lru_cache

import numpy as np
import shap

from app.ml import train as baseline
from app.services import inference as inference_service
from app.services.inference import ModelArtifactError, SAFETY_MESSAGE

EXPLANATION_METHOD = "SHAP"

EXPLANATION_NOTE = (
    "SHAP values describe model behaviour; they are not causal clinical "
    "effects. A positive contribution means the feature pushed the underlying "
    "model estimate higher; a negative contribution means it pushed the "
    "estimate lower. The displayed probability is calibrated after the model "
    "output, and this explanation does not prove what caused the patient's "
    "outcome."
)

BACKGROUND_ROWS = 100

# Optional clinician-facing expansion for selected categorical values.
LABELS = {
    "max_glu_serum": {
        ">200": "Serum glucose > 200 mg/dL",
        ">300": "Serum glucose > 300 mg/dL",
        "None": "Serum glucose not measured",
        "Norm": "Serum glucose normal",
    },
    "A1Cresult": {
        ">7": "A1C > 7%",
        ">8": "A1C > 8%",
        "None": "A1C not measured",
        "Norm": "A1C normal",
    },
}


@lru_cache(maxsize=1)
def _load_background() -> np.ndarray:
    """Fixed validation-derived background sample for the explainer."""
    X_val, _, _ = baseline.load_split("validation")
    return X_val[:BACKGROUND_ROWS]


@lru_cache(maxsize=1)
def _feature_groups() -> list[tuple[str, int, int]]:
    """Map each original feature to its slice of the 55 encoded features.

    Derived from the fitted preprocessor structure (``(name, transformer,
    columns)`` tuples), so one-hot dummies and scaled numeric columns are
    attributed to exactly one original clinical input. Yields
    ``(original_feature, start_index, count)`` in encoded column order.
    """
    preprocessor = _load_preprocessor_safely()
    groups = []
    offset = 0
    for _name, transformer, columns in preprocessor.transformers_:
        if _name in ("numeric", "ordinal_age"):
            for _col in columns:
                groups.append((_col, offset, 1))
                offset += 1
        elif _name in ("race", "nominal"):
            encoder = transformer.named_steps["encoder"]
            for col, categories in zip(columns, encoder.categories_):
                groups.append((col, offset, len(categories)))
                offset += len(categories)
        else:  # pragma: no cover - unknown transformer added in a later phase
            raise ModelArtifactError(
                "Explainability mapping is unavailable (unknown preprocessing "
                "transformer)."
            )
    return groups


@lru_cache(maxsize=1)
def _load_explainer() -> shap.LinearExplainer:
    """Build the exact LinearExplainer for the selected Logistic Regression.

    Interventional (feature-independent) perturbation with a fixed background
    sample makes the values exact for a linear model and fully deterministic.
    """
    model = inference_service._load_safely(
        inference_service._load_model, "Model artifacts are temporarily unavailable."
    )
    background = _load_background()
    masker = shap.maskers.Independent(background, max_samples=background.shape[0])
    return shap.LinearExplainer(model, masker)


def _load_preprocessor_safely():
    return inference_service._load_safely(
        inference_service._load_preprocessor,
        "Model preprocessing artifacts are temporarily unavailable.",
    )


def clear_explainer_cache() -> None:
    """Clear in-memory explainer/background/grouping caches (tests)."""
    for loader in (_load_background, _feature_groups, _load_explainer):
        loader.cache_clear()


def _aggregate_contributions(shap_values: np.ndarray) -> dict[str, float]:
    """Sum transformed SHAP values back to the 17 original features."""
    contributions = {}
    for feature, start, count in _feature_groups():
        contributions[feature] = float(shap_values[start : start + count].sum())
    return contributions


def explain(features: dict, top_n: int | None = None) -> dict:
    """Return the calibrated prediction plus a local SHAP explanation.

    ``top_n`` limits the sorted contributor list (default: all 17 original
    features, sorted by absolute contribution descending).
    """
    parts = inference_service.predict_parts(features)
    encoded = parts["encoded_array"]
    if encoded.ndim != 2 or encoded.shape[0] != 1:
        raise ModelArtifactError("Unexpected model input shape during explanation.")
    if int(encoded.shape[1]) != _expected_feature_count():
        raise ModelArtifactError("Explainability artifacts do not match the model.")

    explainer = inference_service._load_safely(
        _load_explainer, "Explainability artifacts are temporarily unavailable."
    )
    shap_values = explainer.shap_values(encoded)[0]

    contributions = _aggregate_contributions(shap_values)
    ordered = sorted(contributions.items(), key=lambda item: -abs(item[1]))
    if top_n is not None:
        ordered = ordered[:top_n]

    contributors = []
    for rank, (feature, contribution) in enumerate(ordered, start=1):
        value = features.get(feature)
        direction = "higher_risk" if contribution >= 0.0 else "lower_risk"
        contributors.append(
            {
                "feature": feature,
                "value": value,
                "contribution": round(contribution, 6),
                "direction": direction,
                "rank": rank,
                "label": LABELS.get(feature, {}).get(str(value)),
            }
        )

    config = parts["config"]
    probability = parts["probability"]
    threshold = float(config["threshold"]["selected"])
    return {
        "model_version": inference_service.predict(features)["model_version"],
        "probability": round(probability, 6),
        "threshold": threshold,
        "review_required": bool(probability >= threshold),
        "calibration": {
            "method": str(config["calibration"]["method"]),
            "version": str(config["artifact"]["version"]),
        },
        "safety_message": SAFETY_MESSAGE,
        "explanation_method": EXPLANATION_METHOD,
        "explanation_note": EXPLANATION_NOTE,
        "contributors": contributors,
    }


def _expected_feature_count() -> int:
    """Number of encoded features the model was trained on."""
    model = inference_service._load_safely(
        inference_service._load_model, "Model artifacts are temporarily unavailable."
    )
    return int(model.n_features_in_)


def global_summary() -> dict:
    """Return the saved offline global feature-importance summary.

    The summary is generated by ``scripts/global_explainability.py`` and
    contains only aggregates (no individual records).
    """
    from app.ml.config import EXPLAINABILITY_GLOBAL_FILE

    if not EXPLAINABILITY_GLOBAL_FILE.exists():
        raise ModelArtifactError(
            "Global explainability summary is not available. Run "
            "scripts/global_explainability.py to generate it."
        )
    return inference_service._load_safely(
        _load_global_artifact, "Global explainability summary is temporarily unavailable."
    )


@lru_cache(maxsize=1)
def _load_global_artifact() -> dict:
    from app.ml.config import EXPLAINABILITY_GLOBAL_FILE
    import json

    return json.loads(EXPLAINABILITY_GLOBAL_FILE.read_text(encoding="utf-8"))