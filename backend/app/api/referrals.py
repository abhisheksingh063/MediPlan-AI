"""Read-only referral-support API (Phase 15).

``GET /api/v1/referrals/options`` matches facilities against
clinician-selected criteria (required service, optional location/state) and
returns "potentially relevant facilities" for clinician review. It never
autonomously refers a patient, books an appointment, or makes a clinical
referral decision, and no referral-trigger logic is inferred from ML/SHAP/
medicine or Phase 13 treatment-rule inputs.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.facility_referral import ReferralOptionsRead
from app.services import facilities as facility_service

router = APIRouter(prefix="/referrals", tags=["referrals"])

_MISSING_SERVICE_DETAIL = "A required service is required."
_UNKNOWN_SERVICE_DETAIL = "Unknown required service."
_INVALID_SORT_DETAIL = (
    "Unsupported sort. Use one of: name, distance, capability_match, availability."
)
_DISTANCE_SORT_REQUIRES_COORDINATES = (
    "Sorting by distance requires the clinician-provided 'lat' and 'lon'."
)


@router.get("/options", response_model=ReferralOptionsRead)
def referral_options(
    service: str | None = Query(default=None, max_length=128),
    city: str | None = Query(default=None, max_length=128),
    state: str | None = Query(default=None, max_length=128),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    sort: str | None = Query(default="name", max_length=32),
) -> ReferralOptionsRead:
    """Return potentially relevant facilities for one required service.

    The required ``service`` must be a known capability. ``sort`` defaults to
    the neutral alphabetical order; any explicit sort is labeled in the
    response. ``lat``/``lon`` are clinician-provided only and are used for
    approximate distance; provide them to use ``sort=distance``.
    """
    try:
        validated_service = facility_service.validate_service(service)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_MISSING_SERVICE_DETAIL
            if not service
            else _UNKNOWN_SERVICE_DETAIL,
        )
    try:
        validated_sort = facility_service.validate_sort(sort)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_INVALID_SORT_DETAIL,
        )
    if validated_sort == "distance" and (lat is None or lon is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_DISTANCE_SORT_REQUIRES_COORDINATES,
        )
    payload = facility_service.referral_options(
        validated_service,
        city=city,
        state=state,
        lat=lat,
        lon=lon,
        sort=validated_sort,
    )
    return ReferralOptionsRead(**payload)