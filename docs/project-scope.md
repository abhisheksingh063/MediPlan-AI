# MediPlan AI — Project Scope (Phase 1)

## 1. Project Name

**MediPlan AI**

## 2. Project Vision

MediPlan AI is an AI-assisted personalised treatment decision-support platform. It combines patient-specific structured clinical information, ML-based treatment-response or risk estimation, explainability, medicine affordability, healthcare-facility capability, referral intelligence, and clinician review in one workflow.

The platform supports—not replaces—clinical judgement. A clinician remains the final decision-maker for every analysis and any resulting care decision.

## 3. Problem Statement

Treatment-support tools can focus narrowly on clinical prediction while overlooking practical constraints that materially affect care: medicine affordability, availability of required tests and services, healthcare-facility capability, and realistic referral pathways. MediPlan AI brings these considerations together as clinician-reviewable decision support.

## 4. MVP Boundary

### MVP disease

The MVP is limited to **Type 2 Diabetes**. Hypertension and all other diseases are future scope and will not be added to the initial MVP.

### MVP ML objective

The ML component will estimate a measurable treatment-response or risk outcome (or another defensible, dataset-supported target selected during data research and preparation). It will not predict which drug a patient should take, and no model output will be an arbitrary medicine name.

### Intended use

This is a software-only, clinical decision-support prototype demonstrated exclusively with synthetic/test patients. It is not a real-patient clinical deployment.

## 5. Committed MVP Features

### Patient management

- Synthetic patient creation and selection
- Patient profile and clinical records
- Medical history and allergies
- Current medications and previous treatments
- Laboratory results

### Clinical data validation

- Required-field validation
- Missing-value handling
- Unit validation
- Sensible range validation
- Input-consistency checks

### ML engine

- Data preprocessing
- Baseline and primary models
- Evaluation metrics
- Model versioning
- Inference for the selected defensible outcome

### Explainability

- Feature importance and/or SHAP
- Human-readable explanation of the result
- Clear wording that model associations are not causal medical conclusions

### Treatment decision support

- Controlled, reviewable treatment-support options
- Clinician review with approve, modify, or reject actions
- No automatic prescription

### Medicine affordability

- Generic-to-brand relationship
- Strength and form where applicable
- Price, price source, and last-verified date
- Affordability comparison and potential savings

### Facility and referral intelligence

- PHC, CHC, and District Hospital facility levels
- Available tests and services
- Facility-capability assessment
- Referral recommendation when a required service is unavailable

### Audit

- Analysis timestamp and model version
- System and clinician-review actions
- Data-source/reference information

## 6. Safety and Ethical Boundaries

1. MediPlan AI is a clinical decision-support prototype, not a replacement for a clinician.
2. Every AI-supported output requires clinician review.
3. The system must never autonomously diagnose or automatically prescribe.
4. Demonstrations must use only synthetic/test patient data.
5. No real identifiable patient information may be committed to the repository.
6. API keys, credentials, database passwords, and tokens must never be committed.
7. Health data must be minimised to what the prototype needs.
8. Model limitations, dataset bias, and evaluation limits must be documented.
9. Medicine price and availability data must show a source and verification date.
10. The project must not make unsupported clinical-efficacy claims.

## 7. Main User and Workflow

The primary MVP user is a **clinician**.

Patient selection/creation → clinical information → validation → Run AI Analysis → ML result → explanation → treatment-support options → medicine affordability → facility/service availability → referral recommendation → clinician review → audit entry.

The product design and later implementation phases will centre this clinician-reviewable workflow.

## 8. Feature Priority

### Must Have — MVP

- Patient management
- Clinical data validation
- ML pipeline and model evaluation
- Explainability
- Treatment decision support
- Medicine affordability comparison
- Facility/service availability and referral intelligence
- FastAPI backend, React frontend, and PostgreSQL database
- Audit trail
- Synthetic demo patients

### Should Have

- JWT or session-based authentication
- SHAP visualisation
- Responsive dashboard and charts
- Docker Compose
- Strong API testing
- Detailed audit UI

### Could Have / Stretch

- ABDM/ABHA adapter and sandbox workflow
- Maps
- FHIR-compatible internal models
- Multilingual UI
- Additional disease models
- Automated medicine-data refresh

### Explicitly Out of Scope for MVP

- Autonomous diagnosis or prescribing
- Medication ordering
- Real-patient deployment
- Medical hardware or sensors
- Large-scale hospital information system
- Training an LLM or foundation model from scratch
- Mandatory ABDM/ABHA integration

ABDM/ABHA is an optional stretch module. Its failure or unavailability must not block the core MVP workflow.

## 9. MVP Success Criteria

The MVP is successful when:

1. A clinician can create or select a synthetic patient.
2. Clinical information can be entered and validated.
3. The backend processes the patient information.
4. The ML model produces a measurable prediction, risk estimate, or treatment-response estimate.
5. Model evaluation metrics are documented.
6. Important model features are explained.
7. Controlled treatment-support options are shown for clinician review.
8. Brand/generic medicine comparisons are displayed.
9. Medicine price, source, and verification information are visible.
10. The system determines whether a required service exists at the current facility level.
11. A referral recommendation is produced when required.
12. The clinician can approve, modify, or reject AI-supported output.
13. Analysis and review actions are recorded in an audit trail.
14. The frontend → backend → database → ML workflow functions end to end.
15. The demo uses only synthetic/test data.
16. The application clearly states it is decision support, not autonomous prescribing.
17. No hardware is required.
18. ABDM failure or unavailability does not prevent the core MVP workflow.

## 10. Major Project Constraints

### Technical

- Frontend: React + Vite
- Backend: Python + FastAPI
- Database: PostgreSQL
- ML: scikit-learn with Random Forest and/or XGBoost
- Explainability: SHAP and/or feature importance
- Data processing: pandas + NumPy
- Charts: Recharts or Chart.js
- Version control: Git + GitHub
- Docker Compose: recommended for reproducibility, but not required for every development operation

### Project

- Software-only implementation
- Synthetic/test data for the MVP
- One disease and one defensible ML target for the MVP
- Small, curated reference datasets
- Clinician-reviewable outputs

## 11. Future Roadmap

- Phase 2 — Research & Requirements
- Phase 3 — Product & UX Design
- Phase 4 — Architecture & Repository Setup
- Phase 5 — Database & Data Model
- Phase 6 — Patient Management
- Phase 7 — Data Preparation
- Phase 8 — Baseline ML Model
- Phase 9 — Primary ML Model
- Phase 10 — Explainable AI
- Phase 11 — Treatment Decision-Support Layer
- Phase 12 — Medicine Affordability
- Phase 13 — Facility & Referral Intelligence
- Phase 14 — FastAPI Integration
- Phase 15 — Frontend Dashboard
- Phase 16 — ABDM/ABHA Adapter
- Phase 17 — Security, Privacy & Audit
- Phase 18 — Testing & Model Validation
- Phase 19 — Deployment & Monitoring
- Phase 20 — Final Demo, Documentation & Presentation

No future roadmap phase is implemented as part of Phase 1.
