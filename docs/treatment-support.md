# Treatment Decision Support (Phase 13)

Prototype endpoint: `POST /api/v1/treatment-support`

```json
{ "patient_id": 42 }
```

Evaluates a patient's **recorded demographic and laboratory data** against
declarative, evidence-cited clinical considerations and returns everything it
can trigger — independently, unranked, and unsynthesized. It is a
clinician-review aid only and is intentionally kept separate from the Phase
7-10 machine-learning readmission estimate.

## Contract

`TreatmentSupportResponse`:

| Field | Meaning |
| --- | --- |
| `patient_id` | The patient evaluated. |
| `decision_support_only` | Always `true`. |
| `clinical_validation_required` | Always `true` (dataset is not a clinically validated T2D cohort). |
| `guideline_version` | Version of the evidence base used (ADA Standards of Care in Diabetes — 2026). |
| `generated_at` | Evaluation timestamp (audit trail linkage). |
| `considerations[]` | Triggered rules with `rule_id`, `title`, `severity_tag` (`informational` \| `consider_review` \| `urgent_review`), `reason` (rendered clinical text), `evidence_source`, `inputs_evaluated`. |
| `missing_information[]` | Fields that suppressed evaluation: `reason` `missing` (nothing recorded) or `stale` (latest value older than the guideline recency window), with `last_available`. |
| `interpretation_note` | States considerations are unranked/unsynthesized and tensions require clinician judgment. |
| `safety_message` | Standard "Decision support only — clinician review required" notice. |

## Design rules

- **Rules are data.** All rule logic lives in
  `backend/app/treatment_support/rules.json` (11 rules); the clinical input
  catalog (aliases, units, guideline recency windows) lives in
  `backend/app/treatment_support/inputs.json`. The service interprets these
  files; there is no scattered inline threshold logic.
- **Evidence-cited.** Every rule carries `evidence_source`
  (`organization`, `document`, `version`, `section`,
  `table_or_recommendation`, `doi`). ADA rules cite the 2026 edition
  (Diabetes Care, Vol 49, Supplement 1) with `10.2337/dc26-S*` DOIs. The one
  threshold ADA does not define itself — the ≥180/120 hypertensive-crisis
  cutoff — is explicitly attributed to ACC/AHA 2017. Rules for which no
  authoritative threshold could be verified were **not** implemented.
- **Missing vs stale.** Both suppress the affected rules. Values older than
  the guideline recency window (A1C > 6 months, BP > 6 months, eGFR/UACR >
  12 months per ADA) are reported as `stale` and never evaluated. ML
  imputation is never used for clinical inputs.
- **ML separation.** `services/treatment_support.py` never imports the
  inference or explainability services. Rule outcomes are invariant to any
  change in model probability or SHAP values (regression-tested). The ML
  readmission estimate is not part of this module.
- **Safety boundaries.** No drug selection, no doses, no automatic
  medication changes, no diagnosis language. Output text uses calibrated
  phrasing ("may warrant clinician assessment", "Guideline indicates…").
  Banned wording is scanned in tests.

## Current rules (evidence table)

| ID | Rule | Trigger | Severity | Evidence |
| --- | --- | --- | --- | --- |
| TDS-001 | Glycemic goal threshold | A1C ≥ 7.0% | consider_review | ADA 2026 §6, Table 6.3 |
| TDS-002 | A1C ≥1.5% above goal | A1C ≥ 8.5% | consider_review | ADA 2026 §9, Rec 9.6/Table 9.2 |
| TDS-003 | Marked hyperglycemia | A1C > 10.0% | urgent_review | ADA 2026 §9, Rec 9.20 |
| TDS-004 | Reduced kidney function | eGFR < 60 | consider_review | ADA 2026 §11 |
| TDS-005 | Albuminuria | UACR ≥ 30 mg/g | consider_review | ADA 2026 §11 |
| TDS-006 | Obesity | BMI ≥ 30 (computed) | consider_review | ADA 2026 §8, §5 |
| TDS-007 | Overweight | 25 ≤ BMI < 30 | informational | ADA 2026 §8 |
| TDS-008 | BP at/above goal | systolic ≥130 or diastolic ≥80 | consider_review | ADA 2026 §10, Rec 10.1/10.4 |
| TDS-009 | Hypertensive crisis | systolic ≥180 or diastolic ≥120 | urgent_review | ACC/AHA 2017 (referenced by ADA §10) |
| TDS-010 | Statin consideration | age 40–75 | informational | ADA 2026 §10 (lipids) |
| TDS-011 | Less-stringent goal for older adults | age ≥65 and 7.0 ≤ A1C < 8.5 | informational | ADA 2026 §6 Fig 6.1, §13 |

Conflicts are intentionally not resolved: e.g. TDS-001 and TDS-011 can fire
together for the same patient; both are shown as-is.

## Input mapping

Lab values come from `LabResult` rows attached to the patient's clinical
records; `test_name` is free text, so names are normalized (lower-cased,
whitespace-collapsed) and matched against per-field aliases (e.g.
`HbA1c`/`A1C` → `hba1c`). The most recent result per field wins
(`recorded_at`, ties broken by id). `BMI` is computed from stored
`height (cm)` and `weight (kg)`; it is missing if either is absent.

## Verification

- 34 new tests in `tests/test_treatment_support.py` (rule-data integrity,
  trigger/absent/stale behaviour, conflict handling, ML-separation, API
  behaviour, no raw data in errors). Deprecation warnings only.
- Full suite: 167 tests green (Phases 1–12 regression intact, including
  ML prediction, SHAP explanation, and the 0.10 review threshold).
- See `git diff --check` and smoke-test results in the phase report.

## Limitations

- Rules evaluate **one reference value per field**; trends (rising A1C,
  eGFR slope) are not yet modelled.
- `current_medications` is free text and is **not** parsed; no
  medication-flagging rules exist yet (later Medicines phase).
- Family history, comorbidities structure, and medication list are not yet
  available as structured inputs.
- The prototype does not sort or weigh considerations, and the underlying
  dataset is not a clinically validated Type 2 diabetes cohort.
- ABDM/ABHA integrations remain out of scope.