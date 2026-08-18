"""Facility and referral-support service (Phase 15).

Serves curated, source-verified facility reference data loaded from
``app/facilities/facilities.json``. The module answers "what facility
information and referral options exist" and never "what should this patient
receive" or "which facility is clinically best": it is deliberately isolated
from ``app.services.inference``, ``app.services.explainability``,
``app.services.treatment_support``, and ``app.services.medicines``.

Geographic scope (India) is carried declaratively on every record and every
response, matching the Phase 14 pricing scope. Facility status semantics are
``available`` / ``unavailable`` / ``unknown``; ``unknown`` is never treated as
``unavailable``. Any status/capability whose ``source_date`` is older than the
fixed 90-day window is flagged ``stale`` and shown visibly, never treated as
current.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from json import load
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

VALID_STATUSES = {"available", "unavailable", "unknown"}

SAFETY_MESSAGE = (
    "Facility information is reference data only; it does not guarantee "
    "real-time availability and does not constitute a referral or a clinical "
    "decision."
)

REFERRAL_SAFETY_MESSAGE = "Referral support only — clinician review required."

CONTACT_CAUTION_MESSAGE = (
    "Contact information may be outdated — verify independently before relying "
    "on it, and do not use for emergencies."
)

SCOPE_NOTE = (
    "Facility scope is India and is independent of the origin of the clinical "
    "dataset (UCI Diabetes 130-US Hospitals) used for the ML model; this "
    "system does not claim facility capability information applies to the US "
    "hospital population."
)

ORDERING_NOTE = (
    "Facilities are listed alphabetically by name (neutral order) unless an "
    "explicit sort is requested."
)

CANDIDATE_LABEL = "Potentially relevant facility"
MATCH_NOTE_DEFAULT = "Matches selected criteria"

_DISTANCE_LABEL = "Approximate distance"
_SORT_FIELDS = {"name", "distance", "capability_match", "availability"}
_SORT_NOTES = {
    "name": "Sorted by facility name (alphabetical, neutral order).",
    "distance": "Sorted by approximate distance.",
    "capability_match": "Sorted by capability match (confirmed availability first).",
    "availability": "Sorted by reported availability (confirmed available first).",
}

_DATA_DIR = Path(__file__).resolve().parents[1] / "facilities"


class FacilityDataError(Exception):
    """Base error for facility reference-data failures."""


class FacilityDataUnavailableError(FacilityDataError):
    """Raised when the facility reference data cannot be loaded."""


class InvalidFacilityRecordError(FacilityDataError):
    """Raised when a reference-data record fails validation."""


@lru_cache(maxsize=1)
def _load_facility_data() -> dict:
    try:
        with (_DATA_DIR / "facilities.json").open(encoding="utf-8") as handle:
            data = load(handle)
    except (OSError, ValueError) as exc:
        raise FacilityDataUnavailableError(
            "Facility reference data unavailable."
        ) from exc
    for facility in data.get("facilities", []):
        _validate_facility(facility)
    return data


def clear_facility_cache() -> None:
    """Drop cached facility data so tests can reload updated data files."""
    _load_facility_data.cache_clear()


def _validate_facility(facility: dict) -> None:
    """Reject malformed reference-data records (never silently skipped)."""
    if not isinstance(facility, dict):
        raise InvalidFacilityRecordError("Facility record must be an object.")
    for field in (
        "facility_id",
        "name",
        "facility_type",
        "city",
        "state",
        "country",
        "status",
        "source",
        "source_date",
        "retrieved_at",
        "geographic_scope",
        "data_status",
    ):
        if field not in facility or facility[field] in (None, ""):
            raise InvalidFacilityRecordError(
                f"Facility record missing required field {field!r}."
            )
    if facility["status"] not in VALID_STATUSES:
        raise InvalidFacilityRecordError(
            f"Invalid facility status {facility['status']!r} for "
            f"{facility.get('facility_id')}."
        )
    capabilities = facility.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise InvalidFacilityRecordError(
            f"facilities.capabilities must be a list for {facility['facility_id']}."
        )
    for capability in capabilities:
        if capability.get("status") not in VALID_STATUSES:
            raise InvalidFacilityRecordError(
                f"Invalid capability status {capability.get('status')!r} for "
                f"{facility['facility_id']}."
            )
        for field in ("service", "source", "source_date", "retrieved_at"):
            if field not in capability or capability[field] in (None, ""):
                raise InvalidFacilityRecordError(
                    f"Capability {capability.get('service')!r} of "
                    f"{facility['facility_id']} missing required field {field!r}."
                )


def all_facilities() -> list[dict]:
    return _load_facility_data().get("facilities", [])


def as_of_date() -> date:
    return date.fromisoformat(_load_facility_data()["as_of_date"])


def staleness_rule_days() -> int:
    return int(_load_facility_data()["staleness_rule_days"])


def scope_fields() -> dict[str, str]:
    return {"geographic_scope": _load_facility_data()["geographic_scope"]}


def known_services() -> list[str]:
    services = set()
    for facility in all_facilities():
        for capability in facility.get("capabilities", []):
            services.add(capability["service"])
    return sorted(services)


def _is_stale(source_date: str | None, cutoff: date) -> bool:
    if not source_date:
        return False
    try:
        return cutoff - date.fromisoformat(source_date) > timedelta(
            days=staleness_rule_days()
        )
    except ValueError:
        return False


def _enrich_facility(facility: dict) -> dict:
    cutoff = as_of_date()
    enriched = dict(facility)
    enriched["geographic_scope"] = facility.get("geographic_scope")
    enriched["status_stale"] = _is_stale(
        facility.get("status_source_date"), cutoff
    )
    capabilities = []
    for capability in facility.get("capabilities", []):
        item = dict(capability)
        item["stale"] = _is_stale(capability.get("source_date"), cutoff)
        capabilities.append(item)
    enriched["capabilities"] = capabilities
    return enriched


def _capability_status(facility: dict, service: str) -> str | None:
    for capability in facility["capabilities"]:
        if capability["service"] == service:
            return capability["status"]
    return None


def get_facility(facility_id: str) -> dict | None:
    """Return a single enriched facility record, or None."""
    for facility in all_facilities():
        if facility["facility_id"] == facility_id:
            return _enrich_facility(facility)
    return None


def list_facilities() -> list[dict]:
    """Return all enriched facilities in neutral alphabetical order.

    Neutral order means alphabetical by name with facility_id as tiebreaker;
    an unlabeled default order that repeatedly surfaces the same facility
    first would function as an implicit ranking, which this module avoids.
    """
    facilities = [_enrich_facility(f) for f in all_facilities()]
    return sorted(
        facilities, key=lambda f: (f["name"].lower(), f["facility_id"])
    )


def _matches_capability(facility: dict, service: str) -> bool:
    """A facility is eligible for a service unless it is confirmed unavailable.

    Both ``available`` and ``unknown`` statuses qualify (a missing record is
    implicitly unknown); ``unknown`` is never treated as ``unavailable``.
    """
    status = _capability_status(facility, service)
    if status is None:
        return True
    return status != "unavailable"


def _has_capability_record(facility: dict, service: str) -> bool:
    """True when the facility carries a recorded status for the service."""
    return any(c["service"] == service for c in facility["capabilities"])


def search_facilities(
    city: str | None = None,
    state: str | None = None,
    facility_type: str | None = None,
    capability: str | None = None,
) -> list[dict]:
    """Filter enriched facilities by clinician-selected criteria (read-only).

    A ``capability`` filter surfaces facilities that carry a recorded status
    for that capability (available, unavailable, or explicitly unknown);
    facilities with no record are not silently assumed to have it.
    """
    results = list_facilities()
    if city:
        needle = city.strip().lower()
        results = [f for f in results if needle in f["city"].lower()]
    if state:
        needle = state.strip().lower()
        results = [f for f in results if needle in f["state"].lower()]
    if facility_type:
        needle = facility_type.strip().lower()
        results = [f for f in results if needle in f["facility_type"].lower()]
    if capability:
        needle = capability.strip().lower()
        results = [f for f in results if _has_capability_record(f, needle)]
    return results


def _summary(facility: dict) -> dict:
    return {
        "facility_id": facility["facility_id"],
        "name": facility["name"],
        "facility_type": facility["facility_type"],
        "city": facility["city"],
        "state": facility["state"],
        "country": facility["country"],
        "postal_code": facility.get("postal_code"),
        "status": facility["status"],
        "status_stale": facility["status_stale"],
        "has_coordinates": facility.get("coordinates") is not None,
        "geographic_scope": facility["geographic_scope"],
        "data_status": facility["data_status"],
        "capability_services": [
            c["service"] for c in facility["capabilities"]
        ],
    }


def build_list_response() -> dict:
    facilities = list_facilities()
    return {
        **scope_fields(),
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "ordering_note": ORDERING_NOTE,
        "count": len(facilities),
        "facilities": [_summary(f) for f in facilities],
    }


def build_detail_response(facility_id: str) -> dict | None:
    facility = get_facility(facility_id)
    if facility is None:
        return None
    return {
        **scope_fields(),
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "contact_caution_message": CONTACT_CAUTION_MESSAGE,
        "facility": facility,
    }


def build_search_response(
    city: str | None = None,
    state: str | None = None,
    facility_type: str | None = None,
    capability: str | None = None,
) -> dict:
    facilities = search_facilities(city, state, facility_type, capability)
    return {
        **scope_fields(),
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "ordering_note": ORDERING_NOTE,
        "filters": {
            "city": city,
            "state": state,
            "facility_type": facility_type,
            "capability": capability,
        },
        "count": len(facilities),
        "facilities": [_summary(f) for f in facilities],
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres; labeled approximate by callers."""
    earth_radius_km = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = (
        sin(d_phi / 2) ** 2
        + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    )
    return round(earth_radius_km * 2 * asin(sqrt(a)), 1)


def _distance_km(facility: dict, lat: float | None, lon: float | None) -> float | None:
    """Distance only where legitimate coordinates exist; null elsewhere."""
    if lat is None or lon is None:
        return None
    coordinates = facility.get("coordinates")
    if not coordinates:
        return None
    return haversine_km(
        lat, lon, coordinates["latitude"], coordinates["longitude"]
    )


def _candidate(facility: dict, service: str, lat: float | None, lon: float | None) -> dict:
    capability = next(
        (
            c
            for c in facility["capabilities"]
            if c["service"] == service
        ),
        None,
    )
    return {
        "facility_id": facility["facility_id"],
        "name": facility["name"],
        "facility_type": facility["facility_type"],
        "city": facility["city"],
        "state": facility["state"],
        "status": facility["status"],
        "status_stale": facility["status_stale"],
        "service_status": capability["status"] if capability else "unknown",
        "service_stale": capability["stale"] if capability else _is_stale(
            facility.get("status_source_date"), as_of_date()
        ),
        "distance_km": _distance_km(facility, lat, lon),
        "distance_label": (
            _DISTANCE_LABEL
            if _distance_km(facility, lat, lon) is not None
            else None
        ),
        "candidate_label": CANDIDATE_LABEL,
        "match_note": MATCH_NOTE_DEFAULT,
    }


def _candidate_sort_key(mode: str, lat: float | None, lon: float | None):
    if mode == "distance":
        return lambda c: (
            c["distance_km"] is None,
            (
                c["distance_km"]
                if c["distance_km"] is not None
                else float("inf")
            ),
            c["name"].lower(),
        )
    if mode == "capability_match":
        order = {"available": 0, "unknown": 1, "unavailable": 2}
        return lambda c: (
            order.get(c["service_status"], 3),
            c["name"].lower(),
        )
    if mode == "availability":
        order = {"available": 0, "unknown": 1, "unavailable": 2}
        return lambda c: (
            order.get(c["status"], 3),
            c["name"].lower(),
        )
    return lambda c: (c["name"].lower(), c["facility_id"])


def referral_options(
    service: str,
    city: str | None = None,
    state: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    sort: str = "name",
) -> dict:
    """Produce clinician-reviewable candidate facilities for one required service.

    Eligible facilities are those whose status for the required service is not
    confirmed unavailable (i.e., available or unknown). Candidates are labeled
    "Potentially relevant facility" and the applied ordering criterion is
    stated explicitly, so no implicit ranking is possible.
    """
    facilities = search_facilities(city=city, state=state)
    eligibility = [
        f for f in facilities if _matches_capability(f, service)
    ]
    candidates = [
        _candidate(f, service, lat, lon) for f in eligibility
    ]
    candidates.sort(key=_candidate_sort_key(sort, lat, lon))
    return {
        **scope_fields(),
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "contact_caution_message": CONTACT_CAUTION_MESSAGE,
        "referral_safety_message": REFERRAL_SAFETY_MESSAGE,
        "criteria": {
            "service": service,
            "city": city,
            "state": state,
            "latitude": lat,
            "longitude": lon,
            "sort": sort,
        },
        "sorting_note": _SORT_NOTES.get(sort, _SORT_NOTES["name"]),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def validate_sort(sort: str | None) -> str:
    """Return a validated sort mode, defaulting to the neutral 'name'."""
    if sort is None:
        return "name"
    mode = sort.strip().lower()
    if mode not in _SORT_FIELDS:
        raise ValueError(f"Unsupported sort {sort!r}.")
    return mode


def validate_service(service: str | None) -> str:
    if not service:
        raise ValueError("A required service is required.")
    needle = service.strip().lower()
    if needle not in known_services():
        raise ValueError(f"Unknown required service {service!r}.")
    return needle