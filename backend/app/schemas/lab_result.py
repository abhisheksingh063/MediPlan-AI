"""Pydantic schemas for laboratory results."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LabResultCreate(BaseModel):
    """Input for creating a lab result on a clinical record."""

    test_name: str = Field(min_length=1, max_length=128)
    value: float
    unit: str | None = Field(default=None, max_length=32)
    reference_range: str | None = Field(default=None, max_length=256)
    recorded_at: datetime | None = None


class LabResultRead(BaseModel):
    """Read-only representation of a lab result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    clinical_record_id: int
    test_name: str
    value: float
    unit: str | None = None
    reference_range: str | None = None
    recorded_at: datetime