# Explainability (SHAP)

Phase 12 adds a SHAP-based explanation layer over the existing Phase 7-10
readmission model so a clinician can see which of the 17 input fields pushed
the model's estimate of early (<30-day) readmission risk up or down.

**SHAP explains model behaviour; it does not establish clinical causation.**

## Why SHAP

- Additive, locally faithful attributions that sum (exactly, for a linear
  model) to the model output, making the numbers auditable.
- A well-known, library-supported method (`shap`) with a clear
  interpretation: each value is the contribution of that feature to moving the
  model estimate away from the background baseline.
- Model-specific and deterministic for Logistic Regression, so no slow or
  sampling-based approximation is needed.

## Selected SHAP explainer

- `shap.LinearExplainer` with `shap.maskers.Independent` and a fixed
  interventional background sample (the first 100 rows of the Phase 7
  validation partition, `max_samples=100`).
- Appropriate because the selected model is a single-layer Logistic
  Regression (55 encoded features): for linear models interventional SHAP
  values are **exact** (`phi_i = coef_i * (x_i - mean_i)`), deterministic, and
  fast. KernelExplainer would be unnecessary and slower.
- The explainer is built once per worker and cached; nothing is retrained or
  refit during an API request.

## Model being explained

- Selected Logistic Regression (`models/selected_model_v1.joblib`,
  version `selected-model-v1`) from Phase 9.
- SHAP values are computed in the model's **log-odds output space** (the
  decision function). Additivity holds exactly:
  `sum(SHAP) + expected_value == log-odds(model)`.

## Feature transformation and aggregation

Phase 7 transforms the 17 clinical inputs into 55 encoded features (8 scaled
numeric columns, one-hot dummies, one ordinal age column). These are not
exposed to the clinician. Each encoded feature is mapped back to its original
input field using the structure of the fitted preprocessor
(`ColumnTransformer.transformers_`), so one-hot dummies (e.g. the six `race_*`
columns) are summed into a single `race` contribution and each scaled numeric
column maps to itself. This yields exactly one contribution per original
clinical field, and the aggregated contributions still sum to the model output
(verified in tests). The displayed `value` is the raw input value provided by
the caller, never an encoded vector.

## Local explanation

`POST /api/v1/ml/explain` reuses the Phase 11 `InferenceRequest` unchanged,
runs the existing pipeline, and returns the calibrated probability plus a
sorted list of contributors. Contributions are rounded to 6 decimal places and
sorted by absolute contribution descending; each entry carries the original
feature name, the input value, the contribution, a direction
(`higher_risk` / `lower_risk`), a rank, and an optional human-readable label.

## Global explanation

`scripts/global_explainability.py` computes global feature importance offline
(mean absolute SHAP per original feature over the full Phase 7 validation
partition, 15,027 rows) and saves **aggregates only** to
`models/explainability_global_v1.json` (version `explainability-global-v1`).
No individual patient or encounter records are stored. The summary is exposed
read-only via `GET /api/v1/ml/explain/global`.

## Calibration relationship

The displayed probability is the Phase 10 output:
`raw probability (Logistic Regression) -> sigmoid calibration -> calibrated
probability`. SHAP explains the **underlying model output** (log-odds), not
the calibration curve. The sigmoid calibrator is a monotonic post-processing
step, so a feature that pushes the raw model estimate up also pushes the
calibrated probability up; but SHAP values are measured in log-odds units and
must not be mistaken for the calibrated probability scale.

## Interpretation of contributions

- **Positive contribution** → the feature pushed the underlying model estimate
  toward higher readmission risk.
- **Negative contribution** → the feature pushed the underlying model estimate
  toward lower readmission risk.
- Values are relative to the background baseline (mean log-odds over the fixed
  validation sample), and are model-behaviour descriptions, not clinical
  effects.

## Limitations

- SHAP is not causal: it cannot tell whether a feature *caused* a readmission,
  only how it influenced this model for this input.
- The model itself has modest discrimination (test ROC-AUC 0.635) and the
  cohort is a retrospective diabetes-coded US hospital dataset (1999-2008);
  the Phase 7 Type 2-only clinical gate remains open.
- One-hot features are grouped additively; the group attribution is exact for
  this linear model but represents the joint effect of the feature's encoded
  columns.
- Contributions are in log-odds units of the uncalibrated model; they do not
  map linearly to the calibrated probability.

## Safety considerations

- The explanation explicitly states that SHAP values describe model behaviour
  and are not causal clinical effects (`explanation_note` in the response).
- The endpoint is clinician decision support only: it does not diagnose,
  prescribe, automatically recommend treatment, or automatically refer a
  patient.
- Only original clinical input names/values are returned; encoded vectors,
  raw SHAP vectors, filesystem paths and internal errors are never exposed.
- Global aggregates never include individual records.

## API endpoint

`POST /api/v1/ml/explain` — request body is identical to
`POST /api/v1/ml/predict` (the 17-field `InferenceRequest`). Optional query
parameter `top_n` (1–17) limits the contributor list.

Example request:

```json
{
  "race": "Asian",
  "gender": "Female",
  "age": "[70-80)",
  "admission_type_id": 2,
  "admission_source_id": 7,
  "time_in_hospital": 1,
  "num_lab_procedures": 20,
  "num_procedures": 0,
  "num_medications": 5,
  "number_outpatient": 0,
  "number_emergency": 0,
  "number_inpatient": 0,
  "number_diagnoses": 3,
  "max_glu_serum": "Norm",
  "A1Cresult": "Norm",
  "diabetesMed": "No",
  "change": "Ch"
}
```

Example response (abridged):

```json
{
  "model_version": "selected-model-v1",
  "probability": 0.054689,
  "threshold": 0.1,
  "review_required": false,
  "calibration": { "method": "sigmoid", "version": "validation-config-v1" },
  "safety_message": "Estimated probability of early (<30-day) readmission ...",
  "explanation_method": "SHAP",
  "explanation_note": "SHAP values describe model behaviour; they are not causal clinical effects. ...",
  "contributors": [
    { "feature": "race", "value": "Asian", "contribution": -0.314358, "direction": "lower_risk", "rank": 1, "label": null },
    { "feature": "max_glu_serum", "value": "Norm", "contribution": 0.259999, "direction": "higher_risk", "rank": 2, "label": "Serum glucose normal" }
  ]
}
```

`GET /api/v1/ml/explain/global` returns the aggregate global summary.

## Testing instructions

From `backend/`:

```
.venv\Scripts\python.exe -m pytest tests/test_explainability.py -q
.venv\Scripts\python.exe -m pytest -q
```

Tests cover SHAP generation (finite values, 55-feature dimensions,
log-odds additivity, determinism, ordering), feature mapping (original names
only, numerically correct aggregation), direction semantics, API behaviour
(200, `[0,1]` probability, threshold 0.10, review-flag agreement with
inference, `top_n`, validation errors, safe 503 on artifact failure), and the
global aggregate summary. Regenerate the global summary with:

```
python scripts/global_explainability.py        # repo root
python scripts/global_explainability.py --force
```
