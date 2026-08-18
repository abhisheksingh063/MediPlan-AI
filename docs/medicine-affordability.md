# Medicine Affordability Comparison (Phase 14)

> **This module provides medicine information and affordability comparison. It does not prescribe treatment.**

Prototype endpoints (read-only, served from a curated reference snapshot):

```
GET /api/v1/medicines
GET /api/v1/medicines/{medicine_id}
GET /api/v1/medicines/compare?generic=Metformin
GET /api/v1/medicines/compare?therapeutic_class=anti-hypertensive
```

> **Reference MRP only; not stock availability, therapeutic interchangeability, or prescribing advice.**

## Objective

A transparent medicine-information and affordability-comparison layer. It
answers *"what medicine information and pricing exists"*, never *"what should
this patient receive"*. It must not prescribe, auto-select a medicine, supply
dosage instructions, imply cheapest is clinically best, or convert ML
risk / SHAP / Phase 13 considerations into a medicine recommendation.

## Geographic scope and currency — why India / INR

Chosen scope (Option A from the phase brief): **India, prices in INR (₹)**.

Rationale:

- The PMBJP (Pradhan Mantri Bhartiya Janaushadhi Pariyojana) and NPPA are
  **public, government-issued** price sources well suited to a
  government-adjacent prototype, and were already selected as the sourcing
  strategy in `docs/research.md` §5 and `docs/requirements.md` (FR-MED-001/002,
  NFR-DATA-001).
- **This scope is independent of the origin of the clinical dataset.** The
  ML model (Phases 1–13) was trained on the UCI Diabetes 130-US Hospitals
  data (a US population). Nothing in this module claims the priced Indian
  medicines apply specifically to that US hospital population. The API
  carries this independence statement in every response (`scope_note`), and
  every medicine record carries `geographic_scope: "India"` and
  `currency: "INR"`.

## Data sources and licensing basis

Only public, governmental, or explicitly licensed sources are used. No prices
were invented and no commercial retailer/pharmacy sites (1mg, PharmEasy,
GoodRx, etc.) were scraped or redistributed.

| Source | Type | Used for | URL |
| --- | --- | --- | --- |
| PMBJP / Jan Aushadhi Product & MRP List (Government of India, Department of Pharmaceuticals) | Government | Jan Aushadhi generic prices (Metformin ₹6.19/10, Glimepiride ₹4.13/10, Atorvastatin ₹8.25/10, Amlodipine ₹5.16/10, Telmisartan ₹11.25/10) | https://janaushadhi.gov.in/productportfolio/ProductmrpList |
| NPPA ceiling price list, S.O. 1575(E) (Government of India) | Government / regulatory | Regulatory ceiling price (Paracetamol 500 mg ≤ ₹0.93/tablet, effective 2026-04-01) | https://nppa.gov.in/en/listofnotifiedprice |
| Public PMBJP-database mirrors (Generic Drug Scan, Jan Aushadhi Kendra Bhadohi; public informational pages, dated 2021 and 2026) | Public reference | Historical comparisons and brand MRP reference (Metformin brand ₹30/10) | see per-record `source_url` |

Every price record stores `source`, `source_url`, `source_date`,
`retrieved_date`, `geographic_scope`, `currency`, `availability`
(`jan_aushadhi` | `brand` | `unknown`) and a provenance note. Where two
sources report different prices for the same medicine and pack, both are
shown with their own attribution; the system does not average, pick, or
resolve conflicts on the clinician's behalf.

## Schema (file-based, versioned — no database change)

Reference data is a **static, versioned JSON file**:
`backend/app/medicines/medicines.json` (schema_version 1.0). This follows the
phase instruction to prefer static reference data over new storage when
persistence is not needed, and the exact in-package loading pattern used by
Phase 13 (`app/treatment_support/`). No database schema changes were made in
this phase; the pre-existing `medicines`/`medicine_prices` ORM models and demo
seed from earlier phases are deliberately left untouched and are not served
by this module.

Medicine fields: `medicine_id`, `generic_name`, `brand_name`, `strength`,
`form`, `pack_size`, `pack_size_units`, `therapeutic_class`, `manufacturer`,
`geographic_scope`, `currency`, and `prices[]`.

Price fields: `price` (nullable), `price_unit`, `unit_price` (computed),
`source`, `source_url`, `source_date`, `retrieved_date`, `availability`,
`stale` (computed), `geographic_scope`, `currency`, `notes`.

## Staleness rule (fixed, numeric)

**Any price whose `source_date` is more than 180 days before the dataset's
`as_of_date` is flagged `stale: true` and visibly marked in the response; it
is never shown as current.** The rule is fixed at 180 days in
`medicines.json` (`staleness_rule_days`). The PMBJP list is revised through
new tenders and annual NPPA/WPI price adjustments; 180 days is a reasonable
conservative default between such revisions and is stated here as the
governing rule. Mind that `as_of_date` (2026-08-18), not wall-clock time, is
the reference, so the flags are deterministic and reproducible.

## Affordability methodology

- **Package price** and **price-per-unit** are computed from data actually on
  hand: `unit_price = price / pack_size_units`.
- **Monthly treatment cost is never computed** without an explicit clinician
  regimen. No assumed dosage is applied. Labels are limited to "Package
  price" / "Price per tablet".
- **Missing price ⇒ `price: null` and "Price unavailable."** in the record —
  never a guessed value, never silently zero.

## Grouping and comparison logic

- Medicines are **grouped by a comparability key** — generic ingredient +
  strength + form — before any price comparison. A flat list mixing
  unrelated medicines by price is never produced.
- Within a group, items are ordered by the **lowest reported unit price**
  (ascending), price-unavailable items last. The label is "Lower reported
  price" — never "Best option" or "Recommended".
- Multiple sources for the same medicine/pack are shown **together,
  unresolved**, each with its own source and date.
- Filtering is optional and read-only: by `generic` name and/or
  `therapeutic_class`.
- Comparison is read-only; no order or prescription creation exists.

## API

All three endpoints are read-only and every response envelope carries
`geographic_scope`, `currency`, `as_of_date`, `staleness_rule_days`,
`safety_message`, and `scope_note`.

- `GET /api/v1/medicines` — list with summary aggregates (`has_price`,
  `lowest_reported_price`, `lowest_price_source`, `stale_available`).
- `GET /api/v1/medicines/{medicine_id}` — full record with all reported
  prices; unknown id returns 404 "Medicine not found".
- `GET /api/v1/medicines/compare` — grouped comparison; unknown/no-match
  filters return an empty group list (200), handled without error.

Standard safety message carried on every response:

> "Medicine information and affordability comparison only. This does not constitute a prescription or treatment recommendation."

## Safety boundaries

- **Banned wording** is enforced in tests: "Take/Start/Stop/Prescribe",
  "Best medicine", "Best option", "Recommended drug", "You should use",
  "the AI recommends".
- `app/services/medicines.py` and `app/api/medicines.py` do **not import**
  the inference, explainability, or treatment-support services (asserted by
  tests). ML probability, the 0.10 threshold, SHAP contributions, and Phase
  13 considerations can never function as medicine-selection logic.
- No dosage/regimen logic, no drug-to-patient mapping, no diagnosis.

## Verification

- 33 new tests in `tests/test_medicines.py`: reference-data provenance and
  uniqueness, missing price stays null, staleness boundary (179 vs 181 days),
  unit-price math, grouping before comparison, unresolved multi-source
  display, per-record and per-response scope/currency, banned-word scan,
  module isolation from ML/Phase 13, and API behaviours (list/detail/compare,
  unknown id 404, empty results, missing price, read-only).
- Full suite: **200 tests green** (Phases 1–13 regression intact — ML
  prediction, SHAP output, Phase 13 rules, and the 0.10 threshold verified
  unchanged during smoke tests).

## Limitations

- The dataset is a small curated snapshot (8 medicines / 10 price records),
  not a live feed; automated medicine-data refresh is out of scope.
- Prices are reference figures as published; changing market/regulatory
  prices are the reader's responsibility to re-verify against the cited
  source (each record carries its source URL and dates for that purpose).
- One brand-side record (MED-004) intentionally has no verified price and is
  shown as "Price unavailable".
- Jan Aushadhi kendra stock availability is not tracked (a facility/referral
  concern, out of scope).
- ABDM/ABHA integration remains permanently out of scope.