"""Service and API tests for Phase 13 evidence-cited treatment decision support.

Covers the declarative rule data (uniqueness, evidence metadata, no banned
wording, no hallucinated thresholds), rule evaluation behaviour (trigger,
missing vs stale suppression, conflicts returned unranked), machine-learning
separation, and the HTTP endpoint. All assertions work on synthetic data.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status

from app.models import ClinicalRecord, LabResult, Patient
from app.services import patients as patients_service
from app.services import treatment_support as service

TREATMENT_URL = "/api/v1/treatment-support"

NOW = datetime.now(timezone.utc)


def _seed_patient(
    session,
    *,
    reference: str = "SYN-TDS-001",
    age: int | None = 45,
    height: float | None = 170.0,
    weight: float | None = 68.0,
) -> int:
    patient = Patient(
        external_reference=reference,
        age=age,
        height=height,
        weight=weight,
    )
    session.add(patient)
    session.flush()
    return patient.id


def _add_labs(
    session,
    patient_id: int,
    labs: dict[str, float],
    recorded_at: datetime | None = None,
) -> None:
    record = ClinicalRecord(patient_id=patient_id, condition="Diabetes")
    session.add(record)
    session.flush()
    stamp = recorded_at or NOW
    for test_name, value in labs.items():
        session.add(
            LabResult(
                clinical_record_id=record.id,
                test_name=test_name,
                value=value,
                recorded_at=stamp,
            )
        )
    session.flush()


def _evaluate(session, patient_id: int) -> dict:
    return service.evaluate(session, patient_id)


def _rule_ids(result: dict) -> set[str]:
    return {c["rule_id"] for c in result["considerations"]}


def _missing_fields(result: dict) -> dict[str, dict]:
    return {m["field"]: m for m in result["missing_information"]}


def _trigger_fields(trigger: dict) -> set[str]:
    if trigger["op"] in {"all", "any"}:
        fields: set[str] = set()
        for clause in trigger["clauses"]:
            fields |= _trigger_fields(clause)
        return fields
    return {trigger["field"]}


class TestRuleData:
    def test_rule_ids_unique(self):
        ids = [rule["rule_id"] for rule in service._rules()]
        assert len(ids) == len(set(ids))

    def test_every_rule_has_full_metadata(self):
        allowed_severity = {"informational", "consider_review", "urgent_review"}
        for rule in service._rules():
            assert rule["rule_id"]
            assert rule["title"]
            assert rule["clinical_context"]
            assert rule["required_inputs"]
            assert rule["logic_summary"]
            assert rule["output_text"]
            assert rule["severity_tag"] in allowed_severity
            assert rule["requires_clinician_review"] is True
            evidence = rule["evidence_source"]
            for key in ("organization", "document", "version", "section", "doi"):
                assert evidence[key], f"{rule['rule_id']} missing evidence {key}"

    def test_ada_rule_citations_point_to_2026_edition(self):
        for rule in service._rules():
            if rule["evidence_source"]["organization"] == "American Diabetes Association":
                assert "2026" in rule["evidence_source"]["version"]
                assert rule["evidence_source"]["doi"].startswith("10.2337/dc26-")

    def test_non_ada_rule_is_explicitly_named(self):
        ada_rules = {rule["rule_id"] for rule in service._rules()} - {"TDS-009"}
        for rule_id in ada_rules:
            rule = next(r for r in service._rules() if r["rule_id"] == rule_id)
            assert rule["evidence_source"]["organization"] == "American Diabetes Association"
        crisis = next(r for r in service._rules() if r["rule_id"] == "TDS-009")
        assert crisis["evidence_source"]["organization"].startswith("American College")

    def test_rule_inputs_reference_catalog_fields(self):
        catalog = service._input_catalog()
        for rule in service._rules():
            assert set(rule["required_inputs"]).issubset(catalog.keys())
            trigger_fields = _trigger_fields(rule["trigger"])
            assert trigger_fields.issubset(catalog.keys())
            assert trigger_fields.issubset(set(rule["required_inputs"]))

    def test_no_banned_wording_in_rule_output(self):
        banned = [
            "prescribe",
            "start",
            "stop",
            "increase dose",
            "decrease dose",
            "the patient should take",
            "this patient has diabetes because",
            "the ai recommends",
        ]
        for rule in service._rules():
            lowered = rule["output_text"].lower()
            for token in banned:
                assert token not in lowered, f"{rule['rule_id']} uses banned wording: {token}"

    def test_no_invented_dosages_drug_selection_or_auto_decisions(self):
        for rule in service._rules():
            lowered = rule["output_text"].lower()
            assert " dosage" not in lowered
            assert " dose" not in lowered
            for phrase in ["start metformin", "start insulin", "start statin",
                           "prescribe ", "recommend metformin", "recommend insulin"]:
                assert phrase not in lowered, f"{rule['rule_id']}: {phrase}"


class TestEvaluation:
    def test_glycemic_rule_triggers_above_goal(self, session):
        patient_id = _seed_patient(session, age=45)
        _add_labs(session, patient_id, {"HbA1c": 7.2})
        result = _evaluate(session, patient_id)
        assert "TDS-001" in _rule_ids(result)
        assert "TDS-002" not in _rule_ids(result)
        assert "TDS-003" not in _rule_ids(result)

    def test_combination_rule_triggers_at_1_5_percent_above_goal(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"HbA1c": 8.5})
        result = _evaluate(session, patient_id)
        assert {"TDS-001", "TDS-002"} <= _rule_ids(result)

    def test_marked_hyperglycemia_rule_triggers_strictly_above_10(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"HbA1c": 10.1})
        assert "TDS-003" in _rule_ids(_evaluate(session, patient_id))

    def test_marked_hyperglycemia_not_triggered_at_exactly_10(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"HbA1c": 10.0})
        assert "TDS-003" not in _rule_ids(_evaluate(session, patient_id))

    def test_renal_and_albuminuria_rules(self, session):
        patient_id = _seed_patient(session)
        _add_labs(
            session,
            patient_id,
            {"eGFR": 55.0, "UACR": 45.0},
        )
        result = _evaluate(session, patient_id)
        assert {"TDS-004", "TDS-005"} <= _rule_ids(result)

    def test_correct_renal_values_do_not_trigger(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"eGFR": 70.0, "UACR": 20.0})
        result = _rule_ids(_evaluate(session, patient_id))
        assert "TDS-004" not in result
        assert "TDS-005" not in result

    def test_blood_pressure_rules(self, session):
        patient_id = _seed_patient(session)
        _add_labs(
            session,
            patient_id,
            {"Systolic BP": 135.0, "Diastolic BP": 85.0},
        )
        result = _evaluate(session, patient_id)
        assert "TDS-008" in _rule_ids(result)
        assert "TDS-009" not in _rule_ids(result)

    def test_hypertensive_crisis_rule(self, session):
        patient_id = _seed_patient(session)
        _add_labs(
            session,
            patient_id,
            {"Systolic BP": 190.0, "Diastolic BP": 95.0},
        )
        result = _evaluate(session, patient_id)
        assert "TDS-009" in _rule_ids(result)

    def test_bmi_computed_from_height_and_weight(self, session):
        tall_lean = _seed_patient(session, reference="SYN-BMI-1", height=170.0, weight=75.0)
        status_obese = _seed_patient(session, reference="SYN-BMI-2", height=170.0, weight=105.0)
        lean_result = _evaluate(session, tall_lean)
        assert "TDS-007" in _rule_ids(lean_result)  # BMI ~25.95 -> overweight
        assert "TDS-006" not in _rule_ids(lean_result)
        obese_result = _evaluate(session, status_obese)
        assert "TDS-006" in _rule_ids(obese_result)  # BMI ~36.3 -> obesity
        assert "TDS-007" not in _rule_ids(obese_result)

    def test_bmi_missing_without_height_or_weight(self, session):
        patient_id = _seed_patient(session, height=None, weight=None)
        result = _evaluate(session, patient_id)
        assert _missing_fields(result)["bmi"]["reason"] == "missing"
        assert "TDS-006" not in _rule_ids(result)
        assert "TDS-007" not in _rule_ids(result)

    def test_statin_rule_applies_to_age_40_75(self, session):
        in_range = _seed_patient(session, reference="SYN-AGE-1", age=45)
        young = _seed_patient(session, reference="SYN-AGE-2", age=33)
        assert "TDS-010" in _rule_ids(_evaluate(session, in_range))
        assert "TDS-010" not in _rule_ids(_evaluate(session, young))

    def test_older_adult_goal_conflict_is_returned_unranked(self, session):
        patient_id = _seed_patient(session, age=70)
        _add_labs(session, patient_id, {"HbA1c": 7.8})
        result = _evaluate(session, patient_id)
        ids = set(c["rule_id"] for c in result["considerations"])
        assert "TDS-001" in ids and "TDS-011" in ids
        assert "not ranked" in result["interpretation_note"].lower()
        assert "synthesized" in result["interpretation_note"].lower()

    def test_missing_input_suppresses_and_reports(self, session):
        patient_id = _seed_patient(session)
        result = _evaluate(session, patient_id)
        assert _rule_ids(result) == {"TDS-010"}  # age present, labs absent
        missing = _missing_fields(result)
        assert missing["hba1c"]["reason"] == "missing"
        assert missing["egfr"]["reason"] == "missing"
        assert missing["uacr"]["reason"] == "missing"
        assert missing["systolic_bp"]["reason"] == "missing"
        assert missing["diastolic_bp"]["reason"] == "missing"
        assert "TDS-001" not in _rule_ids(result)

    def test_stale_input_is_suppressed_and_reported_as_stale(self, session):
        patient_id = _seed_patient(session)
        stale_stamp = NOW - timedelta(days=400)
        _add_labs(session, patient_id, {"HbA1c": 10.5}, recorded_at=stale_stamp)
        result = _evaluate(session, patient_id)
        assert "TDS-001" not in _rule_ids(result)
        assert "TDS-003" not in _rule_ids(result)
        entry = _missing_fields(result)["hba1c"]
        assert entry["reason"] == "stale"
        assert entry["last_available"]

    def test_most_recent_lab_result_wins(self, session):
        patient_id = _seed_patient(session)
        record = ClinicalRecord(patient_id=patient_id, condition="Diabetes")
        session.add(record)
        session.flush()
        session.add(
            LabResult(
                clinical_record_id=record.id,
                test_name="HbA1c",
                value=12.0,
                recorded_at=NOW - timedelta(days=60),
            )
        )
        session.add(
            LabResult(
                clinical_record_id=record.id,
                test_name="HbA1c",
                value=6.2,
                recorded_at=NOW - timedelta(days=2),
            )
        )
        session.flush()
        result = _evaluate(session, patient_id)
        assert "TDS-001" not in _rule_ids(result)

    def test_rule_text_renders_evaluated_values(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"HbA1c": 7.5}, )
        result = _evaluate(session, patient_id)
        tds001 = next(c for c in result["considerations"] if c["rule_id"] == "TDS-001")
        assert "7.5" in tds001["reason"]
        assert tds001["inputs_evaluated"] == ["hba1c"]
        assert tds001["requires_clinician_review"] is True
        assert "2026" in tds001["evidence_source"]

    def test_safety_and_decision_support_flags(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"HbA1c": 7.2})
        result = _evaluate(session, patient_id)
        assert result["decision_support_only"] is True
        assert result["clinical_validation_required"] is True
        assert "clinician review required" in result["safety_message"].lower()
        assert result["guideline_version"].startswith("ADA")
        assert result["generated_at"]

    def test_response_rejects_banned_wording(self, session):
        patient_id = _seed_patient(session)
        _add_labs(session, patient_id, {"HbA1c": 10.5, "eGFR": 55.0, "UACR": 45.0})
        result = _evaluate(session, patient_id)
        banned = [
            "prescribe",
            "the patient should take",
            "this patient has diabetes because",
            "the ai recommends",
            "start insulin",
            "start metformin",
        ]
        for consideration in result["considerations"]:
            lowered = consideration["reason"].lower()
            for token in banned:
                assert token not in lowered

    def test_machine_learning_results_do_not_change_rule_outcomes(
        self, session, monkeypatch
    ):
        patient_id = _seed_patient(session)
        _add_labs(
            session,
            patient_id,
            {"HbA1c": 9.0, "eGFR": 55.0, "UACR": 45.0, "Systolic BP": 135.0, "Diastolic BP": 85.0},
        )
        baseline = _evaluate(session, patient_id)
        baseline_ids = _rule_ids(baseline)

        def surprise(**kwargs):
            raise AssertionError("ML module must not be consulted during rule evaluation")

        monkeypatch.setattr(
            "app.services.inference.predict_probability", surprise, raising=True
        )
        after = _evaluate(session, patient_id)

        assert _rule_ids(after) == baseline_ids
        assert [c["reason"] for c in after["considerations"]] == [
            c["reason"] for c in baseline["considerations"]
        ]

    def test_no_inference_import_in_service_module(self):
        import app.services.treatment_support as module

        source = module.__file__
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        assert "from app.services import inference" not in text
        assert "from app.services.inference" not in text
        assert "from app.services import explainability" not in text
        assert "from app.services.explainability" not in text
        assert "import inference" not in text
        assert "import explainability" not in text


class TestTreatmentSupportAPI:
    def _create_patient(self, client, reference="SYN-API-TDS-001") -> int:
        response = client.post(
            "/api/v1/patients",
            json={
                "external_reference": reference,
                "age": 45,
                "height": 165.0,
                "weight": 68.0,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED
        return response.json()["id"]

    def test_endpoint_returns_support_payload(self, client, session):
        patient_id = self._create_patient(client)
        response = client.post(
            TREATMENT_URL, json={"patient_id": patient_id}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["patient_id"] == patient_id
        assert body["decision_support_only"] is True
        assert body["clinical_validation_required"] is True
        assert body["guideline_version"].startswith("ADA")
        assert body["generated_at"]
        assert isinstance(body["considerations"], list)
        assert isinstance(body["missing_information"], list)
        assert body["interpretation_note"]
        assert "clinician review" in body["safety_message"]

    def test_endpoint_triggers_consideration_with_sufficient_data(
        self, client, session
    ):
        patient_id = self._create_patient(client)
        record_id = client.post(
            f"/api/v1/patients/{patient_id}/clinical-records",
            json={"condition": "Diabetes"},
        ).json()["id"]
        client.post(
            f"/api/v1/patients/{patient_id}/clinical-records/{record_id}/lab-results",
            json={"test_name": "HbA1c", "value": 7.5, "unit": "%"},
        )
        response = client.post(
            TREATMENT_URL, json={"patient_id": patient_id}
        )
        body = response.json()
        assert "TDS-001" in {c["rule_id"] for c in body["considerations"]}

    def test_endpoint_insufficient_data_has_empty_considerations(
        self, client, session
    ):
        patient_id = self._create_patient(client)
        response = client.post(
            TREATMENT_URL, json={"patient_id": patient_id}
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["considerations"] == [] or all(
            c["rule_id"] != "TDS-001" for c in body["considerations"]
        )
        fields = {m["field"] for m in body["missing_information"]}
        assert "hba1c" in fields

    def test_endpoint_unknown_patient_404(self, client, session):
        response = client.post(TREATMENT_URL, json={"patient_id": 999_999})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_endpoint_rejects_invalid_patient_id(self, client, session):
        for payload in ({"patient_id": 0}, {"patient_id": -1}):
            response = client.post(TREATMENT_URL, json=payload)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_endpoint_rejects_missing_body(self, client, session):
        response = client.post(TREATMENT_URL, json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_errors_do_not_leak_patient_data(self, client, session):
        self._create_patient(client, reference="SYN-LEAK-001")
        patient_id = self._create_patient(client, reference="SYN-LEAK-002")
        record_id = client.post(
            f"/api/v1/patients/{patient_id}/clinical-records",
            json={"condition": "Diabetes"},
        ).json()["id"]
        client.post(
            f"/api/v1/patients/{patient_id}/clinical-records/{record_id}/lab-results",
            json={"test_name": "HbA1c", "value": 14.9, "unit": "%"},
        )
        response = client.post(TREATMENT_URL, json={"patient_id": 999_999})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        detail = str(response.json())
        assert "14.9" not in detail
        assert "SYN-LEAK" not in detail
        assert "Diabetes" not in detail