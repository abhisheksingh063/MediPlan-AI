"""Seed development/reference data into the MediPlan AI PostgreSQL database.

The script inserts only synthetic/test patient data and small, clearly-labelled
curated reference records (facilities, services, medicines, prices). It is
idempotent: re-running it does not duplicate existing demo rows.

Run from the repository root:

    python scripts/seed.py --demo

Data requirements honoured here:
- No real identifiable patient information (project-scope safety boundary #5).
- Medicine prices carry a source and a last-verified date (FR-MED-001).
- Facility service status distinguishes available/unavailable/unknown
  (FR-FAC-002); unknown is used deliberately and is not treated as unavailable.
"""

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models import (  # noqa: E402
    ClinicalRecord,
    Facility,
    FacilityService,
    LabResult,
    Medicine,
    MedicinePrice,
    Patient,
)


def get_or_create(session: Session, model, *, defaults: dict, **filters) -> tuple:
    """Return the existing row matching ``filters``, or create it.

    Returns ``(instance, created: bool)``. Created rows are flushed (not
    committed) so callers can commit the whole seed as one transaction.
    """
    instance = session.scalar(select(model).filter_by(**filters))
    if instance is not None:
        return instance, False
    instance = model(**filters, **defaults)
    session.add(instance)
    session.flush()
    return instance, True


def seed_demo_data(session: Session) -> dict:
    """Insert minimal synthetic/reference demo data. Returns a status summary."""
    counts: dict = {}

    phc, created = get_or_create(
        session,
        Facility,
        defaults={"facility_type": "phc", "district": "Synthetic District", "state": "Demo"},
        name="Synthetic District PHC",
    )
    counts["facility_phc"] = "created" if created else "existing"

    chc, created = get_or_create(
        session,
        Facility,
        defaults={"facility_type": "chc", "district": "Synthetic District", "state": "Demo"},
        name="Synthetic District CHC",
    )
    counts["facility_chc"] = "created" if created else "existing"

    district_hospital, created = get_or_create(
        session,
        Facility,
        defaults={
            "facility_type": "district_hospital",
            "district": "Synthetic District",
            "state": "Demo",
        },
        name="Synthetic District Hospital",
    )
    counts["facility_district_hospital"] = "created" if created else "existing"

    def seed_service(facility, service_name, status) -> bool:
        _, was_created = get_or_create(
            session,
            FacilityService,
            defaults={"availability_status": status},
            facility_id=facility.id,
            service_name=service_name,
        )
        return was_created

    counts["facility_services_created"] = sum(
        [
            seed_service(phc, "HbA1c test", "available"),
            seed_service(phc, "ECG", "unknown"),
            seed_service(chc, "HbA1c test", "available"),
            seed_service(chc, "X-ray", "available"),
            seed_service(district_hospital, "Cardiology consultation", "available"),
        ]
    )

    metformin_ja, created = get_or_create(
        session,
        Medicine,
        defaults={},
        generic_name="Metformin",
        brand_name=None,
        strength="500 mg",
        form="tablet",
        pack_size="20",
    )
    counts["medicine_metformin_jan_aushadhi"] = "created" if created else "existing"

    metformin_brand, created = get_or_create(
        session,
        Medicine,
        defaults={},
        generic_name="Metformin",
        brand_name="Example Brand",
        strength="500 mg",
        form="tablet",
        pack_size="20",
    )
    counts["medicine_metformin_brand"] = "created" if created else "existing"

    _, created = get_or_create(
        session,
        MedicinePrice,
        defaults={
            "source_url": "https://janaushadhi.gov.in/productportfolio/ProductmrpList",
            "price": 12.00,
            "currency": "INR",
            "jan_aushadhi_status": "jan_aushadhi",
        },
        medicine_id=metformin_ja.id,
        source="Jan Aushadhi product list (reference)",
    )
    counts["price_metformin_jan_aushadhi"] = "created" if created else "existing"

    _, created = get_or_create(
        session,
        MedicinePrice,
        defaults={
            "source_url": None,
            "price": 47.50,
            "currency": "INR",
            "jan_aushadhi_status": "brand",
        },
        medicine_id=metformin_brand.id,
        source="NPPA reference (example)",
    )
    counts["price_metformin_brand"] = "created" if created else "existing"

    patient, created = get_or_create(
        session,
        Patient,
        defaults={
            "age": 54,
            "sex": "F",
            "height": 160.0,
            "weight": 72.0,
            "current_facility_id": phc.id,
        },
        external_reference="SYN-DEMO-001",
    )
    counts["patient"] = "created" if created else "existing"

    clinical_record, created = get_or_create(
        session,
        ClinicalRecord,
        defaults={
            "history_text": "SYNTHETIC DEMO HISTORY - not a real patient record.",
            "allergies": "None recorded (synthetic demo data).",
            "current_medications": "Metformin 500 mg (synthetic demo context).",
            "previous_treatments": "Diet and lifestyle (synthetic demo context).",
        },
        patient_id=patient.id,
        condition="Type 2 Diabetes",
    )
    counts["clinical_record"] = "created" if created else "existing"

    _, created = get_or_create(
        session,
        LabResult,
        defaults={
            "value": 7.2,
            "unit": "%",
            "reference_range": "Example reference only; not authoritative.",
        },
        clinical_record_id=clinical_record.id,
        test_name="HbA1c",
    )
    counts["lab_result"] = "created" if created else "existing"

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Insert the minimal synthetic/demo seed data.",
    )
    args = parser.parse_args()

    if not args.demo:
        parser.print_help()
        return 0

    engine = create_engine(settings.resolved_database_url)
    with Session(engine) as session:
        counts = seed_demo_data(session)
        session.commit()
        print("Seeded SYNTHETIC/DEMO data. Status per item ('created'/'existing'):")
        for key, value in counts.items():
            print(f"  {key}: {value}")

    print("\nAll records are synthetic/demo or labelled public reference data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())