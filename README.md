# MediPlan AI

MediPlan AI is an AI-assisted personalised treatment decision-support prototype for Type 2 Diabetes. It is intended to combine structured clinical information, defensible ML-based risk or treatment-response estimation, explainability, affordability comparisons, facility capability, referral intelligence, and clinician review.

## Current Phase

**Phase 5 — Database & Data Model.** PostgreSQL persistence foundation: SQLAlchemy models for patients, clinical records, lab results, medicines/prices, facilities/services, predictions, referrals, and audit logs; Alembic initial migration; and demo seed infrastructure. Application features have not yet been implemented. See [docs/database.md](docs/database.md).

## MVP Scope

The MVP supports synthetic/test patients only and is designed for clinician review. Its committed areas are patient management, clinical-data validation, ML estimation and evaluation, explainability, controlled treatment-support options, medicine affordability comparison, facility/referral intelligence, and an audit trail.

## Planned Technology Stack

React + Vite, Python + FastAPI, PostgreSQL, scikit-learn, Random Forest and/or XGBoost, SHAP and/or feature importance, pandas, NumPy, and Recharts or Chart.js. Docker Compose is recommended for reproducibility.

## Project Structure

```text
backend/        FastAPI application foundation
frontend/       React + Vite application foundation
data/           Future raw, processed, medicine, and facility reference data
models/         Future reviewed model artifacts
scripts/        Future reproducible scripts
infrastructure/ Future infrastructure configuration
docs/           Scope, research, requirements, UX, and architecture records
```

## Local Development Foundation

1. Copy `.env.example` to `.env` and set a local PostgreSQL password.
2. Start PostgreSQL: `docker compose up -d postgres`.
3. Create the schema: `cd backend`, `python -m alembic upgrade head`.
4. (Optional) Seed demo data: `python scripts/seed.py --demo` from the repository root.
5. Install and run the backend: `python -m pip install -r backend/requirements.txt`, then `python -m uvicorn app.main:app --app-dir backend --reload`.
6. Install and run the frontend: `cd frontend`, `npm install`, then `npm run dev`.

The only current backend route is `GET /health`, a local liveness check. Application functionality is intentionally deferred to later phases. See [docs/architecture.md](docs/architecture.md) for boundaries and conventions.

## Safety Disclaimer

MediPlan AI is a decision-support prototype, not a diagnostic, prescribing, or medication-ordering system. It does not replace a clinician. AI-supported output requires clinician review, demonstrations use synthetic/test data, and ABDM/ABHA is optional rather than an MVP dependency.

## Development Roadmap

Next: Phase 6 — Patient Management. The Phase 1 scope is in [docs/project-scope.md](docs/project-scope.md); Phase 2 research and requirements are in [docs/research.md](docs/research.md) and [docs/requirements.md](docs/requirements.md); Phase 3 UX design is in [docs/ux-design.md](docs/ux-design.md); architecture is in [docs/architecture.md](docs/architecture.md); the database model is in [docs/database.md](docs/database.md).
