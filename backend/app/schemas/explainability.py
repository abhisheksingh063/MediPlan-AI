"""Schemas for the Phase 12 ML explainability endpoint.

The request reuses :class:`app.schemas.inference.InferenceRequest` unchanged so
the explain and predict endpoints accept exactly the same validated 17-field
clinical input. The response extends the Phase 11 inference response with the
SHAP contributor list.
"""

from typing import Literal

from pydantic import BaseModel

from app.schemas.inference import InferenceResponse

ExplanationMethod = Literal["SHAP"]
ContributionDirection = Literal["higher_risk", "lower_risk"]


class Contributor(BaseModel):
    """Contribution of one original clinical input to the model estimate.

    ``contribution`` is the aggregated SHAP value (in the model's log-odds
    output space) for the original feature, i.e. the amount the feature pushed
    the underlying model estimate up (``higher_risk``) or down
    (``lower_risk``) relative to the background baseline. It is a model
    behaviour description, not a causal clinical effect.
    """

    feature: str
    value: str | int
    contribution: float
    direction: ContributionDirection
    rank: int
    label: str | None = None


class ExplanationResponse(InferenceResponse):
    """Inference result plus a local SHAP explanation for clinician review."""

    explanation_method: ExplanationMethod
    contributors: list[Contributor]
    explanation_note: str