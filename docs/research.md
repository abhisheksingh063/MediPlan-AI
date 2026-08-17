# MediPlan AI — Phase 2 Research Log

**Accessed:** 17 August 2026. This document records sources actually consulted and separates source-backed findings from project decisions and unresolved assumptions. MediPlan AI remains a synthetic-data, clinician-reviewable prototype.

## 1. Research Objectives

Establish a defensible, non-prescribing Type 2 Diabetes MVP workflow; compare usable datasets; select a measurable ML endpoint; identify medicine and facility data strategies; assess optional ABDM feasibility; and derive privacy/security requirements.

## 2. Clinical Workflow Research

WHO's Type 2 Diabetes primary-care module and India's NP-NCD guidance support a workflow involving screening/diagnosis, monitoring, management and referral, but they are not a specification for automated treatment. [S01](#source-register), [S02](#source-register).

| Information category | Evidence-supported information | MediPlan AI project requirement | Assumption requiring clinical validation |
| --- | --- | --- | --- |
| Demographics and history | Age, sex, risk/medical history and lifestyle context are relevant to diabetes care and screening. [S01](#source-register), [S02](#source-register) | Record age, sex, relevant history and risk factors for synthetic patients. | Exact MVP field list and local terminology require clinician review. |
| Measurements/laboratory data | WHO materials describe glucose and HbA1c as relevant diagnostic/monitoring measures; HbA1c reflects recent longer-term glycaemia. [S01](#source-register), [S03](#source-register) | Capture measurement name, value, unit, collection date and reference/source; validate units/ranges. | Clinical thresholds, alerts and required tests are not automated protocol rules. |
| Medicines/treatments | Medication history is relevant context; WHO guidance discusses management. [S01](#source-register) | Capture current and previous medicines, allergies and clinician-entered treatment history. | Completeness and coding of medicine history require clinician validation. |
| Outcomes/follow-up | Follow-up and glycaemic monitoring are part of diabetes care. [S01](#source-register), [S03](#source-register) | Store synthetic follow-up/outcome fields where the future selected dataset permits evaluation. | A treatment-response outcome is not supported by the selected candidate dataset. |

The prototype workflow is therefore: validated structured information → risk estimate with explanation → controlled reference options and affordability/facility context → clinician approve/modify/reject → audit. It is not a clinical protocol or diagnosis workflow.

## 3. ML Dataset Research

| Dataset | Source | Size | Features | Target | Treatment information | Outcome information | Missing data | Population | Limitations | Suitability |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| Diabetes 130-US Hospitals for Years 1999–2008 | UCI [S04](#source-register) | 101,766 encounter records | 47 features listed by UCI; demographic, admission, laboratory, diagnosis and medication fields | `readmitted`: `NO`, `>30`, `<30`; UCI states the goal is early readmission within 30 days | Yes—24 diabetes medicines, medication change and diabetes-medication fields are described in the associated publication [S05](#source-register) | Yes—readmission category | UCI indicates missing values; per-field prevalence not verified from the available source | Diabetes-coded hospital encounters across 130 US hospitals/integrated networks, 1999–2008 | Old US data; encounter rather than unique-patient rows; no UCI-verified Type 2-only flag; retrospective associations; possible temporal leakage | **Recommended conditionally** for a measurable demonstration endpoint, not treatment response or prescribing |
| CDC Diabetes Health Indicators | UCI-linked CDC/BRFSS data [S06](#source-register) | 253,680 people | UCI lists 21 features (and describes 35 source features); survey, demographics, history and lifestyle fields | Diabetes / pre-diabetes / healthy classification | No medication/treatment fields identified in UCI description | Diagnosis-status class, not longitudinal response | UCI variable listing reports no missing values for shown variables; full export verification remains Phase 7 work | US survey participants; each row is a person | Survey/self-report context; target is not verified as Type 2; no treatment or clinical longitudinal outcome; source/licence points to linked dataset | Candidate for screening-style exploration only; not selected |
| Early Stage Diabetes Risk Prediction | UCI [S07](#source-register) | 520 | 16: age, gender and symptoms/signs including polyuria, polydipsia, weight loss and obesity | `class`: Positive / Negative | No | Diagnostic class only | UCI metadata says missing values, while its variable table marks listed variables as no missing; discrepancy must be verified before use | Questionnaire patients at Sylhet Diabetes Hospital, Bangladesh | Very small; symptom-based diagnostic target risks circularity/leakage; not verified as Type 2; not treatment/outcome data | Not selected; useful only as a cautionary screening-data example |

For all three candidates, target distributions are **not verified from the primary dataset pages available during this research** unless re-computed from the exact downloaded release in Phase 7. Licences/access: UCI gives CC BY 4.0 for the early-stage dataset; the CDC dataset directs users to the linked source's acknowledgement/licence; the 130-hospital page must be checked at download time for its current use terms. No statistics were inferred from secondary copies.

**Data types reviewed:** UCI describes the 130-hospital release as a mix of categorical and integer-coded encounter fields; the target is categorical. UCI describes the CDC release as categorical/integer and the early-stage release as categorical/integer; their targets are categorical. Exact imported dtypes, sentinel values and per-column missingness are release-dependent and are a Phase 7 verification requirement, not assumed here.

## 4. ML Task and Target Research

### Candidate tasks

| Task | Supporting dataset | Target / inputs | Feasibility and limitation |
| --- | --- | --- | --- |
| 30-day readmission-risk classification | Diabetes 130-US Hospitals | `readmitted == '<30'` versus `NO`/`>30`; discharge-time encounter variables | Measurable outcome and medication context exist. It predicts readmission risk, not efficacy, treatment response, diagnosis, or a drug. Cohort is diabetes-coded, not UCI-verified Type 2-only. |
| Diabetes-status classification | CDC Diabetes Health Indicators | Diabetes/pre-diabetes/healthy class; lifestyle, demographic and survey variables | Large and reproducible candidate, but no treatment information, longitudinal outcome, or verified Type 2 target. |
| Symptom-based diabetes class | Early Stage Diabetes Risk Prediction | Positive/negative class; symptoms/signs | Small and vulnerable to target leakage/circularity; not suitable as the MVP model. |

### Final ML recommendation

- **Disease scope:** Type 2 Diabetes MVP, with the cohort limitation below.
- **Task:** binary, discharge-time estimate of readmission in fewer than 30 days for a diabetes-coded hospital encounter.
- **Dataset:** UCI Diabetes 130-US Hospitals for Years 1999–2008 [S04](#source-register).
- **Target variable:** original `readmitted`; derive `early_readmission = 1` only when its value is `<30`, otherwise `0`. This derivation must be verified against the downloaded data dictionary in Phase 7.
- **Inputs:** `race`, `gender`, `age`, `admission_type_id`, `admission_source_id`, `time_in_hospital`, `num_lab_procedures`, `num_procedures`, `num_medications`, `number_outpatient`, `number_emergency`, `number_inpatient`, `number_diagnoses`, `max_glu_serum`, `A1Cresult`, `diabetesMed`, and `change`.
- **Baseline:** regularised Logistic Regression with documented imputation/encoding.
- **Primary model:** Random Forest; XGBoost is a secondary comparison only if justified after baseline evaluation.
- **Future inference output:** model version; predicted probability of `<30` readmission; a clearly labelled, clinician-configured review flag (not a clinical action); top feature contributions; input/data-quality warnings; timestamp.
- **Evaluation:** stratified train/validation/test split, ROC-AUC, precision, recall, F1, PR-AUC, confusion matrix at the pre-specified review threshold, Brier score/calibration curve, and prevalence. Accuracy is supplementary only because early readmission can be imbalanced.

**Critical limitation and decision:** no source consulted establishes that this dataset is a Type 2-only cohort. It must not be described as a validated Type 2 clinical model. Phase 7 must verify diagnosis-code meanings with a clinical adviser and define a reproducible Type 2 cohort; if that cannot be done, this selected dataset must be rejected or the scope/data decision revisited. No reliable candidate supplied treatment-response data, so treatment-response prediction is not supported. The model will not determine medication selection.

### Data-leakage and split requirements

- Exclude identifiers (`encounter_id`, `patient_nbr`) and the target.
- Exclude `discharge_disposition_id` because it is determined at discharge and may encode future outcome/care pathway information; do not add post-discharge variables.
- Assess every remaining field for availability at the stated prediction time; medication-change fields are permitted only if the use case is explicitly *at discharge*, not admission.
- Group splits by `patient_nbr` if repeated encounters occur, so one patient's encounters cannot appear in both train and test.
- Fit imputation, encoding, scaling, feature selection, threshold selection and any resampling on training data only; lock the held-out test set until final evaluation.
- Report missingness and class distribution before and after exclusions, and stratify where appropriate.

## 5. Medicine Data Research and Decision

PMBI's Jan Aushadhi Product & MRP list exposes product/MRP lookup and download functions; the PMBI/Jan Aushadhi site states that its Sugam application can compare generic and brand MRP/savings. [S08](#source-register), [S09](#source-register). PMBI's searchable catalogue reported an update date in the consulted result, but a price is an MRP, not proof of local stock or dispensing price. NPPA's consumer tools cover brand, composition, ceiling price and MRP for relevant formulations. [S10](#source-register).

**MVP strategy:** create a small, manually curated reference table of Type 2 Diabetes-relevant products from the current PMBI product/MRP list and, where needed, an NPPA-verified brand/composition/MRP reference. Each row requires `generic_name`, `brand_name` (nullable where no comparable brand is verified), `strength`, `form`, `pack_size`, `price`, `currency` (`INR`), `source_url`, `source_name`, `last_verified_at`, and `jan_aushadhi_status`. Store like-for-like pack comparison and show savings only when strength, form and pack size are comparable. Review entries before each demo and at least monthly while actively maintained.

No single verified source was found that guarantees every brand-to-generic relation, current local availability, price, or therapeutic interchangeability. UI must show “MRP/reference price, not availability or a prescription recommendation”, source and last-verified date. No scraping or refresh automation is authorised in this phase.

## 6. Facility and Referral Research

NHM IPHS 2022 provides standards for HWC-PHC, CHC and District/Sub-District Hospitals. It describes standards as benchmarks and allows state/region flexibility, so a facility level cannot be treated as proof that a specific service exists. [S11](#source-register). The PHC guidance describes PHC as a first point of qualified public-sector care and a referral unit to CHCs/higher hospitals; the CHC guidance describes CHCs as referral care from PHCs and specialist-capable facilities. [S12](#source-register), [S13](#source-register). NP-NCD has a management/referral focus. [S02](#source-register).

The ABDM Health Facility Registry (HFR) is a national registry across public and private facilities and exposes facility search/profile information, but the public materials consulted do not guarantee service/test-level completeness or an open bulk service-capability feed. [S14](#source-register), [S15](#source-register).

**MVP facility strategy:** seed a small, synthetic/curated facility reference set. For every facility record store facility ID/name, level (PHC/CHC/District Hospital), location, service/test name, `available`/`unknown`, source URL, verification date and data steward. Treat `unknown` as not confirmed—not as unavailable.

**Conceptual referral logic:** current facility + required service → look up facility-specific status → if available, retain clinician workflow; if unavailable/unknown, list an appropriate *candidate* higher-capability facility using curated hierarchy/location data → clinician decides and records the disposition. Required future inputs: current facility, required service/test, availability status, candidate facility, location/distance data if later enabled, source/verification date, and clinician confirmation. This is logistics support, not a medical referral rule.

## 7. ABDM / ABHA Research

Official ABDM information identifies ABHA, HFR/HPR and Health Information Exchange & Consent Manager (HIE-CM) concepts. ABDM says integrations first use the sandbox; health-information exchange is consent based; production access follows sandbox validation/security processes. [S16](#source-register), [S17](#source-register). Credentials/tokens and sandbox registration are therefore required for real integration and must not enter this repository.

**Decision:** ABDM is optional and isolated behind a future adapter. The MVP uses a mock adapter/no-op data source with synthetic data. It must demonstrate no real ABHA creation, consent request, record retrieval, token storage or API call until later, authorised sandbox work. FHIR/interoperability concepts may guide future internal models but are not an implementation requirement now.

## 8. Privacy and Security Research

The Digital Personal Data Protection Act, 2023 is the relevant Indian legal source consulted; applicability and obligations must be confirmed against the current rules, notifications and actual deployment facts before any real-patient use. [S18](#source-register). ABDM states health-data exchange is with patient consent and uses sandbox/security validation for integrations. [S17](#source-register). NIST's log-management guidance supports protected, managed audit logging. [S19](#source-register).

| Category | Research-backed point | Project requirement |
| --- | --- | --- |
| Legal/regulatory | DPDP Act governs processing of digital personal data; detailed project legal interpretation is not performed here. | Use synthetic data only; obtain legal/clinical review before any real-data processing. |
| Consent | ABDM exchange is consent-based. | No ABDM exchange in MVP; model future consent as an auditable, scoped event. |
| Minimisation | Privacy-first handling is appropriate for sensitive health context. | Collect only prototype fields; do not commit identifiable health data. |
| Access/authentication | Not a claim of legal sufficiency. | Implement authenticated, role-limited clinician access in a later phase; deny by default. |
| Audit and secrets | NIST describes lifecycle log management. | Audit access/analysis/review events without secrets or unnecessary clinical payloads; use environment-managed secrets and `.env.example` only. |
| Retention | Duration is deployment/context dependent. | Define a synthetic-demo retention/deletion policy before Phase 5; do not infer a statutory period here. |

## 9. Research Conclusions

1. Structured demographic, history, medication/allergy, measurement and follow-up fields are reasonable prototype inputs, subject to clinical validation.
2. No researched candidate supports a credible treatment-response or drug-selection model.
3. The conditional best measurable candidate is early readmission risk from UCI's 130-hospital dataset, with strong generalisability/subtype/leakage limitations.
4. PMBI/Jan Aushadhi plus selected NPPA references support a small, provenance-led affordability demonstration—not live price/availability claims.
5. IPHS provides hierarchy/standards, while service status must be facility-specific and curated.
6. ABDM is optional; mock isolation is the appropriate student-MVP approach.

## 10. Open Questions

1. Can a clinician validate a reproducible Type 2-only diagnosis-code cohort in the selected UCI release?
2. Which exact clinical input ranges and required fields should the clinician approve?
3. Which PMBI/NPPA products and brand mappings are verified enough for a small reference dataset?
4. Which state/district and named facilities will be represented, and can their service status be verified?
5. Is authorised ABDM sandbox access desired later, and who will own credentials/security review?
6. What retention/deletion policy applies to any non-synthetic data if the project scope changes?

## 11. Source Register

| ID | Source | Type | URL | Topic | Key information used |
| --- | --- | --- | --- | --- | --- |
| S01 | WHO HEARTS-D | WHO technical guidance | https://www.who.int/publications/i/item/who-ucn-ncd-20.1 | T2D workflow | Primary-care diagnosis/management/monitoring context |
| S02 | MoHFW NP-NCD Operational Guidelines 2023–2030 | Government guidance | https://www.mohfw.gov.in/sites/default/files/NP-NCD%20Operational%20Guidelines.pdf | India NCD workflow | Screening, management and referral context |
| S03 | WHO diabetes training manual | WHO guidance | https://www.who.int/docs/default-source/ncds/diabetes-training-manual.pdf | Measurements | Glucose/HbA1c monitoring context |
| S04 | UCI Diabetes 130-US Hospitals | Dataset repository | https://archive.ics.uci.edu/dataset/296/diabetes-130-us-hospitals-for-years-1999-2008 | Dataset | Scale, context, readmission objective |
| S05 | Diabetes readmission dataset publication summary | Peer-reviewed article | https://pmc.ncbi.nlm.nih.gov/articles/PMC9338420/ | Dataset fields | Medication/change and encounter-field description |
| S06 | UCI CDC Diabetes Health Indicators | Dataset repository | https://archive.ics.uci.edu/dataset/891/cdc-diabetes-health-indicators | Dataset | Size, features, class context, CDC provenance |
| S07 | UCI Early Stage Diabetes Risk Prediction | Dataset repository | https://archive.ics.uci.edu/dataset/529/early-stage-diabetes-risk-prediction | Dataset | Size, symptoms, class, licence |
| S08 | Jan Aushadhi Product & MRP List | Government/PMBI product source | https://janaushadhi.gov.in/productportfolio/ProductmrpList | Medicine price | Search/downloadable MRP product catalogue |
| S09 | PMBJP About | Government/PMBI programme page | https://janaushadhi.gov.in/about-pmbjb | Medicine comparison | Generic/brand comparison feature and programme context |
| S10 | NPPA Annual Report 2021–22 | Government report | https://janaushadhi.gov.in/Data/Annual%20Report%202021-22_04052022.pdf | Price reference | Brand/composition/ceiling-price/MRP consumer tool description |
| S11 | NHM IPHS 2022 index | Government standards | https://www.nhm.gov.in/index1.php?lang=1&level=3&lid=154&sublinkid=284 | Facility hierarchy | 2022 PHC/CHC/DH standards and flexibility |
| S12 | IPHS PHC guidance | Government standards | https://www.nhm.gov.in/images/pdf/guidelines/iphs/iphs-revised-guidlines-2012/primay-health-centres.pdf | PHC role | First-contact and referral context |
| S13 | IPHS CHC guidance | Government standards | https://nhm.gov.in/images/pdf/guidelines/iphs/iphs-revised-guidlines-2012/community-health-centres.pdf | CHC role | PHC referral and specialist-care context |
| S14 | ABDM HFR overview | Official ABDM | https://abdm.gov.in/health-facilities | Facility registry | HFR scope |
| S15 | NHPR/HFR public search | Official registry | https://nhpr.abdm.gov.in/nhpr/v4/hfr/publicSearch | Facility data | Facility profile/search fields visible |
| S16 | ABDM health-tech companies | Official ABDM | https://abdm.gov.in/health-tech-companies | Sandbox | Sandbox/API integration path |
| S17 | ABDM FAQ | Official ABDM | https://abdm.gov.in/faqs | Consent/sandbox | HIE-CM, sandbox and testing statements |
| S18 | Digital Personal Data Protection Act, 2023 | India Code statute | https://www.indiacode.nic.in/handle/123456789/22037 | Privacy | Legal source and current rules/notification register |
| S19 | NIST SP 800-92 | Security guidance | https://csrc.nist.gov/pubs/sp/800/92/final | Audit logs | Log-management guidance |
