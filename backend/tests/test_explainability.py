"""Service and API tests for the Phase 12 SHAP explainability layer.

SHAP values are computed with ``shap.LinearExplainer`` (interventional,
deterministic and exact for a linear model) on the selected Logistic
Regression in log-odds space, then aggregated from the 55 transformed features
back to the 17 original clinical inputs. Pinned contributions were computed
from the frozen Phase 7-10 artifacts and are asserted with a small tolerance.
The inference endpoint is DB-independent, so no DB-backed fixture is used.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.config import FEATURES
from app.services import explainability, inference as inference_service

EXPLAIN_URL = "/api/v1/ml/explain"
GLOBAL_URL = "/api/v1/ml/explain/global"

LOW_RISK = {
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

HIGH_RISK = {
    **LOW_RISK,
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

LOW_PROBABILITY = 0.054689
HIGH_PROBABILITY = 0.388865
THRESHOLD = 0.1


class TestShapCalculation:
    def test_explanation_generated_with_finite_values(self):
        result = explainability.explain(LOW_RISK)
        assert len(result["contributors"]) == 17
        for contributor in result["contributors"]:
            assert pytest.approx(contributor["contribution"]) == contributor["contribution"]
            assert abs(contributor["contribution"]) < 5.0
            assert 0.0 <= result["probability"] <= 1.0

    def test_expected_feature_dimensions(self):
        parts = inference_service.predict_parts(LOW_RISK)
        assert parts["encoded_array"].shape == (1, 55)
        assert len(parts["encoded_feature_names"]) == 55

    def test_additivity_log_odds_consistency(self):
        parts = inference_service.predict_parts(LOW_RISK)
        explainer = explainability._load_explainer()
        shap_values = explainer.shap_values(parts["encoded_array"])[0]
        contributions = explainability._aggregate_contributions(shap_values)
        expected_value = float(explainer.expected_value)
        logit = parts["logit"]
        assert sum(contributions.values()) + expected_value == pytest.approx(logit, abs=1e-9)

    def test_explanation_is_deterministic(self):
        first = explainability.explain(LOW_RISK)["contributors"]
        second = explainability.explain(LOW_RISK)["contributors"]
        assert first == second

    def test_contributors_sorted_by_absolute_value_descending(self):
        contributors = explainability.explain(HIGH_RISK)["contributors"]
        magnitudes = [abs(c["contribution"]) for c in contributors]
        assert magnitudes == sorted(magnitudes, reverse=True)
        assert [c["rank"] for c in contributors] == list(range(1, len(contributors) + 1))


class TestFeatureMapping:
    def test_maps_to_original_feature_names_only(self):
        contributors = explainability.explain(LOW_RISK)["contributors"]
        names = {c["feature"] for c in contributors}
        assert names == set(FEATURES)
        assert "race_Asian" not in names
        assert "nominal__gender_Female" not in names

    def test_aggregated_contribution_numerically_correct(self):
        parts = inference_service.predict_parts(LOW_RISK)
        shap_values = explainability._load_explainer().shap_values(parts["encoded_array"])[0]
        contributions = explainability._aggregate_contributions(shap_values)
        groups = explainability._feature_groups()
        for feature, start, count in groups:
            assert contributions[feature] == pytest.approx(
                float(shap_values[start : start + count].sum()), abs=1e-12
            )

    def test_displayed_value_is_the_original_input(self):
        contributors = explainability.explain(LOW_RISK)["contributors"]
        values = {c["feature"]: c["value"] for c in contributors}
        assert values["age"] == "[70-80)"
        assert values["race"] == "Asian"
        assert values["time_in_hospital"] == 1
        assert values["admission_source_id"] == 7


class TestDirection:
    def test_positive_contribution_is_higher_risk(self):
        for contributor in explainability.explain(HIGH_RISK)["contributors"]:
            expected = "higher_risk" if contributor["contribution"] >= 0 else "lower_risk"
            assert contributor["direction"] == expected

    def test_pinned_contributions_and_directions(self):
        contributors = {c["feature"]: c for c in explainability.explain(LOW_RISK)["contributors"]}
        assert contributors["race"]["contribution"] == pytest.approx(-0.314358, abs=1e-6)
        assert contributors["race"]["direction"] == "lower_risk"
        assert contributors["max_glu_serum"]["contribution"] == pytest.approx(0.259999, abs=1e-6)
        assert contributors["max_glu_serum"]["direction"] == "higher_risk"


class TestExplanationEndpoint:
    def test_explain_valid_low_risk(self):
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=LOW_RISK)
        assert response.status_code == 200
        body = response.json()
        assert body["probability"] == pytest.approx(LOW_PROBABILITY, abs=1e-6)
        assert body["threshold"] == THRESHOLD
        assert body["review_required"] is False
        assert body["model_version"] == "selected-model-v1"
        assert body["explanation_method"] == "SHAP"
        assert body["calibration"] == {
            "method": "sigmoid",
            "version": "validation-config-v1",
        }
        assert body["explanation_note"]
        assert body["safety_message"]
        assert len(body["contributors"]) == 17

    def test_explain_valid_high_risk(self):
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=HIGH_RISK)
        assert response.status_code == 200
        body = response.json()
        assert body["probability"] == pytest.approx(HIGH_PROBABILITY, abs=1e-6)
        assert body["review_required"] is True

    def test_explain_top_n_query(self):
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=HIGH_RISK, params={"top_n": 5})
        assert response.status_code == 200
        contributors = response.json()["contributors"]
        assert len(contributors) == 5
        magnitudes = [abs(c["contribution"]) for c in contributors]
        assert magnitudes == sorted(magnitudes, reverse=True)

    def test_explain_top_n_out_of_range_rejected(self):
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=LOW_RISK, params={"top_n": 0})
        assert response.status_code == 422
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=LOW_RISK, params={"top_n": 18})
        assert response.status_code == 422

    def test_explain_probability_matches_predict_endpoint(self):
        with TestClient(app) as client:
            predict_body = client.post("/api/v1/ml/predict", json=HIGH_RISK).json()
            explain_body = client.post(EXPLAIN_URL, json=HIGH_RISK).json()
        assert explain_body["probability"] == predict_body["probability"]
        assert explain_body["threshold"] == predict_body["threshold"]
        assert explain_body["review_required"] == predict_body["review_required"]
        assert explain_body["calibration"] == predict_body["calibration"]


class TestExplanationValidation:
    def test_explain_rejects_invalid_categorical(self):
        payload = dict(LOW_RISK)
        payload["race"] = "UnknownBreed"
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=payload)
        assert response.status_code == 422

    def test_explain_rejects_unknown_admission_source(self):
        payload = dict(LOW_RISK)
        payload["admission_source_id"] = 999
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=payload)
        assert response.status_code == 422

    def test_explain_rejects_out_of_range_numeric(self):
        payload = dict(LOW_RISK)
        payload["time_in_hospital"] = 0
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=payload)
        assert response.status_code == 422

    def test_explain_rejects_missing_field(self):
        payload = dict(LOW_RISK)
        del payload["num_medications"]
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=payload)
        assert response.status_code == 422

    def test_explain_503_without_internal_details_on_artifact_failure(self, monkeypatch):
        def broken_explainer():
            raise inference_service.ModelArtifactError("simulated failure")

        monkeypatch.setattr(explainability, "_load_explainer", broken_explainer)
        with TestClient(app) as client:
            response = client.post(EXPLAIN_URL, json=LOW_RISK)
        assert response.status_code == 503
        assert "artifact" in response.json()["detail"].lower()
        assert "simulated failure" not in response.json()["detail"]


class TestGlobalSummary:
    def test_global_summary_aggregates_only(self):
        summary = explainability.global_summary()
        features = summary["features"]
        assert len(features) == 17
        assert {f["feature"] for f in features} == set(FEATURES)
        for row in features:
            assert row["mean_abs_shap"] >= 0.0
            assert abs(row["mean_abs_shap"]) < 5.0
        assert [f["mean_abs_shap"] for f in features] == sorted(
            (f["mean_abs_shap"] for f in features), reverse=True
        )
        assert summary["artifact"]["version"] == "explainability-global-v1"

    def test_global_endpoint_returns_aggregates(self):
        with TestClient(app) as client:
            response = client.get(GLOBAL_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["features"]) == 17
        assert "explanation_method" not in body