# ML Inference API

Exposes the Phase 7-10 readmission model as a decision-support endpoint. A
validated, structured 17-field clinical input is converted to an estimated
probability of early (<30-day) readmission, calibrated with the frozen sigmoid
calibrator, and compared against the Phase 10 prototype review threshold.

## Endpoint

`POST /api/v1/ml/predict`

## Request body

All 17 fields are required. Categorical values must match the vocabulary the
Phase 7 preprocessor learned from the training partition; numeric fields are
bounded by data-sanity limits from the evaluated dataset (not clinical
thresholds).

| Field                  | Type   | Allowed values / bounds                              |
| ---------------------- | ------ | ---------------------------------------------------- |
| `race`                 | string | `AfricanAmerican`, `Asian`, `Caucasian`, `Hispanic`, `Other`, `Unknown` |
| `gender`               | string | `Female`, `Male`, `Unknown/Invalid`                  |
| `age`                  | string | `[0-10)` … `[90-100)` (10 bins)                      |
| `admission_type_id`    | int    | 1–8                                                  |
| `admission_source_id`  | int    | `1,2,3,4,5,6,7,8,9,10,11,13,14,17,20,22,25`         |
| `time_in_hospital`     | int    | 1–30                                                 |
| `num_lab_procedures`   | int    | 1–200                                                |
| `num_procedures`       | int    | 0–20                                                 |
| `num_medications`      | int    | 1–100                                                |
| `number_outpatient`    | int    | 0–100                                                |
| `number_emergency`     | int    | 0–100                                                |
| `number_inpatient`     | int    | 0–50                                                 |
| `number_diagnoses`     | int    | 1–50                                                 |
| `max_glu_serum`        | string | `>200`, `>300`, `None`, `Norm`                        |
| `A1Cresult`            | string | `>7`, `>8`, `None`, `Norm`                            |
| `diabetesMed`          | string | `No`, `Yes`                                           |
| `change`               | string | `Ch`, `No`                                            |

Example:

```json
{
  "race": "Caucasian",
  "gender": "Male",
  "age": "[60-70)",
  "admission_type_id": 1,
  "admission_source_id": 1,
  "time_in_hospital": 3,
  "num_lab_procedures": 40,
  "num_procedures": 2,
  "num_medications": 10,
  "number_outpatient": 0,
  "number_emergency": 0,
  "number_inpatient": 1,
  "number_diagnoses": 8,
  "max_glu_serum": "None",
  "A1Cresult": "None",
  "diabetesMed": "Yes",
  "change": "No"
}
```

## Response

| Field               | Type   | Description                                            |
| ------------------- | ------ | ------------------------------------------------------ |
| `model_version`     | string | Frozen selected model version (`selected-model-v1`).   |
| `probability`       | number | Calibrated probability of early readmission, in [0, 1].|
| `threshold`         | number | Prototype review threshold (`0.1`).                    |
| `review_required`   | bool   | `true` iff `probability >= threshold`.                 |
| `calibration.method`| string | `sigmoid` (Platt).                                     |
| `calibration.version`| string | Validation config version (`validation-config-v1`).   |
| `safety_message`    | string | Fixed decision-support disclaimer.                     |

## Error handling

| Status | Condition                                                        |
| ------ | ---------------------------------------------------------------- |
| `422`  | Missing required field; unknown categorical value; out-of-range or wrong-type numeric value. |
| `503`  | Inference artifacts (preprocessor/model/calibrator/config) temporarily unavailable. Details never include filesystem paths. |

## Design notes

- Artifacts are loaded once per worker and cached in read-only memory; no
  request triggers a re-load and no raw clinical input or feature vector is
  logged or returned. The endpoint takes no patient identifiers, so it never
  persists inference history.
- The endpoint accepts only the structured 17-field input because the patient
  store (free-text clinical records) does not contain the encoded model
  features; no schema or storage changes were needed.
- The 0.10 threshold is a **prototype review threshold** (Phase 10),
  recall-favouring for clinician triage; it is explicitly not clinically
  optimised (`clinical_calibration: false`).

## Limitations

- Research/prototype estimate only: not a diagnosis, prescription, or
  treatment decision; it does not replace a clinician.
- Cohort is diabetes-coded US hospital encounters (1999-2008); the Phase 7
  Type 2-only clinical gate remains open and no prospective validation has
  been performed, so results may not generalise to other populations or eras.
- Discrimination is modest (test ROC-AUC 0.635). Aggregate summary metrics
  are recorded in `models/selected_model_v1.joblib` metadata and
  `models/model_validation_v1.json`; per-encounter probabilities must be
  interpreted with caution.