"""Pydantic schemas for clinical records."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lab_result import LabResultRead


class ClinicalRecordCreate(BaseModel):
    """Input for creating a clinical record for a patient."""

    condition: str | None = Field(default=None, max_length=256)
    history_text: str | None = None
    allergies: str | None = None
    current_medications: str | None = None
    previous_treatments: str | None = None
    recorded_at: datetime | None = None


class ClinicalRecordRead(BaseModel):
    """Read-only representation of a clinical record and its lab results."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    condition: str | None = None
    history_text: str | None = None
    allergies: str | None = None
    current_medications: str | None = None
    previous_treatments: str | None = None
    recorded_at: datetime
    lab_results: list[LabResultRead] = Field(default_factory=list)