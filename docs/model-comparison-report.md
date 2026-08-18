# MediPlan AI — Phase 9 Model Comparison Report

**Status:** compares the Phase 8 Logistic Regression baseline against Random
Forest and Gradient Boosting candidates using the exact Phase 7 prepared data
and grouped splits. All candidates used the same training, validation and test
partitions, the same 55-feature representation, the same target, and the same
seed (42). Model selection used validation metrics only; the test partition was
evaluated exactly once, after selection. This is a **research/prototype
risk-estimation system** — not a diagnosis, prescription or treatment decision.

## Dataset

| Item | Value |
| --- | --- |
| Dataset | UCI Diabetes 130-US Hospitals for Years 1999–2008 |
| Dataset version | `phase7-preprocessing-v1.0.0` |
| Source | https://archive.ics.uci.edu/dataset/296/diabetes-130-us-hospitals-for-years-1999-2008 (CC BY 4.0, DOI 10.24432/C5230J) |
| Target | `early_readmission` (`1` = readmitted within 30 days of discharge, else `0`) |
| Feature count | 55 encoded features (Phase 7 `preprocessor.joblib` output; unchanged) |
| Split strategy | grouped by `patient_nbr` (two-stage GroupShuffleSplit, seed 42) |
| Split sizes | train 71,520 · validation 15,027 · test 15,219 |

No preprocessing was refit; no new split was created; the target was unchanged.

## Models

All models used `class_weight='balanced'` (inverse train-class frequencies) and
`random_state=42`.

| Model | Description / configuration |
| --- | --- |
| Logistic Regression (baseline) | Phase 8 model, unchanged: `C=1.0`, `max_iter=1000`, `solver=lbfgs`. |
| Random Forest | `n_estimators=300`, `n_jobs=-1`. Two configs: default; and regularised `max_depth=40, min_samples_leaf=25`. |
| Gradient Boosting | sklearn `HistGradientBoostingClassifier`, `max_iter=300`, `learning_rate=0.1`, `max_leaf_nodes=31`, `early_stopping=False`. Two configs: default; and regularised `l2_regularization=1.0, min_samples_leaf=40`. |

**XGBoost trade-off:** XGBoost is not installed and not in the project
requirements. Introducing it would add a compiled third-party dependency for a
boosting implementation that sklearn already provides
(`HistGradientBoostingClassifier`). The phase permits not adding unnecessary
libraries, so XGBoost was **not** introduced; Gradient Boosting is represented
by the sklearn implementation.

## Hyperparameter tuning

- **Parameters tested:** a small, defensible set — two configurations per new
  family (default and one regularised variant), listed above. Logistic
  Regression was **not** tuned because it is the fixed Phase 8 baseline for
  comparison.
- **Selection criterion:** highest validation **PR-AUC**, then validation
  ROC-AUC, then F1, then smaller train-vs-validation ROC-AUC gap as a tie-break.
- **Data used:** training + validation only. The test partition was untouched
  until the final selected model was evaluated.
- **Selected configuration:** Logistic Regression (`C=1.0`, `max_iter=1000`,
  `solver=lbfgs`, `class_weight='balanced'`).

## Validation comparison

All metrics at the same default threshold (0.5) used in Phase 8. Ranking by
validation PR-AUC (the phase emphasis for the ~11% positive class).

| Model | ROC-AUC | PR-AUC | Precision | Recall | F1 |
| ----- | ------: | -----: | --------: | -----: | -: |
| Logistic Regression (baseline) | **0.619348** | **0.179443** | 0.159148 | 0.455918 | 0.235937 |
| Random Forest (regularised) | 0.624374 | 0.172922 | 0.162786 | 0.481280 | 0.243284 |
| Gradient Boosting (regularised) | 0.613250 | 0.171966 | 0.157971 | 0.458937 | 0.235039 |
| Gradient Boosting (default) | 0.610153 | 0.167833 | 0.157320 | 0.460749 | 0.234553 |
| Random Forest (default) | 0.590087 | 0.148887 | 0.201807 | 0.040459 | 0.067404 |

Logistic Regression has the highest validation PR-AUC and ROC-AUC among the
models that generalise; the tree models do not meaningfully improve ranking
quality on the rare positive class.

## Overfitting / generalisation analysis

Train vs validation (ROC-AUC and PR-AUC) per candidate — the gap measures
memorisation:

| Model | Train ROC-AUC | Val ROC-AUC | ROC-AUC gap | Train PR-AUC | Val PR-AUC | PR-AUC gap |
| ----- | ------------: | ----------: | ----------: | -----------: | ---------: | ---------: |
| Logistic Regression | 0.637795 | 0.619348 | +0.018 | 0.193925 | 0.179443 | +0.014 |
| Random Forest (reg.) | 0.762926 | 0.624374 | +0.139 | 0.305388 | 0.172922 | +0.132 |
| Gradient Boosting (reg.) | 0.817318 | 0.613250 | +0.204 | 0.379738 | 0.171966 | +0.208 |
| Gradient Boosting (default) | 0.826387 | 0.610153 | +0.216 | 0.401194 | 0.167833 | +0.233 |
| Random Forest (default) | 1.000000 | 0.590087 | +0.410 | 0.999999 | 0.148887 | +0.851 |

- Logistic Regression has a negligible train/validation gap (~+0.02 ROC-AUC,
  ~+0.01 PR-AUC): it generalises well on this representation.
- Gradient Boosting shows substantial overfitting (~+0.20–0.22 ROC-AUC gap);
  high train scores do not transfer to validation, so boosting is **not**
  selected despite its training performance.
- The unregularised Random Forest **memorises** the training set
  (train ROC-AUC ≈ 1.000) and collapses to near-zero validation recall at the
  0.5 threshold. Even the regularised Random Forest overfits ~6× more than
  Logistic Regression.

Model selection was therefore not based on training scores.

## Final test comparison

The selected model is Logistic Regression (a deterministic refit of the Phase 8
configuration on the training partition, seed 42), so the "selected" model is
identical to the Phase 8 baseline. The test set was evaluated once.

| Metric | Phase 8 Baseline | Phase 9 Selected | Difference |
| ------ | ---------------: | ---------------: | ---------: |
| ROC-AUC | 0.635038 | 0.635038 | 0.0000 |
| PR-AUC (AP) | 0.198731 | 0.198731 | 0.0000 |
| Precision | 0.166599 | 0.166599 | 0.0000 |
| Recall | 0.487500 | 0.487500 | 0.0000 |
| F1 | 0.248332 | 0.248332 | 0.0000 |

Confusion matrix (test, threshold 0.5): TP 819 · TN 9,442 · FP 4,097 · FN 861.

## Model selection

Logistic Regression was retained as the final candidate because:

1. **PR-AUC is highest** (0.179443 vs 0.172922 for the best tree model) — the
   key ranking metric for a ~11% positive class.
2. **Generalisation gap is smallest** (+0.018 ROC-AUC vs +0.139 and +0.204 for
   regularised RF/GB) — the tree models' training gains largely do not transfer.
3. **Simplicity, interpretability and reproducibility** — a linear model with
   documented coefficients and deterministic training is easier to audit,
   explain and reproduce for a research/prototype system.
4. The regularised Random Forest's only real validation advantages (ROC-AUC
   +0.005, F1 +0.007, recall +0.025) are small, come with ~7× the
   overfitting gap, and do not outweigh its PR-AUC deficit.

**Honest conclusion: the stronger (tree) models do not provide a meaningful
improvement over Logistic Regression on the emphasised metrics for this
representation.** On validation PR-AUC the best tree model is ~3.6% worse, and
on the final test evaluation the selected model reproduces the Phase 8 baseline
exactly. The improvement over the baseline is **zero**; this is a negative
result for the Phase 9 objective, and Logistic Regression is the better overall
choice for this prototype.

## Model artifacts

```
models/
├── logistic_regression_baseline_v1.joblib   (Phase 8 — unchanged)
├── baseline_model_metadata.json              (Phase 8 — unchanged)
├── selected_model_v1.joblib                  (Phase 9 — Logistic Regression, version selected-model-v1)
└── selected_model_metadata.json              (Phase 9 — name, version, dataset/preprocessing versions,
                                               hyperparameters, seed, validation metrics, final test metrics,
                                               selection rationale/ranking; no patient-level data)
```

The Phase 8 baseline artifact was **not** overwritten. `data/processed/*` is
unchanged. Reproduce with:

```bash
python scripts/run_model_comparison.py
python scripts/run_model_comparison.py --force   # retrain and overwrite selected artifact
```

Deterministic training (seed 42, fixed hyperparameters) makes repeated runs
bit-identical; the reload check in `compare.verify_saved_selected_model`
reproduces the recorded test metrics within `1e-8`.

## Visualisation

ROC/PR curves were not generated: matplotlib is not installed and was not added
(the phase forbids unnecessary new dependencies). The ranking tables and
confusion matrices above fully support the comparison and selection.

## Limitations

- **Dataset:** diabetes-coded US hospital encounters (1999–2008); **not** a
  clinically validated Type 2-only cohort — the Phase 7 research gate
  (clinical review of ICD-9 code mapping) remains **unresolved**.
- **Class imbalance:** ~11% positive class; threshold-dependent metrics use the
  default 0.5 boundary, which is not clinically optimised. Threshold tuning is
  a Phase 10 concern.
- **Generalisability:** retrospective, single-population data; no prospective
  validation; possible dataset bias and era/population drift.
- **Representation limits:** binned age, coarse glucose categories, large "test
  not performed" share, and no treatment-response evidence — no causal claims.
- All models are research/prototype risk estimators: they estimate early
  readmission risk, do not diagnose, prescribe, or replace clinician judgement.