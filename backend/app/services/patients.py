"""Patient-management application services.

Keeps persistence and validation logic out of the API route handlers, following
the Phase 4 architecture boundary (``backend/app/services/``). HTTP status
semantics are surfaced as ``HTTPException`` so routers stay thin.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import ClinicalRecord, Facility, LabResult, Patient
from app.schemas.clinical_record import ClinicalRecordCreate
from app.schemas.lab_result import LabResultCreate
from app.schemas.patient import PatientCreate, PatientUpdate

_NOT_FOUND = "Patient not found"


def _patient_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def ensure_record_belongs_to_patient(
    record: ClinicalRecord, patient_id: int
) -> None:
    """Raise 404 unless the record belongs to the given patient."""
    if record.patient_id != patient_id:
        raise _patient_not_found()


def _facility_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid facility reference",
    )


def _duplicate_reference(reference: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Patient reference already exists: {reference}",
    )


def _ensure_facility_exists(db: Session, facility_id: int) -> None:
    exists = db.scalar(
        select(Facility.id).where(Facility.id == facility_id)
    )
    if exists is None:
        raise _facility_not_found()


def _ensure_unique_reference(
    db: Session, reference: str, exclude_id: int | None = None
) -> None:
    query = select(Patient.id).where(Patient.external_reference == reference)
    if exclude_id is not None:
        query = query.where(Patient.id != exclude_id)
    if db.scalar(query) is not None:
        raise _duplicate_reference(reference)


def list_patients(db: Session, search: str | None = None) -> list[Patient]:
    """Return patients ordered newest-first, optionally filtered by reference."""
    query = select(Patient).options(selectinload(Patient.current_facility))
    if search:
        query = query.where(
            Patient.external_reference.ilike(f"%{search.strip()}%")
        )
    return list(
        db.scalars(query.order_by(Patient.created_at.desc(), Patient.id.desc()))
    )


def get_patient(db: Session, patient_id: int) -> Patient | None:
    """Return a single patient with its current facility loaded."""
    return db.scalar(
        select(Patient)
        .options(selectinload(Patient.current_facility))
        .where(Patient.id == patient_id)
    )


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = get_patient(db, patient_id)
    if patient is None:
        raise _patient_not_found()
    return patient


def create_patient(db: Session, data: PatientCreate) -> Patient:
    if data.current_facility_id is not None:
        _ensure_facility_exists(db, data.current_facility_id)
    _ensure_unique_reference(db, data.external_reference)
    patient = Patient(**data.model_dump())
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_reference(data.external_reference) from exc
    db.refresh(patient)
    return patient


def update_patient(
    db: Session, patient: Patient, data: PatientUpdate
) -> Patient:
    fields = data.model_dump(exclude_unset=True)
    if "current_facility_id" in fields and fields["current_facility_id"] is not None:
        _ensure_facility_exists(db, fields["current_facility_id"])
    if "external_reference" in fields and fields["external_reference"] != patient.external_reference:
        _ensure_unique_reference(db, fields["external_reference"], exclude_id=patient.id)
    for field, value in fields.items():
        setattr(patient, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_reference(fields.get("external_reference", "")) from exc
    db.refresh(patient)
    return patient


def get_clinical_record_or_404(
    db: Session, record_id: int
) -> ClinicalRecord:
    record = db.get(ClinicalRecord, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Clinical record not found"
        )
    return record


def list_clinical_records(
    db: Session, patient_id: int
) -> list[ClinicalRecord]:
    """Return a patient's clinical records (with lab results) newest-first."""
    return list(
        db.scalars(
            select(ClinicalRecord)
            .options(selectinload(ClinicalRecord.lab_results))
            .where(ClinicalRecord.patient_id == patient_id)
            .order_by(ClinicalRecord.recorded_at.desc(), ClinicalRecord.id.desc())
        )
    )


def create_clinical_record(
    db: Session, patient_id: int, data: ClinicalRecordCreate
) -> ClinicalRecord:
    record = ClinicalRecord(
        patient_id=patient_id,
        condition=data.condition,
        history_text=data.history_text,
        allergies=data.allergies,
        current_medications=data.current_medications,
        previous_treatments=data.previous_treatments,
        recorded_at=data.recorded_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_lab_results(
    db: Session, clinical_record_id: int
) -> list[LabResult]:
    return list(
        db.scalars(
            select(LabResult)
            .where(LabResult.clinical_record_id == clinical_record_id)
            .order_by(LabResult.recorded_at.asc(), LabResult.id.asc())
        )
    )


def create_lab_result(
    db: Session, clinical_record_id: int, data: LabResultCreate
) -> LabResult:
    result = LabResult(
        clinical_record_id=clinical_record_id,
        test_name=data.test_name,
        value=data.value,
        unit=data.unit,
        reference_range=data.reference_range,
        recorded_at=data.recorded_at,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result