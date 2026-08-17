# MediPlan AI

MediPlan AI is an AI-assisted personalised treatment decision-support prototype for Type 2 Diabetes. It is intended to combine structured clinical information, defensible ML-based risk or treatment-response estimation, explainability, affordability comparisons, facility capability, referral intelligence, and clinician review.

## Current Phase

**Phase 2 — Research & Requirements.** This repository contains planning and research documentation only; application components have not yet been implemented.

## MVP Scope

The MVP supports synthetic/test patients only and is designed for clinician review. Its committed areas are patient management, clinical-data validation, ML estimation and evaluation, explainability, controlled treatment-support options, medicine affordability comparison, facility/referral intelligence, and an audit trail.

## Planned Technology Stack

React + Vite, Python + FastAPI, PostgreSQL, scikit-learn, Random Forest and/or XGBoost, SHAP and/or feature importance, pandas, NumPy, and Recharts or Chart.js. Docker Compose is recommended for reproducibility.

## Safety Disclaimer

MediPlan AI is a decision-support prototype, not a diagnostic, prescribing, or medication-ordering system. It does not replace a clinician. AI-supported output requires clinician review, demonstrations use synthetic/test data, and ABDM/ABHA is optional rather than an MVP dependency.

## Development Roadmap

Next: Phase 3 — Product & UX Design. The Phase 1 scope is in [docs/project-scope.md](docs/project-scope.md); Phase 2 research and requirements are in [docs/research.md](docs/research.md) and [docs/requirements.md](docs/requirements.md).
