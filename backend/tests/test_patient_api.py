"""API-layer tests for the patient-management endpoints.

Requests run against a FastAPI ``TestClient`` whose database dependency is
overridden to share the transaction-pinned test session from ``conftest``.
All assertions work on synthetic data only.
"""

from fastapi import status

from app.models import Facility

PATIENTS_URL = "/api/v1/patients"
FACILITIES_URL = "/api/v1/facilities"


def _add_facility(session, name: str = "Test District PHC") -> int:
    facility = Facility(
        name=name,
        facility_type="phc",
        district="Test District",
        state="Test State",
    )
    session.add(facility)
    session.flush()
    return facility.id


def _patient_payload(reference: str = "SYN-API-001", facility_id: int | None = None) -> dict:
    payload = {
        "external_reference": reference,
        "age": 45,
        "sex": "f",
        "height": 160.5,
        "weight": 65.0,
    }
    if facility_id is not None:
        payload["current_facility_id"] = facility_id
    return payload


def _create_patient(client, facility_id: int | None = None, reference: str = "SYN-API-001"):
    response = client.post(
        PATIENTS_URL, json=_patient_payload(reference, facility_id)
    )
    return response


class TestPatientEndpoints:
    def test_create_patient(self, client, session):
        facility_id = _add_facility(session)
        response = _create_patient(client, facility_id=facility_id)
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["external_reference"] == "SYN-API-001"
        assert body["sex"] == "F"
        assert body["age"] == 45
        assert body["current_facility"]["name"] == "Test District PHC"
        assert body["current_facility_id"] == facility_id
        assert body["created_at"]

    def test_create_patient_duplicate_reference(self, client, session):
        _create_patient(client)
        response = _create_patient(client)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_patient_rejects_bad_sanity_data(self, client, session):
        payload = _patient_payload()
        payload["age"] = 999
        response = client.post(PATIENTS_URL, json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        payload = _patient_payload()
        payload["weight"] = 0
        response = client.post(PATIENTS_URL, json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_patient_rejects_unknown_facility(self, client, session):
        response = _create_patient(client, facility_id=999_999)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_patient(self, client, session):
        created = _create_patient(client)
        patient_id = created.json()["id"]
        response = client.get(f"{PATIENTS_URL}/{patient_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["external_reference"] == "SYN-API-001"

    def test_get_patient_not_found(self, client, session):
        response = client.get(f"{PATIENTS_URL}/999999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_patients_and_search(self, client, session):
        _create_patient(client, reference="SYN-SEARCH-A")
        _create_patient(client, reference="SYN-SEARCH-B")
        all_response = client.get(PATIENTS_URL)
        assert all_response.status_code == status.HTTP_200_OK
        assert len(all_response.json()["items"]) == 2

        filtered = client.get(PATIENTS_URL, params={"search": "SEARCH-A"})
        items = filtered.json()["items"]
        assert len(items) == 1
        assert items[0]["external_reference"] == "SYN-SEARCH-A"

    def test_update_patient(self, client, session):
        created = _create_patient(client)
        patient_id = created.json()["id"]
        response = client.patch(
            f"{PATIENTS_URL}/{patient_id}",
            json={"age": 46, "sex": "m", "external_reference": "SYN-API-UPDATED"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["age"] == 46
        assert body["sex"] == "M"
        assert body["external_reference"] == "SYN-API-UPDATED"

    def test_update_patient_explicitly_clears_facility(self, client, session):
        facility_id = _add_facility(session, name="Clearing PHC")
        created = _create_patient(client, facility_id=facility_id)
        patient_id = created.json()["id"]
        response = client.patch(
            f"{PATIENTS_URL}/{patient_id}", json={"current_facility_id": None}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["current_facility_id"] is None
        assert response.json()["current_facility"] is None

    def test_update_patient_rejects_unknown_facility(self, client, session):
        created = _create_patient(client)
        patient_id = created.json()["id"]
        response = client.patch(
            f"{PATIENTS_URL}/{patient_id}",
            json={"current_facility_id": 999_999},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_patient_not_found(self, client, session):
        response = client.patch(
            f"{PATIENTS_URL}/999999", json={"age": 40}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestClinicalRecordEndpoints:
    def test_create_clinical_record(self, client, session):
        created = _create_patient(client)
        patient_id = created.json()["id"]
        response = client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records",
            json={
                "condition": "Hypertension",
                "history_text": "Follow-up visit.",
                "allergies": "None known",
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["patient_id"] == patient_id
        assert body["condition"] == "Hypertension"
        assert body["recorded_at"]
        assert body["lab_results"] == []

    def test_create_clinical_record_patient_not_found(self, client, session):
        response = client.post(
            f"{PATIENTS_URL}/999999/clinical-records",
            json={"condition": "Hypertension"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_clinical_records(self, client, session):
        created = _create_patient(client)
        patient_id = created.json()["id"]
        client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records",
            json={"condition": "Diabetes"},
        )
        response = client.get(f"{PATIENTS_URL}/{patient_id}/clinical-records")
        assert response.status_code == status.HTTP_200_OK
        records = response.json()
        assert len(records) == 1
        assert records[0]["condition"] == "Diabetes"


class TestLabResultEndpoints:
    def test_create_lab_result(self, client, session):
        patient_id = _create_patient(client).json()["id"]
        record_id = client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records",
            json={"condition": "Hypertension"},
        ).json()["id"]
        response = client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records/{record_id}/lab-results",
            json={"test_name": "HbA1c", "value": 6.5, "unit": "%"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["test_name"] == "HbA1c"
        assert body["value"] == 6.5
        assert body["clinical_record_id"] == record_id

    def test_create_lab_result_requires_test_name(self, client, session):
        patient_id = _create_patient(client).json()["id"]
        record_id = client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records",
            json={"condition": "Hypertension"},
        ).json()["id"]
        response = client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records/{record_id}/lab-results",
            json={"value": 5.0},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_lab_result_for_other_patient_is_404(self, client, session):
        owner_id = _create_patient(client, reference="SYN-OWNER").json()["id"]
        record_id = client.post(
            f"{PATIENTS_URL}/{owner_id}/clinical-records",
            json={"condition": "Hypertension"},
        ).json()["id"]
        _create_patient(client, reference="SYN-OTHER")
        other_id = client.get(
            PATIENTS_URL, params={"search": "SYN-OTHER"}
        ).json()["items"][0]["id"]
        response = client.post(
            f"{PATIENTS_URL}/{other_id}/clinical-records/{record_id}/lab-results",
            json={"test_name": "HbA1c", "value": 6.5},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_lab_results(self, client, session):
        patient_id = _create_patient(client).json()["id"]
        record_id = client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records",
            json={"condition": "Hypertension"},
        ).json()["id"]
        client.post(
            f"{PATIENTS_URL}/{patient_id}/clinical-records/{record_id}/lab-results",
            json={"test_name": "HbA1c", "value": 6.5, "unit": "%"},
        )
        response = client.get(
            f"{PATIENTS_URL}/{patient_id}/clinical-records/{record_id}/lab-results"
        )
        assert response.status_code == status.HTTP_200_OK
        results = response.json()
        assert len(results) == 1
        assert results[0]["test_name"] == "HbA1c"


class TestFacilityEndpoints:
    def test_list_facilities(self, client, session):
        _add_facility(session, name="Alpha PHC")
        _add_facility(session, name="Beta CHC")
        response = client.get(FACILITIES_URL)
        assert response.status_code == status.HTTP_200_OK
        names = [f["name"] for f in response.json()]
        assert names == sorted(names)
        assert "Alpha PHC" in names