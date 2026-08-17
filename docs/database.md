# MediPlan AI — Database & Data Model (Phase 5)

## 1. Overview

Phase 5 establishes the PostgreSQL persistence foundation for MediPlan AI. The schema is implemented with **SQLAlchemy 2.0** (typed `Mapped`/`mapped_column` declarative style) and versioned with **Alembic**. The Phase 4 Compose PostgreSQL 16 service is reused unchanged; no new container or database engine was introduced.

The schema follows the Phase 2 blueprint ([requirements.md](requirements.md)) and deliberately avoids later-phase concerns: there are no API endpoints, authentication, ML artifacts, or referral/business logic in the database layer.

## 2. Database Architecture

```text
patients  ─┬─ clinical_records  ── lab_results
           ├─ treatment_predictions
           └─ referrals ── (current facility) ─┐
                                                │
facilities ── facility_services                 │
                                                │
medicines ── medicine_prices                    │
                                                │
patients.current_facility_id ───────────────────┘

audit_logs  (standalone, reference-only)
```

- **Technology:** PostgreSQL 16 (Docker Compose service from Phase 4), SQLAlchemy 2.0, Alembic.
- **Driver:** `psycopg` v3 (`postgresql+psycopg://...`).
- **Models location:** `backend/app/models/`.
- **Migration location:** `backend/alembic/versions/`.
- **Configuration:** `backend/app/core/config.py` (environment-driven, see §8).

## 3. Tables and Important Fields

### `patients`

Synthetic patient demographic context.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | Primary key |
| `external_reference` | varchar(32) | no | **Unique**; synthetic reference (e.g. `SYN-204`) |
| `age` | integer | yes | |
| `sex` | varchar(16) | yes | Plain string; validation is a later phase |
| `height` | numeric(6,2) | yes | |
| `weight` | numeric(6,2) | yes | |
| `current_facility_id` | int FK → `facilities.id` | yes | `ON DELETE SET NULL` |
| `created_at` | timestamptz | no | `server_default now()` |

### `clinical_records`

A dated, clinician-entered clinical snapshot per patient.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `patient_id` | int FK → `patients.id` | no | **Indexed**; `ON DELETE CASCADE` |
| `condition` | varchar(256) | yes | e.g. "Type 2 Diabetes" |
| `history_text` | text | yes | |
| `allergies` | text | yes | |
| `current_medications` | text | yes | |
| `previous_treatments` | text | yes | |
| `recorded_at` | timestamptz | no | `server_default now()` |

### `lab_results`

A single measurement linked to a clinical record. Reference ranges are free text and are **not** encoded as rules.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `clinical_record_id` | int FK → `clinical_records.id` | no | **Indexed**; `ON DELETE CASCADE` |
| `test_name` | varchar(128) | no | e.g. "HbA1c" |
| `value` | double precision | no | Measurements, not money |
| `unit` | varchar(32) | yes | |
| `reference_range` | varchar(256) | yes | Display-only reference text |
| `recorded_at` | timestamptz | no | |

### `medicines`

A product-level medicine entry. `pack_size` is stored here (a product attribute) so later like-for-like comparisons (FR-MED-002) can be constrained by strength/form/pack.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `generic_name` | varchar(256) | no | |
| `brand_name` | varchar(256) | yes | Nullable where no comparable brand is verified |
| `strength` | varchar(64) | yes | e.g. "500 mg" |
| `form` | varchar(64) | yes | e.g. "tablet" |
| `pack_size` | varchar(64) | yes | Product attribute, added beyond the field list because FR-MED-001/002 require pack-aware comparison |

Unique constraint `uq_medicines_product` on `(generic_name, brand_name, strength, form, pack_size)`.

> Note: PostgreSQL treats `NULL`s as distinct in unique constraints, so two rows with the same generic name and `NULL` brand would not collide. Curated data should avoid that ambiguity; validation is Phase 12/13 work.

### `medicine_prices`

Verified reference MRP prices with provenance (FR-MED-001, NFR-DATA-001).

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `medicine_id` | int FK → `medicines.id` | no | **Indexed**; `ON DELETE CASCADE` |
| `source` | varchar(128) | no | e.g. "Jan Aushadhi product list" |
| `source_url` | text | yes | Added for provenance (research §5); nullable |
| `price` | numeric(12,2) | no | **Exact decimal — never float** |
| `currency` | varchar(3) | no | Default `INR` (Python and server default) |
| `last_verified_at` | timestamptz | no | `server_default now()` |
| `jan_aushadhi_status` | varchar(32) | yes | e.g. `jan_aushadhi`, `brand`, `unknown` |

### `facilities`

Named facility with a Level stored as a plain string so the PHC/CHC/District Hospital hierarchy is supported without hard-coding capabilities (FR-FAC-001).

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `name` | varchar(256) | no | |
| `facility_type` | varchar(64) | no | e.g. `phc`, `chc`, `district_hospital` |
| `district` | varchar(128) | yes | |
| `state` | varchar(128) | yes | |

### `facility_services`

Facility-specific service availability (FR-FAC-001/002).

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `facility_id` | int FK → `facilities.id` | no | **Indexed**; `ON DELETE CASCADE` |
| `service_name` | varchar(256) | no | |
| `availability_status` | varchar(16) | no | `available`, `unavailable`, `unknown` (default `unknown`) |

Unique constraint `uq_facility_services_service` on `(facility_id, service_name)`.

### `treatment_predictions`

A versioned model run for a patient. The Phase 2 ML decision is a conditional 30-day readmission-risk estimate; **this schema does not assume a drug-prescription output** (FR-ML-003, project-scope architectural boundary).

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `patient_id` | int FK → `patients.id` | no | `ON DELETE CASCADE` |
| `model_version` | varchar(64) | no | |
| `option_name` | varchar(128) | no | Label for the predicted outcome/option |
| `score` | double precision | no | Probability / score for the option |
| `explanation_json` | jsonb | yes | Explanations such as feature contributions |
| `created_at` | timestamptz | no | |

Index `ix_treatment_predictions_patient_id_created_at` on `(patient_id, created_at)`.

### `referrals`

Clinician-reviewable candidate referral (FR-REF-001); logistics support, not an automatic referral.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `patient_id` | int FK → `patients.id` | no | **Indexed**; `ON DELETE CASCADE` |
| `required_service` | varchar(256) | no | |
| `current_facility_id` | int FK → `facilities.id` | yes | **Indexed**; `ON DELETE SET NULL` (facility reference data may be realigned later) |
| `recommended_facility_level` | varchar(64) | yes | |
| `reason` | text | yes | |
| `created_at` | timestamptz | no | |

### `audit_logs`

Append-only, attributable audit of analysis/review activity (FR-AUD-001/002). Stores references, not sensitive payloads. `patient_reference` is deliberately a plain string rather than a foreign key so the trail remains readable and stable if patient rows change.

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | integer PK | no | |
| `actor_id` | varchar(128) | yes | Populated once authentication exists (Phase 17) |
| `action` | varchar(128) | no | e.g. `analysis_created`, `review_approved` |
| `model_version` | varchar(64) | yes | Nullable for non-ML actions |
| `patient_reference` | varchar(32) | yes | Synthetic reference, not a FK |
| `created_at` | timestamptz | no | |

Index `ix_audit_logs_patient_reference_created_at` on `(patient_reference, created_at)`.

## 4. Relationships

| Relationship | Cardinality | Behaviour |
| --- | --- | --- |
| Patient → Clinical Records | 1 : N | DB `ON DELETE CASCADE`; ORM `cascade="all, delete-orphan"`, `passive_deletes=True` |
| Clinical Record → Lab Results | 1 : N | DB `ON DELETE CASCADE`; ORM cascade delete-orphan |
| Patient → Predictions | 1 : N | DB `ON DELETE CASCADE`; ORM cascade delete-orphan |
| Patient → Referrals | 1 : N | DB `ON DELETE CASCADE`; ORM cascade delete-orphan |
| Patient → Current Facility | N : 1 | FK with `ON DELETE SET NULL`; referential only |
| Facility → Services | 1 : N | DB `ON DELETE CASCADE`; ORM cascade delete-orphan |
| Medicine → Prices | 1 : N | DB `ON DELETE CASCADE`; ORM cascade delete-orphan |
| Referral → Current Facility | N : 1 | FK with `ON DELETE SET NULL` |

All foreign keys are real DB constraints with explicit `ON DELETE` actions (see §3). ORM relationships are configured deliberately (cascades declared, back-populates used) rather than relying on defaults.

## 5. Constraints and Indexes

- **Primary keys:** integer auto-increment `id` on every table (single consistent strategy).
- **Uniqueness:**
  - `patients.external_reference`
  - `medicines (generic_name, brand_name, strength, form, pack_size)`
  - `facility_services (facility_id, service_name)`
- **Indexes (besides the above):**
  - `clinical_records.patient_id`
  - `lab_results.clinical_record_id`
  - `medicine_prices.medicine_id`
  - `facility_services.facility_id`
  - `referrals.patient_id`, `referrals.current_facility_id`
  - `treatment_predictions (patient_id, created_at)`
  - `audit_logs (patient_reference, created_at)`
- **Non-nullable fields** are used where a value is always expected (e.g. `action`, `service_name`, `price`, `score`); demographic/optional context stays nullable.
- A shared **naming convention** on the metadata gives deterministic constraint names (`pk_*`, `fk_*`, `uq_*`, `ix_*`), which keeps migrations reproducible.

## 6. Design Decisions

| Decision | Rationale |
| --- | --- |
| Integer auto-increment PKs | Single consistent strategy across all models; adequate for a synthetic prototype. |
| Timezone-aware timestamps | `created_at`/`recorded_at`/`last_verified_at` are `timestamptz`. |
| `price` is `Numeric(12,2)` | Money is never stored as float (exact decimal). |
| `explanation_json` is JSONB | PostgreSQL-native JSONB for structured explainability payloads. |
| No enums for `sex`/`facility_type`/`availability_status` | Plain strings keep migrations and demo data flexible; validation belongs to later phases. |
| No DB-level check constraints on score/ranges | Sensible-range/unit validation is explicitly Phase 6/7 application logic, per the blueprint; reference ranges are not hard-coded. |
| `medicines.pack_size` and `medicine_prices.source_url` added | Required by FR-MED-001 and research §5 for provenance and like-for-like comparison; documented above. |
| `audit_logs.patient_reference` is not a FK | Keeps the audit trail stable and readable (FR-AUD-001/002). |

## 7. Migration Process (Alembic)

Alembic is configured in `backend/` (`alembic.ini`, `backend/alembic/`). The database URL is resolved at runtime from `app.core.config.Settings`, so no credentials live in `alembic.ini`.

```bash
# From the repository root (with PostgreSQL running via docker compose)
cd backend
.venv\Scripts\activate                      # or use the venv python directly
python -m alembic upgrade head              # apply all migrations
python -m alembic current                   # show current revision
python -m alembic downgrade base            # revert all (validated, optional)
```

Creating a new migration after model changes:

```bash
python -m alembic revision --autogenerate -m "describe the change"
# review the generated file in backend/alembic/versions/ before applying
python -m alembic upgrade head
```

**Validation performed in Phase 5:** `alembic upgrade head` on an empty database → all 10 tables created; `alembic downgrade base` reverted cleanly; `alembic upgrade head` re-applied successfully on the same (now clean) database, proving repeatability.

## 8. Local Database Setup and Environment Variables

Copy `.env.example` to `.env` at the repository root and set a local password, then start the Phase 4 Compose service:

```bash
docker compose up -d postgres
```

Environment variables (all defined in `.env.example`):

| Variable | Purpose | Default |
| --- | --- | --- |
| `POSTGRES_DB` | Database name | `mediplan_ai` |
| `POSTGRES_USER` | Database user | `mediplan_dev` |
| `POSTGRES_PASSWORD` | Local password (never commit) | — |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Host port mapped to PostgreSQL | `5432` |
| `DATABASE_URL` | Optional full URL override (takes precedence over the `POSTGRES_*` composing) | unset |
| `BACKEND_PORT` | Reserved FastAPI port | `8000` |
| `VITE_API_BASE_URL` | Frontend API base URL | `http://localhost:8000` |

The backend composes `postgresql+psycopg://<user>:<password>@<host>:<port>/<db>` unless `DATABASE_URL` is set. Tests use a dedicated `mediplan_ai_test` database.

Backend dependencies were extended: see `backend/requirements.txt` (runtime) and `backend/requirements-dev.txt` (`-r requirements.txt` plus `pytest`).

## 9. Seed Process

`scripts/seed.py` inserts a minimal, clearly-labelled **synthetic/demo** dataset used only to verify the schema and relationships. It is idempotent (safe to re-run).

```bash
python scripts/seed.py --demo
```

Seed contents (all marked synthetic or public-reference): three facilities (PHC, CHC, District Hospital), five facility-service rows with `available`/`unknown` status, two metformin product rows (Jan Aushadhi generic + example brand) with sourced, dated reference prices, one synthetic patient (`SYN-DEMO-001`), one clinical record, and one lab result. No real identifiable patient data is ever seeded.

## 10. Tests

Database-layer tests live in `backend/tests/` (pytest; run from `backend/`):

```bash
python -m pytest
```

Tests are isolated from the development database by using a dedicated `mediplan_ai_test` database whose schema is rebuilt from ORM metadata; every test runs in a rolled-back transaction. They verify:

- All 10 expected tables are created.
- Patient → ClinicalRecord → LabResult relationships.
- Medicine → MedicinePrice and Facility → FacilityService relationships.
- Patient → TreatmentPrediction and Patient → Referral relationships.
- Foreign-key enforcement (`IntegrityError` on a bad `patient_id`).
- Unique `external_reference` enforcement.
- Exact (numeric, non-float) money round-trip for prices.
- Timezone-aware timestamps.
- DB-level cascade delete for patients and `SET NULL` for facilities.
- Audit-log creation for analysis/review actions.

## 11. Out of Scope (deliberately not implemented)

Patient CRUD APIs, clinical-data validation endpoints, authentication, ML training/inference, SHAP/explainability services, treatment decision logic, medicine comparison API, referral engine, ABDM adapter, React screens, dashboard, and production deployment all belong to later phases and are **not** part of this database layer.