# MediPlan AI — Phase 8 Baseline Model Report

**Status:** first baseline model for Phase 9 comparison. Prepared data from
Phase 7 is used unchanged; no preprocessing was refit. This model is a
**research/prototype risk estimator** — not a diagnosis, prescription,
treatment recommendation, or substitute for clinician judgement.

## Dataset

| Item | Value |
| --- | --- |
| Dataset | UCI Diabetes 130-US Hospitals for Years 1999–2008 |
| Dataset version | `phase7-preprocessing-v1.0.0` |
| Source | https://archive.ics.uci.edu/dataset/296/diabetes-130-us-hospitals-for-years-1999-2008 (CC BY 4.0, DOI 10.24432/C5230J) |
| Size | 101,766 encounter rows (71,518 unique patients) |
| Target | `early_readmission` (`1` = readmitted within 30 days of discharge, else `0`) |
| Encoded feature count | 55 (exact Phase 7 `ColumnTransformer` output) |

## Model

- Logistic Regression (L2-regularised, sklearn `LogisticRegression`)
- Hyperparameters: `C=1.0`, `max_iter=1000`, `solver=lbfgs` (deterministic),
  `class_weight='balanced'`, `random_state=42`
- **Class-weight strategy:** `balanced` — sklearn reweights the loss by
  inverse train-class frequencies to counter the ~11% positive class. Weights
  derive from training labels only, so no validation/test leakage.
- Prediction threshold: `0.5` for reporting threshold-dependent metrics. This
  is the default decision boundary and is **not** claimed to be clinically
  optimal.

## Training methodology

- Training set: 71,520 rows · Validation set: 15,027 rows · Test set: 15,219 rows.
- Model fit **only** on the Phase 7 training partition (grouped by patient).
- Validation used solely for assessment; the test partition was evaluated once
  after the baseline configuration was fixed (no tuning on test).
- Feature representation is the persisted Phase 7 output consumed directly from
  `data/processed/{train,validation,test}.csv`; `data/processed/preprocessor.joblib`
  is untouched and no preprocessing is refit.

## Validation results (threshold 0.5)

| Metric | Validation |
| --- | --- |
| Positive prevalence | 11.02% |
| Accuracy | 0.6746 |
| Precision | 0.1591 |
| Recall | 0.4559 |
| F1-score | 0.2359 |
| ROC-AUC | 0.6193 |
| PR-AUC (average precision) | 0.1794 |
| Confusion matrix | TP 755 · TN 9,382 · FP 3,989 · FN 901 |

## Final test results (threshold 0.5)

| Metric | Test |
| --- | --- |
| Positive prevalence | 11.04% |
| Accuracy | 0.6742 |
| Precision | 0.1666 |
| Recall | 0.4875 |
| F1-score | 0.2483 |
| ROC-AUC | 0.6350 |
| PR-AUC (average precision) | 0.1987 |
| Confusion matrix | TP 819 · TN 9,442 · FP 4,097 · FN 861 |

Train-set metrics (reported separately): accuracy 0.6722, ROC-AUC 0.6378,
PR-AUC 0.1939 — no meaningful train/test gap, so the model is not
overfitting this representation.

## Interpretation

At a 0.5 threshold the baseline recalls about half of true early-readmission
encounters while most flagged encounters are false positives (low precision) —
expected for a 11% positive class without threshold tuning. Threshold-free
ranking quality is modest (test ROC-AUC 0.635, PR-AUC 0.199, i.e. ~1.8× the
prevalence). This is consistent with published work on this dataset and is a
reasonable **baseline for comparison** in Phase 9. It does **not** mean the
model can "predict which patients will be readmitted safely"; it is a weak but
usable risk-estimation baseline that later models must beat.

## Limitations

- **Cohort:** diabetes-coded US hospital encounters (1999–2008); **not** a
  clinically validated Type 2-only cohort (Phase 7 gate unresolved).
- **Generalisability:** retrospective, US-only, older data; no prospective
  validation; possible dataset bias and era/population drift.
- **Class imbalance:** 11% positive class depresses threshold-dependent
  metrics; calibrating/tuning thresholds is out of Phase 8 scope.
- **Features:** binned age, coarse glucose categories, large "test not
  performed" share, and no treatment-response evidence — no causal claims.
- The saved model reproduces its recorded metrics on reload (sanity-checked).

## Artifacts and reproducibility

- Model: `models/logistic_regression_baseline_v1.joblib`
- Metadata: `models/baseline_model_metadata.json` (aggregate stats only; no
  patient data)
- Reproduce:
  ```bash
  python scripts/train_baseline.py            # guard: refuses overwrite
  python scripts/train_baseline.py --force    # retrain and overwrite
  ```

Deterministic `lbfgs` + fixed seed (42) ⇒ repeated runs produce identical
weights and metrics (verified by tests within 1e-8).