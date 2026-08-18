"""HTTP API exposing the Phase 7-10 readmission model for decision support."""

from fastapi import APIRouter, HTTPException, Query

from app.schemas.explainability import ExplanationResponse
from app.schemas.inference import InferenceRequest, InferenceResponse
from app.services import explainability, inference as inference_service
from app.services.inference import InferenceError, InsufficientInputError

router = APIRouter(prefix="/ml", tags=["ml"])


def _handle_inference_error(exc: InferenceError) -> HTTPException:
    """Map service failures to controlled HTTP responses (no internals)."""
    if isinstance(exc, InsufficientInputError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


@router.post(
    "/predict",
    response_model=InferenceResponse,
    summary="Estimate early-readmission probability for clinical review",
)
def predict(payload: InferenceRequest) -> InferenceResponse:
    """Return a calibrated probability of early (<30-day) readmission.

    Decision-support output only: the result flags encounters whose estimated
    readmission risk meets or exceeds the prototype review threshold.
    """
    try:
        result = inference_service.predict(payload.model_dump())
    except InferenceError as exc:
        raise _handle_inference_error(exc) from exc
    return InferenceResponse(**result)


@router.post(
    "/explain",
    response_model=ExplanationResponse,
    summary="Estimate early-readmission probability with a SHAP explanation",
)
def explain(
    payload: InferenceRequest,
    top_n: int | None = Query(default=None, ge=1, le=17),
) -> ExplanationResponse:
    """Return the calibrated probability plus per-feature SHAP contributions.

    Contributions are aggregated to the original clinical input fields and
    describe what moved the underlying model estimate; they are not causal
    clinical effects.
    """
    try:
        result = explainability.explain(payload.model_dump(), top_n=top_n)
    except InferenceError as exc:
        raise _handle_inference_error(exc) from exc
    return ExplanationResponse(**result)


@router.get(
    "/explain/global",
    summary="Global SHAP feature-importance summary (aggregates only)",
)
def explain_global() -> dict:
    """Return the offline-generated global feature-importance summary.

    The summary contains only aggregate statistics over the validation
    partition; no individual patient or encounter records are exposed.
    """
    try:
        return explainability.global_summary()
    except InferenceError as exc:
        raise _handle_inference_error(exc) from exc