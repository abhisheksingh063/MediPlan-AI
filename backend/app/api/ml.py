"""HTTP API exposing the Phase 7-10 readmission model for decision support."""

from fastapi import APIRouter, HTTPException

from app.schemas.inference import InferenceRequest, InferenceResponse
from app.services import inference as inference_service
from app.services.inference import InferenceError, InsufficientInputError

router = APIRouter(prefix="/ml", tags=["ml"])


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
    except InsufficientInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InferenceError as exc:
        raise HTTPException(
            status_code=503, detail=str(exc)
        ) from exc
    return InferenceResponse(**result)