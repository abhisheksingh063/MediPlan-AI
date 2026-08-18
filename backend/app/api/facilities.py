"""Read-only facility reference API.

Two layers share this router:

- ``GET /api/v1/facilities`` (unchanged, Phase 4): a minimal database-backed
  lookup so patient creation can reference a current facility.
- ``GET /api/v1/facilities/search`` and ``GET /api/v1/facilities/{facility_id}``
  (Phase 15): curated, source-verified facility reference data with capability
  and status/availability information, served from a static dataset with
  provenance. This layer is reference data only; it never autonomously refers
  a patient or makes a clinical referral decision.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Facility
from app.schemas.facility import FacilityRead
from app.schemas.facility_referral import (
    FacilityDetailRead,
    FacilityListRead,
    FacilityReferenceSummaryRead,
    FacilitySearchRead,
)
from app.services import facilities as service

router = APIRouter(prefix="/facilities", tags=["facilities"])

_NOT_FOUND_DETAIL = "Facility not found"


@router.get("", response_model=list[FacilityRead])
def list_facilities(db: Session = Depends(get_db)) -> list[FacilityRead]:
    """List known facilities ordered by name."""
    rows = db.scalars(select(Facility).order_by(Facility.name)).all()
    return [FacilityRead.model_validate(f) for f in rows]


@router.get("/search", response_model=FacilitySearchRead)
def search_facilities(
    city: str | None = Query(default=None, max_length=128),
    state: str | None = Query(default=None, max_length=128),
    facility_type: str | None = Query(default=None, max_length=64),
    capability: str | None = Query(default=None, max_length=128),
) -> FacilitySearchRead:
    """Facilities matching clinician-selected criteria (read-only reference).

    Filtering never ranks; results are returned in neutral alphabetical order.
    A ``capability`` filter excludes only facilities whose status for that
    capability is confirmed ``unavailable`` - ``unknown`` is never treated as
    unavailable.
    """
    payload = service.build_search_response(city, state, facility_type, capability)
    payload["facilities"] = [
        FacilityReferenceSummaryRead(**item) for item in payload["facilities"]
    ]
    return FacilitySearchRead(**payload)


@router.get("/{facility_id}", response_model=FacilityDetailRead)
def get_facility(facility_id: str) -> FacilityDetailRead:
    """Return one curated facility's full record with provenance."""
    payload = service.build_detail_response(facility_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL
        )
    return FacilityDetailRead(**payload)