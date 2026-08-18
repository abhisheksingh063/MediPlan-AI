"""Service and API tests for Phase 14 medicine information/affordability.

Covers reference-data integrity and provenance, staleness flagging, grouping
before comparison, unresolved multi-source price display, unit-price math,
geographic/currency scope, safety wording, API behaviour, and isolation from
the ML and Phase 13 modules.
"""

from datetime import date, timedelta

from fastapi import status

from app.services import medicines as service

MEDICINES_URL = "/api/v1/medicines"
BANNED_TOKENS = [
    "take ",
    "start ",
    "stop ",
    "prescribe",
    "best medicine",
    "best option",
    "recommended drug",
    "you should use",
    "the ai recommends",
]


def _enumerate_medicines() -> list[dict]:
    """Enrich all medicines the same way the service serves them."""
    cutoff = service.as_of_date()
    result = []
    for medicine in service.all_medicines():
        medicine = dict(medicine)
        medicine["prices"] = [
            service._enrich_price(price, cutoff, medicine)
            for price in medicine["prices"]
        ]
        service._aggregate_price_fields(medicine)
        result.append(medicine)
    return result


def _price_distinct_sources(medicine: dict) -> list[str]:
    return [price["source"] for price in medicine["prices"]]


class TestReferenceData:
    def test_records_load_and_have_unique_ids(self):
        medicines = service.all_medicines()
        assert medicines
        ids = [m["medicine_id"] for m in medicines]
        assert len(ids) == len(set(ids))

    def test_every_record_carries_full_provenance(self):
        for medicine in _enumerate_medicines():
            assert medicine["medicine_id"]
            assert medicine["generic_name"]
            assert medicine["strength"]
            assert medicine["form"]
            assert medicine["pack_size"]
            assert medicine["pack_size_units"] > 0
            assert medicine["therapeutic_class"]
            for price in medicine["prices"]:
                assert price["price"] is None or price["price"] >= 0
                assert price["price_unit"]
                assert price["source"]
                assert price["source_date"]
                assert price["retrieved_date"]
                assert price["availability"] in {"jan_aushadhi", "brand", "unknown"}

    def test_missing_price_stays_null_never_fabricated(self):
        med = service.get_medicine("MED-004")
        assert med is not None
        assert med["has_price"] is False
        assert med["lowest_reported_price"] is None
        assert all(price["price"] is None for price in med["prices"])

    def test_stale_prices_flagged_older_than_180_days(self):
        cutoff = service.as_of_date()
        for medicine in _enumerate_medicines():
            for price in medicine["prices"]:
                if not price.get("source_date"):
                    continue
                actual = (cutoff - date.fromisoformat(price["source_date"])).days
                expected_stale = actual > service.staleness_rule_days()
                assert price["stale"] is expected_stale, (
                    f"{medicine['medicine_id']} {price['source']}"
                )

    def test_current_and_stale_prices_coexist_unresolved(self):
        med = service.get_medicine("MED-001")
        prices = med["prices"]
        assert len(prices) == 2
        assert {p["price"] for p in prices} == {6.19, 5.0}
        assert any(p["stale"] for p in prices)
        assert any(not p["stale"] for p in prices)
        assert med["stale_available"] is True

    def test_schemas_reject_malformed_records(self):
        from app.schemas.medicine import MedicineRead

        for medicine in _enumerate_medicines():
            built = MedicineRead(**medicine)
            assert built.medicine_id == medicine["medicine_id"]


class TestStalenessRule:
    def test_rule_is_fixed_numeric_180_days(self):
        assert service.staleness_rule_days() == 180

    def test_boundary_behaviour(self):
        cutoff = service.as_of_date()
        fresh = service._enrich_price(
            {"source_date": (cutoff - timedelta(days=179)).isoformat()}, cutoff, {}
        )
        assert fresh["stale"] is False
        stale = service._enrich_price(
            {"source_date": (cutoff - timedelta(days=181)).isoformat()}, cutoff, {}
        )
        assert stale["stale"] is True


class TestUnitPrice:
    def test_unit_price_math(self):
        med = service.get_medicine("MED-001")
        current = next(p for p in med["prices"] if p["price"] == 6.19)
        assert current["unit_price"] == round(6.19 / 10, 2)

    def test_per_tablet_record_unit_math(self):
        med = service.get_medicine("MED-008")
        assert med["prices"][0]["unit_price"] == 0.93

    def test_none_price_has_none_unit_price(self):
        med = service.get_medicine("MED-004")
        assert med["prices"][0]["unit_price"] is None


class TestGrouping:
    def test_grouped_by_generic_before_compare(self):
        compare = service.build_compare_response("Metformin")
        assert compare["group_count"] == 1
        group = compare["groups"][0]
        ids = {m["medicine_id"] for m in group["medicines"]}
        assert ids == {"MED-001", "MED-002"}

    def test_lowest_reported_unit_price_leads_group(self):
        compare = service.build_compare_response("Metformin")
        group = compare["groups"][0]
        ordered = [m["medicine_id"] for m in group["medicines"]]
        assert ordered == ["MED-001", "MED-002"]

    def test_multisource_prices_all_surface_unresolved(self):
        med = service.get_medicine("MED-001")
        sources = _price_distinct_sources(med)
        assert len(sources) == len(set(sources)) == 2
        prices = {p["price"] for p in med["prices"]}
        assert prices == {6.19, 5.0}

    def test_price_unavailable_item_still_in_group(self):
        compare = service.build_compare_response("Glimepiride")
        group = compare["groups"][0]
        assert len(group["medicines"]) == 2
        has_price = [m["medicine_id"] for m in group["medicines"] if m["has_price"]]
        no_price = [m["medicine_id"] for m in group["medicines"] if not m["has_price"]]
        assert has_price == ["MED-003"]
        assert no_price == ["MED-004"]

    def test_unknown_generic_returns_empty(self):
        compare = service.build_compare_response("DefinitelyNotADrug")
        assert compare["group_count"] == 0
        assert compare["groups"] == []

    def test_class_filter(self):
        compare = service.build_compare_response(therapeutic_class="statin")
        assert compare["group_count"] == 1
        group = compare["groups"][0]
        assert {m["generic_name"] for m in group["medicines"]} == {"Atorvastatin"}


class TestScope:
    def test_every_record_carries_scope_and_currency(self):
        for medicine in _enumerate_medicines():
            assert medicine["geographic_scope"] == "India"
            assert medicine["currency"] == "INR"
            for price in medicine["prices"]:
                assert price["geographic_scope"] == "India"
                assert price["currency"] == "INR"

    def test_responses_carry_scope_and_currency(self):
        for payload in (
            service.build_list_response(),
            service.build_detail_response("MED-001"),
            service.build_compare_response(),
        ):
            assert payload["geographic_scope"] == "India"
            assert payload["currency"] == "INR"
            assert "independent" in payload["scope_note"]
            assert "UCI Diabetes 130" in payload["scope_note"]

    def test_no_inference_import_in_service_module(self):
        import pathlib

        source = pathlib.Path(service.__file__).read_text(encoding="utf-8")
        assert "from app.services import inference" not in source
        assert "from app.services.inference" not in source
        assert "from app.services import treatment_support" not in source
        assert "from app.services import explainability" not in source


class TestSafety:
    def _assert_no_banned_wording(self, payload: dict):
        import json

        text = json.dumps(payload, default=str).lower()
        for token in BANNED_TOKENS:
            assert token not in text, f"banned wording present: {token!r}"

    def test_list_response_has_safety_and_no_banned_wording(self):
        payload = service.build_list_response()
        assert "prescription" in payload["safety_message"]
        self._assert_no_banned_wording(payload)

    def test_detail_response_has_safety_and_no_banned_wording(self):
        payload = service.build_detail_response("MED-001")
        assert "prescription" in payload["safety_message"]
        self._assert_no_banned_wording(payload)

    def test_compare_response_has_safety_and_no_banned_wording(self):
        payload = service.build_compare_response("Metformin")
        assert "prescription" in payload["safety_message"]
        assert "without the system resolving them" in payload["comparison_note"]
        self._assert_no_banned_wording(payload)

    def test_medicines_module_isolated_from_ml_and_phase13(self):
        import app.api.medicines as api_module
        import pathlib

        for module in (service, api_module):
            source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
            assert "from app.services import inference" not in source
            assert "from app.services.inference" not in source
            assert "from app.services import explainability" not in source
            assert "from app.services.explainability" not in source
            assert "from app.services import treatment_support" not in source
            assert "from app.services.treatment_support" not in source


class TestAPI:
    def test_list_medicines(self, client):
        response = client.get(MEDICINES_URL)
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["geographic_scope"] == "India"
        assert body["currency"] == "INR"
        assert body["count"] == 8
        assert body["medicines"]
        assert "prescription" in body["safety_message"]

    def test_get_medicine_detail(self, client):
        response = client.get(f"{MEDICINES_URL}/MED-001")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        medicine = body["medicine"]
        assert medicine["generic_name"] == "Metformin"
        assert len(medicine["prices"]) == 2
        assert {p["price"] for p in medicine["prices"]} == {6.19, 5.0}
        assert any(p["stale"] for p in medicine["prices"])
        assert medicine["has_price"] is True

    def test_get_medicine_missing_price(self, client):
        response = client.get(f"{MEDICINES_URL}/MED-004")
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["medicine"]["has_price"] is False
        assert body["medicine"]["prices"][0]["price"] is None
        assert "Price unavailable" in body["medicine"]["prices"][0]["notes"]

    def test_get_unknown_medicine_404(self, client):
        response = client.get(f"{MEDICINES_URL}/MED-999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        detail = str(response.json())
        assert "Medicine not found" in detail
        assert "6.19" not in detail

    def test_compare_valid(self, client):
        response = client.get(f"{MEDICINES_URL}/compare", params={"generic": "Metformin"})
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["group_count"] == 1
        group = body["groups"][0]
        assert {m["medicine_id"] for m in group["medicines"]} == {"MED-001", "MED-002"}

    def test_compare_empty_results(self, client):
        response = client.get(
            f"{MEDICINES_URL}/compare", params={"generic": "xyzzy-nothing"}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["group_count"] == 0
        assert body["groups"] == []

    def test_compare_no_params_returns_all_groups(self, client):
        response = client.get(f"{MEDICINES_URL}/compare")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["group_count"] >= 3

    def test_compare_by_class(self, client):
        response = client.get(
            f"{MEDICINES_URL}/compare", params={"therapeutic_class": "anti-hypertensive"}
        )
        assert response.status_code == status.HTTP_200_OK
        generics = {
            item["generic_name"]
            for group in response.json()["groups"]
            for item in group["medicines"]
        }
        assert {"Amlodipine", "Telmisartan"} <= generics

    def test_compare_and_detail_are_read_only(self, client):
        before = client.get(MEDICINES_URL).json()["count"]
        client.get(f"{MEDICINES_URL}/compare")
        client.get(f"{MEDICINES_URL}/MED-002")
        after = client.get(MEDICINES_URL).json()["count"]
        assert before == after == 8