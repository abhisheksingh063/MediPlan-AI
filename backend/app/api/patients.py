"""Patient-management API routes.

Endpoints follow the Phase 4 convention: plural resource names under
``/api/v1``. Handlers stay thin; persistence and validation live in
``app.services.patients``.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.clinical_record import ClinicalRecordCreate, ClinicalRecordRead
from app.schemas.lab_result import LabResultCreate, LabResultRead
from app.schemas.patient import PatientCreate, PatientList, PatientRead, PatientUpdate
from app.services import patients as service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=PatientList)
def list_patients(
    search: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
) -> PatientList:
    """List synthetic patients, optionally filtered by reference."""
    rows = service.list_patients(db, search=search)
    return PatientList(items=[PatientRead.model_validate(p) for p in rows])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)) -> PatientRead:
    """Create a synthetic patient."""
    return PatientRead.model_validate(service.create_patient(db, payload))


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: int, db: Session = Depends(get_db)) -> PatientRead:
    """Return a single patient."""
    return PatientRead.model_validate(service.get_patient_or_404(db, patient_id))


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: int, payload: PatientUpdate, db: Session = Depends(get_db)
) -> PatientRead:
    """Update an existing synthetic patient."""
    patient = service.get_patient_or_404(db, patient_id)
    return PatientRead.model_validate(service.update_patient(db, patient, payload))


@router.post(
    "/{patient_id}/clinical-records",
    response_model=ClinicalRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_clinical_record(
    patient_id: int,
    payload: ClinicalRecordCreate,
    db: Session = Depends(get_db),
) -> ClinicalRecordRead:
    """Create a clinical record for a patient."""
    service.get_patient_or_404(db, patient_id)
    record = service.create_clinical_record(db, patient_id, payload)
    return ClinicalRecordRead.model_validate(
        service.get_clinical_record_or_404(db, record.id)
    )


@router.get("/{patient_id}/clinical-records", response_model=list[ClinicalRecordRead])
def list_clinical_records(
    patient_id: int, db: Session = Depends(get_db)
) -> list[ClinicalRecordRead]:
    """List a patient's clinical records, newest first, with lab results."""
    service.get_patient_or_404(db, patient_id)
    records = service.list_clinical_records(db, patient_id)
    return [ClinicalRecordRead.model_validate(r) for r in records]


@router.post(
    "/{patient_id}/clinical-records/{record_id}/lab-results",
    response_model=LabResultRead,
    status_code=status.HTTP_201_CREATED,
)
def create_lab_result(
    patient_id: int,
    record_id: int,
    payload: LabResultCreate,
    db: Session = Depends(get_db),
) -> LabResultRead:
    """Create a lab result on a clinical record belonging to the patient."""
    service.get_patient_or_404(db, patient_id)
    record = service.get_clinical_record_or_404(db, record_id)
    service.ensure_record_belongs_to_patient(record, patient_id)
    return LabResultRead.model_validate(
        service.create_lab_result(db, record.id, payload)
    )


@router.get(
    "/{patient_id}/clinical-records/{record_id}/lab-results",
    response_model=list[LabResultRead],
)
def list_lab_results(
    patient_id: int,
    record_id: int,
    db: Session = Depends(get_db),
) -> list[LabResultRead]:
    """List lab results for a clinical record belonging to the patient."""
    service.get_patient_or_404(db, patient_id)
    record = service.get_clinical_record_or_404(db, record_id)
    service.ensure_record_belongs_to_patient(record, patient_id)
    return [
        LabResultRead.model_validate(r)
        for r in service.list_lab_results(db, record.id)
    ]