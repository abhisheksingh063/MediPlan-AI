# Facility & Referral Intelligence (Phase 15)

> **This module provides facility and referral-support information. It does not autonomously refer patients or make clinical referral decisions.**

Prototype endpoints (read-only, served from a curated reference snapshot):

```
GET /api/v1/facilities                (unchanged Phase 4: DB-backed current-facility lookup for patient records)
GET /api/v1/facilities/search         (criteria-filtered facility reference)
GET /api/v1/facilities/{facility_id}  (full record with provenance)
GET /api/v1/referrals/options         (referral-support candidates for a required service)
```

Every referral-related result carries: **"Referral support only — clinician review required."**

## Objective

Facility information + referral-support intelligence for clinicians. The module
answers *"what facility information and referral options exist"*, never
*"which facility should this patient go to"*. It does not autonomously refer,
book an appointment, contact a facility, auto-select a facility as a clinical
decision, guarantee availability, or imply one facility is clinically superior.

Three concepts are kept strictly distinct:

| Concept | Meaning |
| --- | --- |
| **Facility information** | Sourced fact about a named facility (identity, capabilities, status, provenance). |
| **Referral intelligence** | Criteria-matched candidates, labeled "Potentially relevant facility" / "Matches selected criteria". |
| **Clinical referral decision** | The clinician's own act; the system never performs or completes it. |

## Geographic scope — matches Phase 14 (India)

Phase 14 established India/INR as the pricing scope. Facility data uses the
**same geographic scope (India)** so a referral candidate never implies a
different region from the affordability context. Every facility record and
every API response carries `geographic_scope: "India"`. The scope is
independent of the origin of the ML clinical dataset (UCI Diabetes 130-US
Hospitals); each response's `scope_note` states this independence explicitly.

## Source selection and the ABDM/HFR exclusion

**ABDM's Health Facility Registry (HFR) — and any ABDM-adjacent API — was
deliberately NOT used**, even though it would be the most authoritative source
of Indian facility data. ABDM/ABHA integration is permanently out of scope, and
pulling from HFR would be a backdoor into it (per the phase brief).

Instead, this phase uses a **small, explicitly hand-curated and documented
reference dataset** (`backend/app/facilities/facilities.json`) built only from
named, dated, public (non-ABDM) sources:

| Source | Type | Used for |
| --- | --- | --- |
| Official Delhi Government hospital websites (`*.delhi.gov.in`: DDUH, GGSGH, ANH, JPCH, and the Delhi Govt Hospitals directory `health.delhi.gov.in`, last updated 2026-08-18) | Government | Facility identity, addresses, phones, emails, emergency-service availability with page dates |
| DGHS Emergency Medical Care guidelines (`dgehs.delhi.gov.in`, last updated 2026-08-13) | Government | Facility-level capability facts (CT+ICU+ventilator hospitals, ICCU hospitals, regional blood-transfusion centres; GTBH explicitly listed as "without CT scan") |
| AIIMS New Delhi official website (`aiims.edu`) | Government | AIIMS identity, contact, 24/7 casualty/emergency confirmation |
| National Health Mission — Monitoring of Essential Components of the PIP, Gonda District (PRC-IEG report commissioned by MoHFW, Nov 2022) | Government-commissioned | Real PHC/CHC/District Hospital identities in Gonda (UP) and two service confirmations (SNCU and deliveries at District Women Hospital) |
| OpenStreetMap (Nominatim geocoding, ODbL) | Open data (explicit licence) | Coordinates only, where a geocoded node exists |

11 facilities are curated: 8 in Delhi (AIIMS, DDUH, GGSGH, ANH, GTBH, LNJP,
Safdarjung, Dr. BSAH) and 3 in Gonda, Uttar Pradesh (District Women Hospital,
CHC Colonelganj, PHC Kanjemau) — covering `medical_college`, `district_hospital`,
`chc`, and `phc` facility types.

## Provenance (every record)

Every facility carries: `facility_id`, `name`, `facility_type`, `address`,
`city`, `state`, `country`, `postal_code`, `coordinates` (only when
legitimately sourced), `contact` (only when sourced), `status`,
`status_source`, `status_source_reference`, `status_source_date`, `capabilities`
(per service: `source`, `source_url`, `source_date`, `retrieved_at`, `notes`),
`source`, `source_reference`, `source_date`, `retrieved_at`,
`geographic_scope`, and `data_status`.

**Nothing was invented.** Fields without a legitimate source are `null`
(coordinates, contact, postal code) and capabilities are **`Unknown`** — never
silently converted to Available or Unavailable. `data_status: "confirmed"`
means identity was confirmed by the cited source; service-level availability
remains `Unknown` unless a source states it.

## Capability / status semantics

Three states only:

- **`available`** — Confirmed by a named, dated source (e.g., "Accident and
  Emergency working round the clock", 24/7 blood bank, SNCU, labour room).
- **`unavailable`** — Confirmed by a named, dated source (e.g., GTBH's CT scan:
  DGHS explicitly lists GTBH as having intensive care/ventilator support
  "without CT scan").
- **`unknown`** — No confirmation retrieved. **`unknown` is never treated as
  `unavailable`.**

The three-state rule applies both to the facility-level `status` and to each
capability's `status`. In search, a `capability` filter surfaces facilities
with a **recorded** status for that capability (available, unavailable, or
explicitly unknown); a facility with no record is not silently assumed to have
the capability. In referral matching, facilities whose capability status is
`available` **or** `unknown` (including no record) are eligible candidates —
`unknown` is never excluded.

## 90-day staleness rule

**Any facility status/capability whose `source_date` is older than 90 days
before the dataset's `as_of_date` (2026-08-18) is flagged `stale: true` and
shown visibly in the response — never silently treated as current.**

Facility status/availability goes stale faster than drug pricing, so the
window is 90 days (vs Phase 14's 180). The rule is fixed and numeric in
`facilities.json` (`staleness_rule_days: 90`). Example: all Gonda records
(2022-11-28) and AIIMS's emergency-capability page (2024-01-12) are flagged
stale; the Delhi Government 2026 pages are fresh.

## Contact-information caution

Publicly sourced phone numbers/addresses/emails are **informational only**.
Every response that can contain contact info carries:

> "Contact information may be outdated — verify independently before relying on it, and do not use for emergencies."

Sourced contact data is never presented as verified or current without an
explicit verification source/date supporting that claim (the per-contact
`source`, `source_reference`, `source_date`, `retrieved_at` fields).

## Distance methodology

- Haversine great-circle distance in kilometres, computed **only where
  legitimate coordinates exist** (sourced from OpenStreetMap/Nominatim, ODbL).
- Labeled **"Approximate distance"** — never a travel-time claim (no legitimate
  routing source).
- `distance_km: null` when coordinates are missing — never guessed.
- Location input (`lat`/`lon`) is **clinician-provided only**; never fabricated
  or auto-detected. `sort=distance` requires `lat` and `lon` (422 otherwise).

## Default-ordering policy

- The **default list order is neutral**: alphabetical by name, `facility_id`
  as tiebreaker. No unlabeled default that repeatedly surfaces the same
  facility first.
- **Ranking is only applied on explicit request** and the criterion is always
  stated: "Sorted by facility name (alphabetical, neutral order)", "Sorted by
  approximate distance", "Sorted by capability match (confirmed availability
  first)", "Sorted by reported availability (confirmed available first)".
- Default ordering is independent of ML/SHAP/medicine/treatment-rule inputs
  (there is no coupling — see module boundaries).

## Filtering (search)

`GET /api/v1/facilities/search?city=&state=&facility_type=&capability=`

Case-insensitive filters combined with AND; results stay in neutral
alphabetical order; unknown matches return an empty list (200). Filters never
rank.

## Referral intelligence

`GET /api/v1/referrals/options?service=ct_scan&city=&state=&lat=&lon=&sort=`

- `service` (required) must be a known capability (`ct_scan`, `icu`, `iccu`,
  `emergency_care`, `blood_bank`, `newborn_care`, `maternity_obstetrics`,
  `trauma_care`, `dialysis`); unknown service → 422.
- Candidates are facilities whose status for that service is **not confirmed
  unavailable** (i.e., `available` or `unknown`). Each candidate is labeled
  **"Potentially relevant facility"** / **"Matches selected criteria"** — never
  "Recommended" or "Best".
- Confirmed-unavailable facilities are excluded for that service (e.g., GTBH is
  never offered for `ct_scan`).
- `unknown` candidates are included and flagged `service_status: unknown`,
  never treated as unavailable.
- Every response includes the applied `sorting_note`, the criteria echo, and
  the referral safety message.

## Safety boundaries

- **Banned wording** (enforced by tests): "Automatically referred",
  "Patient should go to", "best hospital", "best facility",
  "Referral completed", "we recommend", "recommend".
- No POST/PUT that creates a referral or appointment — the module is read-only.
- No distance travel-time claims; no real-time availability claims (source
  dates are always shown).
- Module isolation: `app/services/facilities.py`, `app/api/referrals.py` and
  the Phase 15 endpoints do **not** import inference, explainability,
  treatment-support, or medicines services (asserted by tests). ML probability,
  the 0.10 threshold, SHAP contributions, medicine affordability, and Phase 13
  rules can never function as referral-trigger logic; they are not passed
  through even as context.

## API

| Endpoint | Notes |
| --- | --- |
| `GET /api/v1/facilities` | Unchanged Phase 4 DB-backed list (patient current-facility reference). |
| `GET /api/v1/facilities/search` | Criteria filter; neutral order; empty results → 200. |
| `GET /api/v1/facilities/{facility_id}` | Full record; unknown id → 404 "Facility not found". |
| `GET /api/v1/referrals/options` | Referral-support candidates; validated inputs; 422 for missing/unknown service, invalid sort, distance without coordinates. |

All responses carry `geographic_scope`, `as_of_date`, `staleness_rule_days`,
`safety_message`, `scope_note`; detail and referral responses add
`contact_caution_message`; referral responses add `referral_safety_message`.

## Reuse of existing assets

- **Reused the existing facilities router** (`app/api/facilities.py`): the
  Phase 4 DB-backed list route is unchanged; the Phase 15 reference routes
  (`/search`, `/{facility_id}`) were added to the same router, as anticipated
  by its original docstring ("facility capability/referral intelligence is a
  later phase").
- **Reused the Phase 14 pattern**: static, versioned reference JSON in-package
  (`app/facilities/facilities.json`), cached JSON loader with
  `clear_facility_cache`, per-record scope/staleness enrichment, envelope
  schemas with safety messaging.
- **No database schema changes.** The existing `facilities`,
  `facility_services`, and `referrals` ORM models and their Alembic migration
  are untouched; the Phase 15 reference layer is file-based reference data,
  following the Phase 14 medicine precedent. `data/facilities/` remains the
  empty tracked directory it has always been.

## Verification

- 54 new tests in `tests/test_facility_referral.py`: provenance, three-state
  status validation, 90-day staleness boundary (89/91 days), search filters
  (city/state/type/capability/combined/empty), distance correctness and null
  handling, neutral default ordering vs labeled explicit sorts, referral
  safety wording, confirmed-unavailable exclusion, unknown-not-unavailable
  inclusion, module isolation, geographic-scope parity with Phase 14, and the
  read-only API (including 404/422 paths and no POST routes).
- Full suite: **254 tests green** (Phases 1–14 regression intact).

## Limitations

- Small curated snapshot (11 facilities); not a live facility feed.
- Only capabilities actually confirmed by cited sources are shown; most
  facility-level services are `Unknown`.
- Gonda and AIIMS status data predates the 90-day window and is flagged stale.
- Coordinates rely on OpenStreetMap geocoding accuracy; distance is
  approximate and never a travel-time estimate.
- Contact numbers are informational; the caution message applies.
- No availability guarantees; no facility-quality or clinical-suitability
  comparison.
- ABDM/ABHA integration (including the HFR) remains permanently out of scope.