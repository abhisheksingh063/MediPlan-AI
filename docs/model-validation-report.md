# MediPlan AI — Phase 10 Model Validation & Calibration Report

**Status:** validates the Phase 9 selected model (Logistic Regression) against
the Phase 7 validation partition: a prototype review threshold is selected and
probability calibration is assessed. All decisions used training + validation
only; the Phase 7 test partition was evaluated exactly once, after the
configuration was frozen. The frozen configuration is saved to
`models/model_validation_v1.json`. This is a **research/prototype risk
estimator** — not a diagnosis, prescription or treatment decision, and no
clinical validity is claimed.

## 1. Objective

Phase 8/9 reported metrics at a fixed default threshold of `0.50` on the raw
`class_weight='balanced'` Logistic Regression probabilities. That threshold
was never examined, and balanced class weights are known to shift predicted
probabilities away from true event rates. This phase therefore (a) analyses the
precision/recall trade-off across thresholds, (b) assesses whether the model's
probabilities are reliably calibrated to observed event rates, and (c) freezes
a defensible prototype review configuration — while never treating the test set
as a tuning resource.

## 2. Existing model

| Item | Value |
| --- | --- |
| Model | Logistic Regression (regularised, `class_weight='balanced'`, `max_iter=1000`, seed 42) |
| Artifact | `models/selected_model_v1.joblib` (unchanged; Phase 8 baseline and Phase 9 comparison preserved) |
| Model version | `selected-model-v1` |
| Dataset | UCI Diabetes 130-US Hospitals for Years 1999–2008 |
| Dataset version | `phase7-preprocessing-v1.0.0` |
| Preprocessing | `1.0.0` (Phase 7 `preprocessor.joblib`; not refit) |
| Feature count | 55 encoded features |
| Target | `early_readmission` (`1` = readmitted within 30 days, else `0`) |
| Splits (unchanged) | train 71,520 · validation 15,027 · test 15,219 (grouped by patient, seed 42) |

## 3. Threshold analysis

Performed on the **validation** partition using the model's calibrated scores
(the scale the frozen inference configuration uses; see §5). All metrics at
threshold `t` use `probability >= t ⇒ flag for review`.

| Threshold | Precision | Recall | F1 | Specificity | FPR | FNR |
| --------: | --------: | -----: | --: | ----------: | --: | --: |
| 0.05 | 0.110429 | 0.999396 | 0.198882 | 0.002917 | 0.997083 | 0.000604 |
| **0.10** | **0.146652** | **0.633454** | **0.238166** | **0.543490** | **0.456510** | **0.366546** |
| 0.15 | 0.207640 | 0.203502 | 0.205550 | 0.903822 | 0.096178 | 0.796498 |
| 0.20 | 0.265802 | 0.099034 | 0.144303 | 0.966121 | 0.033879 | 0.900966 |
| 0.25 | 0.296774 | 0.055556 | 0.093591 | 0.983696 | 0.016304 | 0.944444 |
| 0.30 | 0.343949 | 0.032609 | 0.059570 | 0.992297 | 0.007703 | 0.967391 |
| 0.35 | 0.329670 | 0.018116 | 0.034345 | 0.995438 | 0.004562 | 0.981884 |
| 0.40 | 0.423077 | 0.013285 | 0.025761 | 0.997756 | 0.002244 | 0.986715 |
| 0.45 | 0.531250 | 0.010266 | 0.020142 | 0.998878 | 0.001122 | 0.989734 |
| 0.50 | 0.565217 | 0.007850 | 0.015485 | 0.999252 | 0.000748 | 0.992150 |
| 0.55 | 0.900000 | 0.005435 | 0.010804 | 0.999925 | 0.000075 | 0.994565 |
| 0.60 | 0.888889 | 0.004831 | 0.009610 | 0.999925 | 0.000075 | 0.995169 |
| 0.65 | 0.833333 | 0.003019 | 0.006017 | 0.999925 | 0.000075 | 0.996981 |
| 0.70 | 1.000000 | 0.001812 | 0.003617 | 1.000000 | 0.000000 | 0.998188 |
| 0.75 | 1.000000 | 0.000604 | 0.001207 | 1.000000 | 0.000000 | 0.999396 |
| 0.80 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 0.000000 | 1.000000 |
| 0.85 | 0.000000 | 0.000000 | 0.000000 | 1.000000 | 0.000000 | 1.000000 |

FPR = false-positive rate `FP/(FP+TN)`; FNR = false-negative rate `FN/(FN+TP)`.

The trade-off is steep: calibrated scores mostly lie in the 0.05–0.20 range
(the model discriminates only modestly, ROC-AUC ≈ 0.62). Lower thresholds trade
precision for recall; higher thresholds flag almost nothing.

## 4. Threshold selection

**Selected prototype review threshold: 0.10** (validation F1 0.2382, recall
0.6335, precision 0.1467, specificity 0.5435).

- **Why 0.10:** it maximises F1 on calibration-free validation metrics — the
  best precision/recall balance. It favours recall (0.63) over precision, which
  fits the prototype's clinician-review workflow: flagged cases are reviewed by
  a clinician, so missing a true early readmission (FNR 0.37) is costlier than
  reviewing an extra false positive (FPR 0.46).
- **Why 0.50 was not retained:** 0.50 was the decision boundary on the *raw*
  balanced-class-weight scores (Phase 8/9). Platt calibration remaps scores to
  the true event-rate scale, on which 0.50 would flag ≈0.8% of positives
  (validation recall 0.008). The equivalent operating point after calibration is
  much lower (≈0.10, matching the ~11% base rate).
- **Label:** this is a **prototype review threshold**, explicitly **not
  clinically validated**. No clinical cost model for false negatives vs false
  positives exists, so no claim of clinical optimality is made. High-recall and
  high-precision operating points are documented above for future clinician
  input.

## 5. Calibration

The raw `class_weight='balanced'` probabilities are severely miscalibrated
(worse than a constant predictor at the base rate). Validation Brier / ECE
(expected calibration error, 10 uniform bins across [0, 1]):

| Scores | Brier score | ECE |
| ------ | ----------: | --: |
| Uncalibrated (raw model) | 0.230936 | 0.363310 |
| Sigmoid (Platt) calibrated | **0.095904** | 0.007843 |
| Isotonic calibrated | 0.095935 | 0.002054 |

- Calibration **is** warranted: both methods reduce validation Brier from 0.231
  (worse than the ~0.098 constant-model floor) to ≈0.096 and ECE from 0.363 to
  <0.008.
- **Selected method: sigmoid (Platt scaling)** — a logistic regression on the
  logit-transformed scores, fitted on the training partition's scores, assessed
  on validation (best validation Brier). Isotonic achieves a marginally lower
  ECE but a marginally worse Brier; sigmoid was chosen for its robustness on the
  very sparse high-probability region (≥0.5 bins hold almost no validation
  cases).
- **Leakage control:** the calibrator was fit only on training-set scores; it
  never saw validation or test labels. Validation assessed fit; test evaluated
  only after freeze. The calibrator is fit on the same data the model saw
  (standard "fit calibrator on training data" practice); a strict nested
  train/calibrate/validate split would be preferable but the project structure
  reserves train for the model and validation for decisions. This nuance is
  recorded rather than introducing leakage.
- **Clinical calibration is not claimed** — calibration describes agreement with
  observed rates in this retrospective dataset only.

**Calibration method in the frozen config: `sigmoid`**
(`models/selected_model_calibrator_v1.joblib`).

## 6. Final test evaluation

The test set was evaluated **once**, with the frozen configuration
(sigmoid calibration + threshold 0.10). The raw 0.50 result is reported for
continuity with Phases 8/9.

| Threshold | Precision | Recall | F1 | Specificity | FPR | FNR |
| --------- | --------: | -----: | --: | ----------: | --: | --: |
| 0.50 (raw, Phase 8/9) | 0.166599 | 0.487500 | 0.248332 | 0.697393 | 0.302607 | 0.512500 |
| **0.10 (calibrated)** | **0.147927** | **0.650000** | **0.241006** | **0.535416** | **0.464584** | **0.350000** |

Confusion matrices (test):

- **0.50 raw:** TP 819 · TN 9,442 · FP 4,097 · FN 861
- **0.10 calibrated:** TP 1,092 · TN 7,249 · FP 6,290 · FN 588

At the selected threshold the model flags 33% more true early readmissions
(1,092 vs 819; recall 0.65 vs 0.49) at the cost of 2,193 more false positives
flagged for clinician review and a lower specificity (0.54 vs 0.70). F1 is
essentially unchanged (0.241 vs 0.248), consistent with the model's weak
discrimination (test ROC-AUC 0.635, PR-AUC 0.199). This is a defensible
higher-recall operating point for a clinician-review prototype — nothing more.

## 7. Clinical interpretation

The configured output is an **estimated probability of early (<30-day)
readmission based on the evaluated dataset** — never "the probability that this
patient will definitely be readmitted", and **not** a diagnosis, prescription or
treatment decision.

- This is a prototype; the dataset is retrospective (US, 1999–2008).
- The cohort is diabetes-coded and **not clinically validated as Type 2-only**.
- No prospective clinical validation has been performed.
- The threshold (0.10) is a prototype review threshold, **not** a clinically
  validated risk cut-off; calibration shows agreement with observed rates in
  this dataset only.

## 8. Limitations

- **Clinical-validation gate (unresolved):** the Phase 7/requirements gate
  requires clinician review of the ICD-9 diagnosis-code mapping to establish a
  Type 2-only cohort. Research/requirements documents define this as a
  clinician-adviser procedure; no clinician is available in this build phase, so
  the gate remains **open**. It was **not** silently "solved" by filtering.
- **Discrimination is weak:** ROC-AUC 0.635 / PR-AUC 0.199 (test). The model
  ranks risk only modestly; the 0.10 threshold depends on this limited signal.
- **Sparse high-probability region:** after calibration almost no patients score
  ≥ 0.5; high thresholds are statistically unsupported.
- **Calibrator fitted on training scores** (model and calibrator share the
  training partition) — slight optimism; a strict nested holdout is out of scope
  here (documented rather than introducing leakage).
- **Class imbalance** (~11%): Brier ≈ 0.096 is close to the constant-model floor
  (prevalence×(1−prevalence) ≈ 0.098), so the calibrated model offers modest
  improvement over a constant base-rate predictor.
- Retrospective, US-only data; no prospective validation; possible dataset bias
  and era/population drift. Coarse/binned features; no causality claims.

## 9. Reproducibility

```bash
python scripts/validate_model.py            # refuses to overwrite existing config
python scripts/validate_model.py --force    # recompute and overwrite
```

Artifacts:
- `models/model_validation_v1.json` — frozen configuration (model, dataset,
  threshold + rationale + full analysis table, calibration + assessment,
  validation metrics, final test metrics at selected threshold and at raw 0.50;
  no patient-level data).
- `models/selected_model_calibrator_v1.joblib` — sigmoid calibrator used by the
  frozen configuration.
- `models/selected_model_v1.joblib`, `logistic_regression_baseline_v1.joblib`,
  and their metadata — **unchanged**.

Deterministic pipeline (fixed model, seed 42, fixed thresholds): repeated runs
reproduce identical numbers. Calibration/threshold curves are stored as data
inside `model_validation_v1.json`; matplotlib is not installed and was not
added, so no image plots were generated (avoiding a new dependency per the
project rule).