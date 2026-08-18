"""Phase 15 tests: facility & referral-support module.

Covers reference-data provenance and validation, capability/status semantics
(unknown never treated as unavailable), the fixed 90-day staleness rule,
search/filter, distance methodology, neutral default ordering vs labeled
explicit sorts, referral-support safety, geographic-scope consistency with
Phase 14, module isolation from ML/SHAP/medicine/Phase 13, and the read-only
API.
"""

import json
from datetime import date, timedelta

from fastapi import status

from app.services import facilities as service
from app.services import medicines as medicines_service

BANNED_TOKENS = [
    "automatically referred",
    "should go to",
    "best hospital",
    "best facility",
    "referral completed",
    "we recommend",
    "recommend",
]


def _enumerate_facilities() -> list[dict]:
    return [service._enrich_facility(f) for f in service.all_facilities()]


class TestReferenceData:
    def test_all_facilities_have_full_provenance(self):
        facilities = _enumerate_facilities()
        assert len(facilities) >= 8
        required = [
            "facility_id",
            "name",
            "facility_type",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "coordinates",
            "contact",
            "status",
            "status_source",
            "status_source_reference",
            "status_source_date",
            "capabilities",
            "source",
            "source_reference",
            "source_date",
            "retrieved_at",
            "geographic_scope",
            "data_status",
        ]
        for facility in facilities:
            for field in required:
                assert field in facility, f"{facility['facility_id']} missing {field}"
            assert facility["geographic_scope"] == "India"
            assert facility["source_date"]
            assert facility["retrieved_at"]
            assert facility["data_status"]

    def test_facility_ids_unique(self):
        ids = [f["facility_id"] for f in service.all_facilities()]
        assert len(ids) == len(set(ids))

    def test_capabilities_status_is_three_state_only(self):
        for facility in _enumerate_facilities():
            for capability in facility["capabilities"]:
                assert capability["status"] in {
                    "available",
                    "unavailable",
                    "unknown",
                }

    def test_unknown_status_never_mutated_to_unavailable(self):
        gtb = service.get_facility("FAC-005")
        assert gtb["capabilities"][0]["status"] in {
            "available",
            "unavailable",
            "unknown",
        }
        phc = service.get_facility("FAC-011")
        assert phc["status"] == "unknown"
        for capability in phc["capabilities"]:
            assert capability["status"] != "unavailable"

    def test_invalid_status_rejected(self):
        import pytest

        with pytest.raises(service.InvalidFacilityRecordError):
            service._validate_facility(
                {
                    "facility_id": "BAD",
                    "name": "x",
                    "facility_type": "phc",
                    "city": "N",
                    "state": "N",
                    "country": "India",
                    "status": "maybe",
                    "source": "s",
                    "source_date": "2026-01-01",
                    "retrieved_at": "2026-08-18",
                    "geographic_scope": "India",
                    "data_status": "confirmed",
                    "capabilities": [],
                }
            )

    def test_invalid_capability_rejected(self):
        import pytest

        with pytest.raises(service.InvalidFacilityRecordError):
            service._validate_facility(
                {
                    "facility_id": "BAD2",
                    "name": "x",
                    "facility_type": "phc",
                    "city": "N",
                    "state": "N",
                    "country": "India",
                    "status": "unknown",
                    "source": "s",
                    "source_date": "2026-01-01",
                    "retrieved_at": "2026-08-18",
                    "geographic_scope": "India",
                    "data_status": "confirmed",
                    "capabilities": [
                        {
                            "service": "icu",
                            "status": "perhaps",
                            "source": "s",
                            "source_date": "2026-01-01",
                            "retrieved_at": "2026-08-18",
                        }
                    ],
                }
            )

    def test_geographic_scope_matches_phase_14(self):
        assert (
            service.scope_fields()["geographic_scope"]
            == medicines_service.scope_fields()["geographic_scope"]
            == "India"
        )


class TestStalenessRule:
    def test_stale_and_fresh_status_flagged(self):
        gonda = service.get_facility("FAC-009")
        assert gonda["status_stale"] is True
        fresh = service.get_facility("FAC-002")
        assert fresh["status_stale"] is False
        ggsgh = service.get_facility("FAC-003")
        assert ggsgh["status_stale"] is False

    def test_stale_capability_flagged(self):
        gonda = service.get_facility("FAC-009")
        for capability in gonda["capabilities"]:
            assert capability["stale"] is True
        dduh = service.get_facility("FAC-002")
        for capability in dduh["capabilities"]:
            assert capability["stale"] is False

    def test_aiims_old_capability_is_stale(self):
        aiims = service.get_facility("FAC-001")
        emergency = next(
            c for c in aiims["capabilities"] if c["service"] == "emergency_care"
        )
        assert emergency["stale"] is True

    def test_boundary_days(self):
        cutoff = service.as_of_date()
        assert (
            service._is_stale(
                (cutoff - timedelta(days=89)).isoformat(), cutoff
            )
            is False
        )
        assert (
            service._is_stale(
                (cutoff - timedelta(days=91)).isoformat(), cutoff
            )
            is True
        )


class TestSearchFilters:
    def test_city_filter(self):
        results = service.search_facilities(city="New Delhi")
        assert results
        assert all("delhi" in f["city"].lower() for f in results)
        assert len(results) < len(service.list_facilities())

    def test_state_filter(self):
        results = service.search_facilities(state="Uttar Pradesh")
        assert {f["state"] for f in results} == {"Uttar Pradesh"}

    def test_type_filter(self):
        phc = service.search_facilities(facility_type="phc")
        assert [f["facility_id"] for f in phc] == ["FAC-011"]
        chc = service.search_facilities(facility_type="chc")
        assert [f["facility_id"] for f in chc] == ["FAC-010"]

    def test_capability_filter_surfaces_recorded_statuses(self):
        results = service.search_facilities(capability="ct_scan")
        ids = {f["facility_id"] for f in results}
        assert "FAC-001" in ids  # recorded available
        assert "FAC-005" in ids  # recorded unavailable (shown, not coerced)
        assert "FAC-011" not in ids  # no record -> not silently assumed to have it

    def test_combined_filters(self):
        results = service.search_facilities(
            city="New Delhi", facility_type="district_hospital"
        )
        for f in results:
            assert f["city"] == "New Delhi"
            assert f["facility_type"] == "district_hospital"

    def test_empty_results(self):
        assert service.search_facilities(city="Mumbai") == []
        assert service.search_facilities(capability="mri") == []


class TestDistance:
    def test_haversine_zero(self):
        assert (
            service.haversine_km(28.56686, 77.20781, 28.56686, 77.20781) == 0.0
        )

    def test_haversine_known_pair(self):
        distance = service.haversine_km(
            28.56686, 77.20781, 28.62816, 77.11110
        )
        assert abs(distance - 11.6) < 0.3

    def test_distance_null_without_coordinates(self):
        fac = service.get_facility("FAC-003")
        assert fac["coordinates"] is None
        assert service._distance_km(fac, 28.5, 77.2) is None

    def test_distance_labeled_approximate(self):
        options = service.referral_options(
            "ct_scan", lat=28.56686, lon=77.20781, sort="distance"
        )
        with_distance = [
            c for c in options["candidates"] if c["distance_km"] is not None
        ]
        assert with_distance
        for candidate in with_distance:
            assert candidate["distance_label"] == "Approximate distance"

    def test_distance_sort_orders_by_distance(self):
        options = service.referral_options(
            "ct_scan", lat=28.56686, lon=77.20781, sort="distance"
        )
        distances = [
            c["distance_km"] for c in options["candidates"]
            if c["distance_km"] is not None
        ]
        assert distances == sorted(distances)

    def test_no_coordinates_candidates_sort_last_with_null(self):
        options = service.referral_options(
            "ct_scan", lat=28.56686, lon=77.20781, sort="distance"
        )
        values = [c["distance_km"] for c in options["candidates"]]
        first_null = next((i for i, v in enumerate(values) if v is None), len(values))
        assert all(v is not None for v in values[:first_null])
        assert all(v is None for v in values[first_null:])


class TestOrdering:
    def test_default_list_neutral_alphabetical(self):
        facilities = service.list_facilities()
        names = [f["name"].lower() for f in facilities]
        assert names == sorted(names)
        assert [f["facility_id"] for f in facilities] == [
            f["facility_id"] for f in service.list_facilities()
        ]

    def test_default_order_independent_of_other_modules(self):
        first = [f["facility_id"] for f in service.list_facilities()]
        medicines_service.clear_medicine_cache()
        medicines_service.list_medicines()
        second = [f["facility_id"] for f in service.list_facilities()]
        assert first == second

    def test_explicit_sort_capability_match_labeled(self):
        options = service.referral_options("newborn_care", sort="capability_match")
        statuses = [c["service_status"] for c in options["candidates"]]
        first_unknown = next(
            (i for i, s in enumerate(statuses) if s == "unknown"), len(statuses)
        )
        assert all(s == "available" for s in statuses[:first_unknown])
        assert "Sorted by capability match" in options["sorting_note"]

    def test_explicit_sort_availability_labeled(self):
        options = service.referral_options("newborn_care", sort="availability")
        assert "Sorted by reported availability" in options["sorting_note"]
        statuses = [c["status"] for c in options["candidates"]]
        assert statuses[0] == "available" or all(
            s == "unknown" for s in statuses
        )

    def test_default_sort_is_neutral_and_labeled(self):
        options = service.referral_options("ct_scan")
        assert options["criteria"]["sort"] == "name"
        assert "alphabetical" in options["sorting_note"]

    def test_validate_sort_rejects_unknown(self):
        import pytest

        with pytest.raises(ValueError):
            service.validate_sort("fastest")

    def test_validate_service_rejects_unknown(self):
        import pytest

        with pytest.raises(ValueError):
            service.validate_service("mri")


class TestReferralSafety:
    def test_no_automatic_referral_language(self):
        options = service.referral_options("ct_scan")
        self._assert_no_banned_wording(options)

    def test_candidate_label_and_note(self):
        options = service.referral_options("ct_scan")
        for candidate in options["candidates"]:
            assert candidate["candidate_label"] == (
                "Potentially relevant facility"
            )
            assert candidate["match_note"] == "Matches selected criteria"

    def test_referral_safety_message(self):
        options = service.referral_options("ct_scan")
        assert (
            options["referral_safety_message"]
            == "Referral support only — clinician review required."
        )

    def test_confirmed_unavailable_excluded_from_candidates(self):
        options = service.referral_options("ct_scan")
        ids = {c["facility_id"] for c in options["candidates"]}
        assert "FAC-005" not in ids  # GTB ct_scan confirmed unavailable

    def test_unknown_service_status_still_a_candidate(self):
        options = service.referral_options("ct_scan")
        ids = {c["facility_id"] for c in options["candidates"]}
        assert "FAC-011" in ids
        candidate = next(c for c in options["candidates"] if c["facility_id"] == "FAC-011")
        assert candidate["service_status"] == "unknown"

    def test_candidates_with_contact_pathology_carry_caution(self):
        options = service.referral_options("newborn_care")
        assert "verify independently" in options["contact_caution_message"]

    def test_module_isolated_from_other_services(self):
        import inspect

        source = inspect.getsource(service)
        for forbidden in (
            "from app.services.inference",
            "from app.services.explainability",
            "from app.services.treatment_support",
            "from app.services.medicines",
            "import shap",
            "import joblib",
        ):
            assert forbidden not in source, f"forbidden import present: {forbidden}"

    def _assert_no_banned_wording(self, payload: dict):
        text = json.dumps(payload, default=str).lower()
        for token in BANNED_TOKENS:
            assert token not in text, f"banned wording present: {token!r}"


class TestApi:
    def test_list_facilities(self, client):
        response = client.get("/api/v1/facilities/search")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["geographic_scope"] == "India"
        assert body["staleness_rule_days"] == 90
        assert "alphabetical" in body["ordering_note"]
        assert body["count"] >= 8
        names = [f["name"] for f in body["facilities"]]
        assert names == sorted(names)

    def test_detail_facility(self, client):
        response = client.get("/api/v1/facilities/FAC-002")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["geographic_scope"] == "India"
        assert body["facility"]["facility_id"] == "FAC-002"
        assert body["facility"]["status"] == "available"
        assert body["facility"]["status_stale"] is False
        assert body["contact_caution_message"] == service.CONTACT_CAUTION_MESSAGE
        assert body["facility"]["contact"]["phone"]

    def test_detail_stale_visible_in_response(self):
        detail = service.build_detail_response("FAC-009")
        assert detail["facility"]["status_stale"] is True
        assert all(c["stale"] for c in detail["facility"]["capabilities"])
        raw = json.dumps(detail, default=str)
        assert '"stale": true' in raw

    def test_detail_unknown_facility_404(self, client):
        response = client.get("/api/v1/facilities/NOPE")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Facility not found"

    def test_search_with_filters(self, client):
        response = client.get(
            "/api/v1/facilities/search",
            params={"state": "Uttar Pradesh", "facility_type": "chc"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["count"] == 1
        assert body["facilities"][0]["facility_id"] == "FAC-010"
        assert body["filters"]["state"] == "Uttar Pradesh"

    def test_search_capability_recorded_unavailable_shown(self, client):
        response = client.get(
            "/api/v1/facilities/search", params={"capability": "ct_scan"}
        )
        body = response.json()
        by_id = {f["facility_id"]: f for f in body["facilities"]}
        assert "FAC-005" in by_id  # GTB recorded as ct_scan unavailable
        assert "FAC-011" not in by_id  # no record for ct_scan
        detail = service.get_facility("FAC-005")
        ct = next(c for c in detail["capabilities"] if c["service"] == "ct_scan")
        assert ct["status"] == "unavailable"

    def test_search_empty(self, client):
        response = client.get(
            "/api/v1/facilities/search", params={"city": "Mumbai"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 0

    def test_referral_options(self, client):
        response = client.get(
            "/api/v1/referrals/options", params={"service": "ct_scan"}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["referral_safety_message"] == (
            "Referral support only — clinician review required."
        )
        assert body["candidate_count"] == len(body["candidates"])
        assert body["criteria"]["service"] == "ct_scan"
        ids = {c["facility_id"] for c in body["candidates"]}
        assert "FAC-005" not in ids
        assert all(
            c["candidate_label"] == "Potentially relevant facility"
            for c in body["candidates"]
        )
        self._assert_no_banned_wording(body)

    def test_referral_distance_sort_requires_coordinates(self, client):
        response = client.get(
            "/api/v1/referrals/options",
            params={"service": "ct_scan", "sort": "distance"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "lat" in response.json()["detail"] and "lon" in response.json()["detail"]

    def test_referral_distance_sort(self, client):
        response = client.get(
            "/api/v1/referrals/options",
            params={
                "service": "ct_scan",
                "sort": "distance",
                "lat": 28.56686,
                "lon": 77.20781,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert "Sorted by approximate distance" in body["sorting_note"]
        distances = [
            c["distance_km"] for c in body["candidates"]
            if c["distance_km"] is not None
        ]
        assert distances == sorted(distances)

    def test_referral_unknown_service_422(self, client):
        response = client.get(
            "/api/v1/referrals/options", params={"service": "mri"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Unknown required service" in response.json()["detail"]

    def test_referral_missing_service_422(self, client):
        response = client.get("/api/v1/referrals/options")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "required service" in response.json()["detail"]

    def test_referral_invalid_sort_422(self, client):
        response = client.get(
            "/api/v1/referrals/options",
            params={"service": "ct_scan", "sort": "fastest"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_referral_options_never_returns_unavailable_capability(self, client):
        response = client.get(
            "/api/v1/referrals/options", params={"service": "ct_scan"}
        )
        for candidate in response.json()["candidates"]:
            assert candidate["service_status"] != "unavailable"

    def test_no_create_endpoints_for_referrals_or_facilities(self):
        from app.main import app

        for route in app.routes:
            path = getattr(route, "path", "")
            methods = getattr(route, "methods", set()) or set()
            if path.startswith("/api/v1/referrals") or path.startswith(
                "/api/v1/facilities"
            ):
                assert "POST" not in methods
                assert "PUT" not in methods

    def _assert_no_banned_wording(self, payload: dict):
        text = json.dumps(payload, default=str).lower()
        for token in BANNED_TOKENS:
            assert token not in text, f"banned wording present: {token!r}"


class TestSafetyMessageContent:
    def test_contact_caution_message(self):
        assert (
            service.CONTACT_CAUTION_MESSAGE
            == (
                "Contact information may be outdated — verify independently "
                "before relying on it, and do not use for emergencies."
            )
        )

    def test_scope_note_independence(self):
        assert "UCI Diabetes 130-US Hospitals" in service.SCOPE_NOTE
        assert "US" in service.SCOPE_NOTE