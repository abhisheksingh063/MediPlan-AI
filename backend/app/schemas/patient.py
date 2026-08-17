"""Pydantic schemas for synthetic patient records.

Age/height/weight bounds are data-sanity limits only; they are not clinical
thresholds (which belong to later validation phases). ``sex`` accepts M/F/O to
match the prototype's data model without introducing a database enum.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.facility import FacilityRead

ALLOWED_SEX_VALUES = {"M", "F", "O"}


def _normalise_sex(value: str | None) -> str | None:
    if value is None:
        return None
    normalised = value.strip().upper()
    if normalised not in ALLOWED_SEX_VALUES:
        raise ValueError(f"sex must be one of {sorted(ALLOWED_SEX_VALUES)}")
    return normalised


class PatientCreate(BaseModel):
    """Input for creating a synthetic patient."""

    external_reference: str = Field(min_length=1, max_length=32)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, max_length=16)
    height: float | None = Field(default=None, gt=0, le=300)
    weight: float | None = Field(default=None, gt=0, le=600)
    current_facility_id: int | None = Field(default=None, gt=0)

    _normalise_sex = field_validator("sex")(_normalise_sex)


class PatientUpdate(BaseModel):
    """Input for updating an existing synthetic patient (all fields optional)."""

    external_reference: str | None = Field(default=None, min_length=1, max_length=32)
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = Field(default=None, max_length=16)
    height: float | None = Field(default=None, gt=0, le=300)
    weight: float | None = Field(default=None, gt=0, le=600)
    current_facility_id: int | None = Field(default=None, gt=0)

    _normalise_sex = field_validator("sex")(_normalise_sex)


class PatientRead(BaseModel):
    """Read-only representation of a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_reference: str
    age: int | None = None
    sex: str | None = None
    height: float | None = None
    weight: float | None = None
    current_facility_id: int | None = None
    current_facility: FacilityRead | None = None
    created_at: datetime


class PatientList(BaseModel):
    """List response for patients."""

    items: list[PatientRead]