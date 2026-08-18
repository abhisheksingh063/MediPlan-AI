"""HTTP API for the evidence-cited treatment decision support module.

Phase 13: returns clinical considerations derived from the patient's recorded
data against declarative ADA-2026 rules. Output is decision-support only and is
kept separate from the machine-learning readmission estimate.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.treatment_support import (
    TreatmentSupportRequest,
    TreatmentSupportResponse,
)
from app.services import treatment_support as service

router = APIRouter(prefix="/treatment-support", tags=["treatment-support"])


@router.post(
    "",
    response_model=TreatmentSupportResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate evidence-based clinical considerations for a patient",
)
def evaluate_treatment_support(
    payload: TreatmentSupportRequest,
    db: Session = Depends(get_db),
) -> TreatmentSupportResponse:
    """Return triggered considerations plus any missing clinical information.

    The evaluation uses only the patient's recorded demographic and laboratory
    data. Machine-learning readmission estimates are never part of rule
    evaluation. The result is decision-support only and requires clinician
    review; it never selects drugs, doses, or diagnoses.
    """
    result = service.evaluate(db, payload.patient_id)
    return TreatmentSupportResponse(**result)
