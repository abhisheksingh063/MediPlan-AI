"""Service and API tests for the Phase 11 ML inference endpoint.

The endpoint accepts a validated 17-field clinical input and returns a
calibrated probability of early (<30-day) readmission with the prototype
review flag. The DB-backed ``client`` fixture is intentionally not used: the
inference endpoint is DB-independent, so these tests run without a database.
Expected probabilities for the fixed payloads were computed from the frozen
Phase 7-10 artifacts (preprocessor, selected model, sigmoid calibrator,
threshold 0.1) and are pinned with a small tolerance.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml import compare, preprocessing, validate
from app.ml.config import FEATURES
from app.services import inference as inference_service
from app.services.inference import InsufficientInputError

ML_URL = "/api/v1/ml/predict"

VALID_PAYLOAD = {
    "race": "Asian",
    "gender": "Female",
    "age": "[70-80)",
    "admission_type_id": 2,
    "admission_source_id": 7,
    "time_in_hospital": 1,
    "num_lab_procedures": 20,
    "num_procedures": 0,
    "num_medications": 5,
    "number_outpatient": 0,
    "number_emergency": 0,
    "number_inpatient": 0,
    "number_diagnoses": 3,
    "max_glu_serum": "Norm",
    "A1Cresult": "Norm",
    "diabetesMed": "No",
    "change": "Ch",
}

LOW_RISK = VALID_PAYLOAD
LOW_RISK_PROBABILITY = 0.054689  # expected calibrated probability < 0.1

HIGH_RISK = {
    **VALID_PAYLOAD,
    "age": "[90-100)",
    "max_glu_serum": ">300",
    "A1Cresult": ">8",
    "diabetesMed": "Yes",
    "num_procedures": 6,
    "num_medications": 30,
    "time_in_hospital": 14,
    "number_inpatient": 5,
    "number_diagnoses": 16,
}
HIGH_RISK_PROBABILITY = 0.388865  # expected calibrated probability >= 0.1

REVIEW_THRESHOLD = 0.1


def _raw_probability(payload: dict) -> float:
    frame = inference_service._build_raw_frame(payload)
    encoded = preprocessing.apply_preprocessor(
        preprocessing.load_preprocessor(), frame
    ).to_numpy("float64")
    return float(
        compare.baseline.predict_probabilities(compare.load_selected_model(), encoded)[0]
    )


class TestInferenceService:
    def test_low_risk_below_review_threshold(self):
        result = inference_service.predict(LOW_RISK)
        assert result["probability"] == pytest.approx(LOW_RISK_PROBABILITY, abs=1e-6)
        assert result["review_required"] is False

    def test_high_risk_at_or_above_review_threshold(self):
        result = inference_service.predict(HIGH_RISK)
        assert result["probability"] == pytest.approx(HIGH_RISK_PROBABILITY, abs=1e-6)
        assert result["review_required"] is True

    def test_probability_in_unit_interval(self):
        for payload in (LOW_RISK, HIGH_RISK):
            probability = inference_service.predict_probability(payload)
            assert 0.0 <= probability <= 1.0

    def test_calibration_is_applied(self):
        raw = _raw_probability(LOW_RISK)
        calibrated = inference_service.predict_probability(LOW_RISK)
        assert calibrated == pytest.approx(LOW_RISK_PROBABILITY, abs=1e-6)
        assert abs(calibrated - raw) > 1e-3

    def test_response_reports_expected_metadata(self):
        result = inference_service.predict(HIGH_RISK)
        assert result["model_version"] == "selected-model-v1"
        assert result["threshold"] == REVIEW_THRESHOLD
        assert result["calibration"] == {
            "method": "sigmoid",
            "version": "validation-config-v1",
        }
        assert "probability" in result["safety_message"].lower()

    def test_missing_required_input_raises_insufficient_input(self):
        payload = dict(LOW_RISK)
        del payload["num_procedures"]
        with pytest.raises(InsufficientInputError):
            inference_service.predict(payload)


class TestInferenceEndpoint:
    def test_predict_returns_calibrated_probability_low(self):
        with TestClient(app) as client:
            response = client.post(ML_URL, json=VALID_PAYLOAD)
        assert response.status_code == 200
        body = response.json()
        assert body["probability"] == pytest.approx(LOW_RISK_PROBABILITY, abs=1e-6)
        assert body["review_required"] is False
        assert body["threshold"] == REVIEW_THRESHOLD

    def test_predict_returns_calibrated_probability_high(self):
        with TestClient(app) as client:
            response = client.post(ML_URL, json=HIGH_RISK)
        assert response.status_code == 200
        body = response.json()
        assert body["probability"] == pytest.approx(HIGH_RISK_PROBABILITY, abs=1e-6)
        assert body["review_required"] is True

    def test_predict_rejects_invalid_categorical_value(self):
        payload = dict(VALID_PAYLOAD)
        payload["race"] = "UnknownBreed"
        with TestClient(app) as client:
            response = client.post(ML_URL, json=payload)
        assert response.status_code == 422

    def test_predict_rejects_unknown_admission_source(self):
        payload = dict(VALID_PAYLOAD)
        payload["admission_source_id"] = 999
        with TestClient(app) as client:
            response = client.post(ML_URL, json=payload)
        assert response.status_code == 422

    def test_predict_rejects_out_of_range_numeric(self):
        payload = dict(VALID_PAYLOAD)
        payload["time_in_hospital"] = 0
        with TestClient(app) as client:
            response = client.post(ML_URL, json=payload)
        assert response.status_code == 422

    def test_predict_rejects_missing_required_field(self):
        payload = dict(VALID_PAYLOAD)
        del payload["num_medications"]
        with TestClient(app) as client:
            response = client.post(ML_URL, json=payload)
        assert response.status_code == 422

    def test_predict_rejects_wrong_field_type(self):
        payload = dict(VALID_PAYLOAD)
        payload["num_procedures"] = "two"
        with TestClient(app) as client:
            response = client.post(ML_URL, json=payload)
        assert response.status_code == 422

    def test_predict_503_when_model_artifact_unavailable(self, monkeypatch):
        def broken_loader():
            raise inference_service.ModelArtifactError("simulated failure")

        monkeypatch.setattr(inference_service, "_load_model", broken_loader)
        with TestClient(app) as client:
            response = client.post(ML_URL, json=VALID_PAYLOAD)
        assert response.status_code == 503
        assert "artifact" in response.json()["detail"].lower()


class TestSchemaValidation:
    def test_request_accepts_all_allowed_categories(self):
        for race in ("AfricanAmerican", "Asian", "Caucasian", "Hispanic", "Other", "Unknown"):
            payload = dict(VALID_PAYLOAD)
            payload["race"] = race
            response = inference_service.predict(payload)
            assert 0.0 <= response["probability"] <= 1.0

    def test_admission_source_id_must_be_in_observed_set(self):
        import pydantic

        payload = dict(VALID_PAYLOAD)
        payload["admission_source_id"] = 15
        with pytest.raises(pydantic.ValidationError):
            from app.schemas.inference import InferenceRequest

            InferenceRequest(**payload)

    def test_age_bins_match_preprocessor_ordinal_categories(self):
        from app.schemas.inference import AgeBin

        ordinal_encoder = preprocessing.load_preprocessor().named_transformers_[
            "ordinal_age"
        ].named_steps["encoder"]
        expected = list(ordinal_encoder.categories_[0])
        assert list(AgeBin.__args__) == expected