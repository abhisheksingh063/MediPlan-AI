# MediPlan AI — Phase 7 Data Preparation Report

Status: explores and preprocesses the Phase 2 decision only; no model is trained.
Cohort, dataset and target follow `docs/research.md §4` and `docs/requirements.md §1, §4`.

## 1. Dataset used

- **UCI Diabetes 130-US Hospitals for Years 1999–2008** (`diabetic_data.csv`)
- 101,766 encounter rows, 50 raw columns (47 features + 2 identifiers + target)
- Each row is one diabetes-coded inpatient encounter; patients recur (16,773 patients
  have more than one encounter; max 40; 71,518 unique patients).
- **Cohort caveat:** the release is *diabetes-coded*, not a clinically validated
  Type 2-only cohort. The Phase 2 gate (requirements.md §1) requires clinical review
  of ICD-9 code mapping before any Type 2-specific claim. This pipeline therefore
  uses the whole release as-is and explicitly does NOT apply an unvalidated Type 2
  filter.

## 2. Source

- Publisher: **UCI Machine Learning Repository**
- Page: https://archive.ics.uci.edu/dataset/296/diabetes-130-us-hospitals-for-years-1999-2008
- Download: https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip
- DOI: **10.24432/C5230J** · License: **CC BY 4.0**
- Citation: Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). Diabetes
  130-US Hospitals for Years 1999-2008 [Dataset]. UCI ML Repository.
- Introductory paper: Strack et al. (2014), *BioMed Research International*, 2014, 781670.
- Acquired: **2026-08-17**. SHA-256 of archive and CSV are recorded in
  `data/raw/diabetes_130_us_hospitals/ACQUISITION.txt` and
  `data/processed/dataset_metadata.json`.

## 3. Dataset size

| Item | Value |
| --- | --- |
| Rows | 101,766 |
| Raw columns | 50 (47 features, `encounter_id` + `patient_nbr`, `readmitted`) |
| Unique patients | 71,518 |
| Rows from repeated patients | 30,248 |
| Full-duplicate rows | 0 |

## 4. Target

- Column: `readmitted` (`NO`, `>30`, `<30`); generated: `early_readmission = 1` when
  `readmitted == '<30'`, else `0` (Phase 2 definition, verified against the release).
- Class distribution: `<30` 11,357 (11.16%); `NO` 54,864; `>30` 35,545.
- No missing target values; unusable rows: 0.

## 5. Feature inventory

Selected Phase 2 features (exact order from research.md §4):

| Feature | Type | Missing (`?`) | Transformation |
| --- | --- | --- | --- |
| `race` | categorical | 2,273 (2.2%) | constant `Unknown` + one-hot |
| `gender` | categorical | 0 | one-hot |
| `age` | categorical (10 bins) | 0 | ordinal (bin order) |
| `admission_type_id` | categorical (8) | 0 | one-hot |
| `admission_source_id` | categorical (17) | 0 | one-hot |
| `time_in_hospital` | numeric | 0 | median → StandardScaler |
| `num_lab_procedures` | numeric | 0 | median → StandardScaler |
| `num_procedures` | numeric | 0 | median → StandardScaler |
| `num_medications` | numeric | 0 | median → StandardScaler |
| `number_outpatient` | numeric | 0 | median → StandardScaler |
| `number_emergency` | numeric | 0 | median → StandardScaler |
| `number_inpatient` | numeric | 0 | median → StandardScaler |
| `number_diagnoses` | numeric | 0 | median → StandardScaler |
| `max_glu_serum` | categorical | 0 (see note) | one-hot |
| `A1Cresult` | categorical | 0 (see note) | one-hot |
| `diabetesMed` | categorical | 0 | one-hot |
| `change` | categorical | 0 | one-hot |

Note: `max_glu_serum`/`A1Cresult` values `None` are the published "test not
performed" category, not missing data; they are encoded as their own category.

## 6. Missing values

- Only `?` is treated as missing (`'None'` stays a category to avoid pandas'
  default NA list mis-labelling it).
- Missing is confined to `race` (2,273) among selected features; all other selected
  features have zero missing values.
- Strategy: `race` → explicit constant `Unknown` category (avoids assuming majority
  category wrongly); numeric → median; the remaining categoricals → most-frequent.
  Every imputer is fitted **on the training split only**.

## 7. Duplicate handling

- Verified `encounter_id` unique (0 duplicates) and 0 full-row duplicates in the
  release; no rows are dropped for duplication.

## 8. Outlier handling

- No outliers removed. `time_in_hospital` is bounded [1,14] by the release inclusion
  criteria; count variables are recorded as-is. Removing unusual values would alter
  the release and is not justified for Phase 8 tree/LR baselines.

## 9. Encoding

- Nominal → scikit-learn `OneHotEncoder` (`handle_unknown='ignore'` for safe
  inference with unseen categories).
- `age` → `OrdinalEncoder` with the explicit, ordered bin list
  `[0-10) … [90-100)` (order is genuinely meaningful; arbitrary codes were avoided).

## 10. Scaling

- Numeric features: `StandardScaler` (fit on training split only) — the Phase 2
  baseline is regularised logistic regression, which benefits from scaling; Random
  Forest is scale-invariant and unaffected.

## 11. Leakage analysis

- **Excluded identifiers:** `encounter_id`, `patient_nbr`.
- **Excluded target:** `readmitted` (kept only as the derived label, joined after
  preprocessing).
- **Excluded `discharge_disposition_id`:** determined at discharge; may encode care
  pathway/outcome information (explicit Phase 2 exclusion).
- **Excluded non-selected Phase 2 variables:** `weight`, `payer_code`,
  `medical_specialty`, `diag_1..3`, and all per-medication and combination-medication
  columns (not in the Phase 2 feature set; no post-discharge variables added).
- **No future information:** the feature set is discharge-time encounter data only.
- **Split integrity:** grouped split by `patient_nbr` keeps one patient's encounters
  in a single partition, so no patient appears in both train and test.
- **Fit-time separation:** imputation, encoding and scaling fit on the training split
  only; validation/test are only transformed. No validation/test statistic feeds any
  preprocessing parameter (verified by tests).

## 12. Train / validation / test split

- Strategy: two-stage `GroupShuffleSplit` grouped by `patient_nbr` (~70 / 15 / 15).
  Grouped splitting prevents patient contamination; row-level stratification is
  approximated at group level because patients must stay intact.
- Seed: **42**.
- Resulting sizes (from `data/processed/dataset_metadata.json`):

| Split | Rows | Unique patients | Early rate |
| --- | --- | --- | --- |
| train | 71,520 | 50,062 | 11.22% |
| validation | 15,027 | 10,728 | 11.02% |
| test | 15,219 | 10,728 | 11.04% |

## 13. Preprocessing pipeline

- Single `sklearn` `ColumnTransformer` in `backend/app/ml/preprocessing.py`:

```
numeric   : SimpleImputer(median) -> StandardScaler
race      : SimpleImputer(constant 'Unknown') -> OneHotEncoder
nominal   : SimpleImputer(most_frequent) -> OneHotEncoder(handle_unknown='ignore')
age       : SimpleImputer(most_frequent) -> OrdinalEncoder(ordered bins)
```

- Fitted once on train; applied to all splits and reusable at inference from
  `data/processed/preprocessor.joblib`. Result: **55 encoded features** (no NaNs).

## 14. Final dataset statistics

- Encoded feature count: 55 (8 scaled numeric + 1 ordinal age + 46 one-hot).
- Feature order is recorded in `data/processed/dataset_metadata.json`
  (`encoded_feature_order`) and matches the CSV columns of `train/validation/test.csv`
  after the leading `encounter_id`, `patient_nbr` identifiers.
- No unexpected missing values in any encoded split (asserted by tests).

## 15. Limitations

- Not a clinically validated Type 2-only cohort (see §1). No clinical claim is made.
- US, 1999–2008, discharge/encounter context; age is binned.
- Coarse glucose categories (`>200`, `>300`, `Norm`, `None`) and high `None` share.
- Imbalanced positive class (11.16%) — Phase 8 evaluation must report precision,
  recall, PR-AUC, Brier and calibration, not accuracy alone (NFR-ML-002).
- No causality or treatment-response evidence is supported by this dataset.

## 16. Reproducibility instructions

```text
pip install -r backend/requirements.txt        # pandas, scikit-learn, joblib
python scripts/prepare_dataset.py --download   # fetch + verify + preserve raw
python scripts/prepare_dataset.py              # profile + split + preprocess
pytest backend/tests/test_data_preparation.py  # focused pipeline tests
pytest backend/tests/                          # full suite (all phases)
```

- Raw release is preserved under `data/raw/` and never modified; only `?` is
  interpreted as missing at load time. `git` ignores `data/raw/*` and
  `data/processed/*` (except `.gitkeep`), so outputs are reproducible from code.
- Same seed ⇒ identical splits and identical processed bytes (tested).