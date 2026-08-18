"""Pydantic schemas for the Phase 15 facility & referral-support module.

Curated, source-verified reference data only. Read-only; the module never
autonomously refers a patient, books an appointment, or makes a clinical
referral decision. Status semantics: ``available`` (confirmed), ``unavailable``
(confirmed), or ``unknown`` — ``unknown`` is never treated as ``unavailable``.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

FacilityStatus = Literal["available", "unavailable", "unknown"]


class CoordinatesRead(BaseModel):
    """Coordinates that are only ever carried when a legitimate source exists."""

    latitude: float
    longitude: float
    source: str
    source_reference: str | None
    retrieved_at: date


class ContactRead(BaseModel):
    """Publicly sourced contact information; informational only."""

    phone: str | None
    email: str | None
    source: str
    source_reference: str | None
    source_date: date
    retrieved_at: date
    note: str | None


class CapabilityRead(BaseModel):
    """Availability of one named service at one named facility."""

    service: str
    status: FacilityStatus
    source: str
    source_url: str | None
    source_date: date
    retrieved_at: date
    stale: bool
    notes: str | None


class FacilityReferenceRead(BaseModel):
    """Full facility record including capabilities, contact and provenance."""

    facility_id: str
    name: str
    facility_type: str
    address: str | None
    city: str
    state: str
    country: str
    postal_code: str | None
    coordinates: CoordinatesRead | None
    contact: ContactRead | None
    status: FacilityStatus
    status_source: str
    status_source_reference: str | None
    status_source_date: date | None
    status_stale: bool
    capabilities: list[CapabilityRead]
    source: str
    source_reference: str | None
    source_date: date
    retrieved_at: date
    geographic_scope: str
    data_status: str
    notes: str | None


class FacilityReferenceSummaryRead(BaseModel):
    """Compact facility record for list and search responses."""

    facility_id: str
    name: str
    facility_type: str
    city: str
    state: str
    country: str
    postal_code: str | None
    status: FacilityStatus
    status_stale: bool
    has_coordinates: bool
    geographic_scope: str
    data_status: str
    capability_services: list[str]


class FacilityListRead(BaseModel):
    """List response envelope; scope, ordering and safety travel with it."""

    geographic_scope: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    ordering_note: str
    count: int
    facilities: list[FacilityReferenceSummaryRead]


class FacilityDetailRead(BaseModel):
    """Detail response envelope."""

    geographic_scope: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    contact_caution_message: str
    facility: FacilityReferenceRead


class FacilitySearchRead(BaseModel):
    """Search response envelope; echoes the applied filters."""

    geographic_scope: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    ordering_note: str
    filters: dict[str, str | None]
    count: int
    facilities: list[FacilityReferenceSummaryRead]


class ReferralCandidateRead(BaseModel):
    """A criteria-matched candidate facility for clinician review.

    Candidates are labeled "potentially relevant" only; the module never
    chooses, ranks by quality, or recommends a facility.
    """

    facility_id: str
    name: str
    facility_type: str
    city: str
    state: str
    status: FacilityStatus
    status_stale: bool
    service_status: FacilityStatus
    service_stale: bool
    distance_km: float | None
    distance_label: str | None
    candidate_label: str
    match_note: str


class ReferralOptionsRead(BaseModel):
    """Referral-support response envelope.

    Always carries the referral safety message and the explicit criterion that
    was used for ordering, so no implicit ranking is possible.
    """

    geographic_scope: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    contact_caution_message: str
    referral_safety_message: str
    criteria: dict[str, str | float | None]
    sorting_note: str
    candidate_count: int
    candidates: list[ReferralCandidateRead]


class FacilityNotFoundError(BaseModel):
    """Controlled 404 body; carries no internal detail."""

    detail: str