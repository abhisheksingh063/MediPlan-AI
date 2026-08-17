# MediPlan AI — Phase 2 Requirements

**Status:** Requirements baseline derived from [research.md](research.md). All clinical content remains clinician-reviewable; this is not a treatment protocol, diagnosis tool, or prescribing system.

## 1. Product Decisions

- MVP disease: **Type 2 Diabetes only**; synthetic/test patient demonstrations only.
- ML decision: conditional 30-day readmission-risk classification using UCI Diabetes 130-US Hospitals, as documented in [research.md](research.md). It is not a drug, diagnosis or treatment-response model.
- Mandatory gate: Phase 7 must clinically validate the Type 2 cohort definition and data dictionary before training. Failure requires revisiting the dataset decision.
- Medicine decision: small curated PMBI/Jan Aushadhi + selected NPPA reference table with provenance/date, not live availability.
- Facility decision: small curated, facility-specific capability table using IPHS hierarchy as context; no type-level assumptions.
- ABDM decision: optional, future adapter with mock/no-op default.

## 2. Functional Requirements

| ID | Requirement | Priority | Rationale/source | Future phase |
| --- | --- | --- | --- | --- |
| FR-PAT-001 | The system shall create/select synthetic patients only. | Must | MVP safety boundary | 6 |
| FR-PAT-002 | The system shall display a patient profile with demographics, history, allergies and medication history. | Must | [Research §2](research.md#2-clinical-workflow-research) | 6 |
| FR-REC-001 | The system shall store structured clinical records and laboratory measurements with units and collection dates. | Must | Research §2 | 5–6 |
| FR-REC-002 | The system shall record current medicines and previous treatments as clinician-entered context. | Must | Research §2 | 5–6 |
| FR-VAL-001 | The system shall validate required fields, data types, units, sensible ranges and cross-field consistency. | Must | Scope/Research §2 | 6–7 |
| FR-VAL-002 | The system shall surface missing/invalid inputs and prevent ML analysis until required model inputs are resolved or explicitly handled. | Must | Research §4 | 6–7 |
| FR-ML-001 | The system shall run only the approved, versioned ML model on validated inputs. | Must | Research §4 | 8–9, 14 |
| FR-ML-002 | The ML output shall be probability of the documented measurable endpoint, model version, timestamp and data-quality warnings. | Must | Research §4 | 8–9, 14 |
| FR-ML-003 | The system shall never output a drug selection, prescription, diagnosis or treatment-response claim unsupported by data. | Must | Research §4 | 11, 14 |
| FR-XAI-001 | The system shall show feature-contribution information and plain-language association/limitation wording. | Must | Scope/Research §4 | 10, 15 |
| FR-DS-001 | The system shall present controlled treatment-support reference options separately from the ML estimate. | Must | Scope | 11, 15 |
| FR-DS-002 | The system shall require a clinician to approve, modify or reject an AI-supported output. | Must | Scope | 11, 15 |
| FR-MED-001 | The system shall represent generic name, brand name, strength, form, pack size, INR price, source, last-verified date and Jan Aushadhi status. | Must | Research §5 | 5, 12 |
| FR-MED-002 | The system shall compare only like-for-like strength/form/pack products and label MRP/reference price as non-availability information. | Must | Research §5 | 12, 15 |
| FR-FAC-001 | The system shall represent a named facility, level, service/test, availability state, source and verification date. | Must | Research §6 | 5, 13 |
| FR-FAC-002 | The system shall distinguish `available`, `unavailable`, and `unknown`; unknown shall not be reported as unavailable. | Must | Research §6 | 13 |
| FR-REF-001 | The system shall show clinician-reviewable candidate referral options when a required service is unavailable or unconfirmed. | Must | Research §6 | 13, 15 |
| FR-AUD-001 | The system shall record analysis timestamp, model version, inputs/references used, system action and clinician review action. | Must | Scope/Research §8 | 5, 17 |
| FR-AUD-002 | The audit trail shall not store secrets or unnecessary sensitive payloads. | Must | Research §8 | 5, 17 |
| FR-ABDM-001 | The system shall use a mock/no-op ABDM adapter by default; core workflow shall not depend on ABDM. | Must | Research §7 | 16 |
| FR-ABDM-002 | A real ABDM adapter shall require authorised sandbox credentials, consent-aware flow and security review. | Stretch | Research §7 | 16 |

## 3. Non-functional Requirements

| ID | Requirement | Priority | Future phase |
| --- | --- | --- | --- |
| NFR-SEC-001 | Use authenticated, role-limited access and deny-by-default authorisation before any non-demo deployment. | Should | 17 |
| NFR-SEC-002 | Keep secrets outside version control; provide only `.env.example`. | Must | 4, 17 |
| NFR-PRIV-001 | Use synthetic/test data for all MVP demonstrations and minimise collected fields. | Must | 4–6, 17 |
| NFR-AUD-001 | Make audit events attributable, timestamped, protected and reviewable. | Must | 5, 17 |
| NFR-ML-001 | Make preprocessing reproducible, version data/model/configuration, and prevent train/test leakage. | Must | 7–10, 18 |
| NFR-ML-002 | Report calibration, prevalence, missingness, class imbalance and limitations; do not rely on accuracy alone. | Must | 8–10, 18 |
| NFR-USE-001 | Clearly label all AI material as decision support requiring clinician review. | Must | 3, 15 |
| NFR-USE-002 | Present missing-data, source-date and facility-unknown states clearly. | Must | 12–15 |
| NFR-DATA-001 | Show source and last-verified date for medicine and facility reference data. | Must | 12–13 |
| NFR-API-001 | Future APIs shall use documented, consistent errors and validation messages. | Should | 14, 18 |
| NFR-REL-001 | A failed optional ABDM adapter must not interrupt the core synthetic-demo workflow. | Must | 16 |
| NFR-PERF-001 | Set response-time targets only after Phase 3 user journeys and Phase 4 architecture are defined; no unsupported target is fixed now. | Pending | 3–4 |
| NFR-RET-001 | Define retention/deletion rules before storing any data beyond the synthetic demo; obtain appropriate legal review for real data. | Must | 5, 17 |

## 4. ML Data and Evaluation Requirements

1. Phase 7 shall download the exact selected dataset release, preserve provenance/licence evidence, inspect its data dictionary and compute target distribution/missingness from that release.
2. Phase 7 shall obtain clinician review of the diagnosis-code mapping needed for any Type 2 cohort and halt/revisit the ML decision if that mapping cannot be defensibly established.
3. Training shall use only the documented discharge-time feature list and must exclude identifiers, target, post-discharge information and `discharge_disposition_id`.
4. Splitting shall group by patient identifier when repeated encounters exist; all preprocessing/resampling/threshold selection shall be fit only on training folds.
5. Evaluation shall include ROC-AUC, PR-AUC, precision, recall, F1, confusion matrix, Brier/calibration assessment and class prevalence. Accuracy may be reported only as supplementary.
6. The UI shall disclose data age, US encounter context, cohort/subtype uncertainty, non-causality and lack of treatment-response support.

## 5. Risks and Assumptions

| Risk | Impact | Probability | Mitigation |
| --- | --- | --- | --- |
| ML target not sufficiently supported | High | Medium | Use a measurable readmission endpoint; validate exact source release. |
| Selected cohort is not verified Type 2-only | High | High | Mandatory Phase 7 clinical code-mapping gate; revisit selection if it fails. |
| Dataset bias/generalisation limits | High | High | Disclose US/older encounter context; avoid clinical deployment claims. |
| Treatment-response data unavailable | High | High | Do not model response or drug choice; retain controlled clinician review. |
| Leakage or repeated-patient contamination | High | Medium | Time-of-prediction review; grouped split; train-only preprocessing. |
| Medicine prices change or mappings are incomplete | Medium | High | Curate a small set; source/date each row; show freshness limitations. |
| Facility data/capability is incomplete | Medium | High | Use facility-specific `unknown` status and verified curated references. |
| ABDM access unavailable | High | High | Mock/no-op adapter; keep core independent. |
| Clinical validation unavailable | High | Medium | Label prototype; do not automate recommendations. |
| Scope creep | High | Medium | Freeze Type 2 MVP and priority list. |
| Secrets or identifiable data are committed | High | Low | `.gitignore`, review process, synthetic data and environment-managed secrets. |

## 6. Open Questions and Phase Gates

- Validate the Type 2 cohort mapping, exact release, licence and target distribution before data preparation.
- Obtain clinician approval for MVP validation ranges, required inputs and wording of risk/review flags.
- Choose named facilities/geography and independently verify service availability.
- Select and date-verify the small medicine reference set.
- Decide whether ABDM sandbox access is in scope after the core MVP; if yes, identify accountable credentials/security owners.
- Define retention/deletion policy and obtain legal review before any change from synthetic data.

## 7. Traceability

Research evidence, URLs and source IDs are maintained in [research.md](research.md#11-source-register). Functional requirements are deliberately limited to subsequent roadmap phases; no software implementation is authorised by this document.
