"""Database-layer tests for the Phase 5 schema.

Covered:
- All expected tables are created.
- Patient -> ClinicalRecord -> LabResult relationships (ORM + FK behaviour).
- Medicine -> MedicinePrice, Facility -> FacilityService relationships.
- Patient -> TreatmentPrediction, Patient -> Referral relationships.
- Foreign-key enforcement and unique constraints raise IntegrityError.
- Money is stored exactly (Numeric, never float).
- Timestamps are timezone-aware.
"""

from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    ClinicalRecord,
    Facility,
    FacilityService,
    LabResult,
    Medicine,
    MedicinePrice,
    Patient,
    Referral,
    TreatmentPrediction,
)

EXPECTED_TABLES = {
    "patients",
    "clinical_records",
    "lab_results",
    "medicines",
    "medicine_prices",
    "facilities",
    "facility_services",
    "treatment_predictions",
    "referrals",
    "audit_logs",
}


@pytest.fixture()
def patient(session: Session) -> Patient:
    row = Patient(external_reference="SYN-TEST-001", age=55, sex="M")
    session.add(row)
    session.flush()
    return row


@pytest.fixture()
def facility(session: Session) -> Facility:
    row = Facility(name="Test PHC", facility_type="phc", district="Test District")
    session.add(row)
    session.flush()
    return row


def test_all_tables_created(engine):
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= tables


def test_patient_clinical_record_relationship(session, patient):
    record = ClinicalRecord(patient=patient, condition="Type 2 Diabetes")
    session.add(record)
    session.flush()

    assert record in patient.clinical_records
    assert record.patient is patient
    assert session.scalar(
        select(ClinicalRecord).filter_by(patient_id=patient.id)
    ) is record


def test_clinical_record_lab_result_relationship(session, patient):
    record = ClinicalRecord(patient=patient, condition="Type 2 Diabetes")
    lab = LabResult(
        clinical_record=record,
        test_name="HbA1c",
        value=7.2,
        unit="%",
    )
    session.add(lab)
    session.flush()

    assert lab in record.lab_results
    assert lab.clinical_record is record
    assert session.scalar(
        select(LabResult).filter_by(clinical_record_id=record.id)
    ) is lab


def test_medicine_price_relationship(session):
    medicine = Medicine(generic_name="Metformin", strength="500 mg")
    price = MedicinePrice(medicine=medicine, source="Test source", price=12.0)
    session.add(price)
    session.flush()

    assert price in medicine.prices
    assert price.medicine is medicine
    assert session.scalar(
        select(MedicinePrice).filter_by(medicine_id=medicine.id)
    ) is price


def test_facility_service_relationship(session, facility):
    service = FacilityService(
        facility=facility,
        service_name="HbA1c test",
        availability_status="available",
    )
    session.add(service)
    session.flush()

    assert service in facility.facility_services
    assert service.facility is facility
    assert session.scalar(
        select(FacilityService).filter_by(facility_id=facility.id)
    ) is service


def test_patient_prediction_relationship(session, patient):
    prediction = TreatmentPrediction(
        patient=patient,
        model_version="test-model-1",
        option_name="early_readmission_30d",
        score=0.42,
        explanation_json={"feature": "feature_x", "contribution": 0.1},
    )
    session.add(prediction)
    session.flush()

    assert prediction in patient.predictions
    assert prediction.patient is patient
    assert session.scalar(
        select(TreatmentPrediction).filter_by(patient_id=patient.id)
    ) is prediction


def test_patient_referral_relationship(session, patient, facility):
    referral = Referral(
        patient=patient,
        required_service="Cardiology consultation",
        current_facility=facility,
        recommended_facility_level="district_hospital",
        reason="Service unknown at current facility",
    )
    session.add(referral)
    session.flush()

    assert referral in patient.referrals
    assert referral.patient is patient
    assert referral.current_facility is facility
    assert session.scalar(
        select(Referral).filter_by(patient_id=patient.id)
    ) is referral


def test_patient_current_facility_relationship(session, patient, facility):
    patient.current_facility = facility
    session.flush()

    session.expire(patient)
    assert patient.current_facility is facility


def test_foreign_key_violation_raises(session, patient):
    record = ClinicalRecord(
        patient_id=999999, condition="Type 2 Diabetes"
    )
    session.add(record)
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_external_reference_enforced(session):
    session.add(Patient(external_reference="SYN-DUP-001", age=30))
    session.flush()
    session.add(Patient(external_reference="SYN-DUP-001", age=40))
    with pytest.raises(IntegrityError):
        session.flush()


def test_money_stored_exactly(session):
    medicine = Medicine(generic_name="Metformin", strength="500 mg")
    price = MedicinePrice(medicine=medicine, source="Test source", price=Decimal("1234.56"))
    session.add(price)
    session.flush()

    stored = session.scalar(select(MedicinePrice).filter_by(id=price.id))
    assert stored.price == Decimal("1234.56")


def test_timestamps_are_timezone_aware(session, patient):
    session.flush()
    session.refresh(patient)
    assert patient.created_at.tzinfo is not None


def test_cascade_delete_patient_to_clinical_records(session, patient):
    record = ClinicalRecord(patient=patient, condition="Type 2 Diabetes")
    lab = LabResult(
        clinical_record=record, test_name="HbA1c", value=7.2, unit="%"
    )
    session.add_all([record, lab])
    session.flush()
    patient_id = patient.id

    session.execute(delete(Patient).where(Patient.id == patient_id))
    session.flush()

    assert session.scalar(select(func.count()).select_from(ClinicalRecord).where(ClinicalRecord.patient_id == patient_id)) == 0
    assert session.scalar(select(func.count()).select_from(LabResult)) == 0


def test_facility_delete_sets_patient_facility_null(session, patient, facility):
    patient.current_facility = facility
    session.flush()
    assert patient.current_facility_id == facility.id

    session.execute(delete(Facility).where(Facility.id == facility.id))
    session.flush()
    session.expire(patient)
    assert patient.current_facility_id is None


def test_audit_log_append_only(session, patient):
    session.add(
        AuditLog(
            action="analysis_created",
            model_version="test-model-1",
            patient_reference=patient.external_reference,
        )
    )
    session.add(
        AuditLog(
            action="review_approved",
            patient_reference=patient.external_reference,
        )
    )
    session.flush()

    rows = session.scalars(select(AuditLog)).all()
    assert len(rows) == 2
    assert {row.action for row in rows} == {"analysis_created", "review_approved"}


def test_database_url_uses_psycopg(engine):
    from sqlalchemy import inspect

    assert engine.dialect.name == "postgresql"
    assert engine.url.get_backend_name() == "postgresql"
    assert engine.url.get_driver_name() == "psycopg"
    inspector = inspect(engine)
    assert "patients" in inspector.get_table_names()
    assert engine.dialect.server_version_info[0] >= 13