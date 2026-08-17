"""Persistence models.

Importing this package registers every model on the shared ``Base.metadata``,
which is required for Alembic autogeneration and ``create_all`` in tests.
"""

from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.clinical_record import ClinicalRecord
from app.models.facility import Facility
from app.models.facility_service import FacilityService
from app.models.lab_result import LabResult
from app.models.medicine import Medicine
from app.models.medicine_price import MedicinePrice
from app.models.patient import Patient
from app.models.referral import Referral
from app.models.treatment_prediction import TreatmentPrediction

__all__ = [
    "AuditLog",
    "Base",
    "ClinicalRecord",
    "Facility",
    "FacilityService",
    "LabResult",
    "Medicine",
    "MedicinePrice",
    "Patient",
    "Referral",
    "TreatmentPrediction",
]