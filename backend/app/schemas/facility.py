"""Pydantic schemas for facility reference data."""

from pydantic import BaseModel, ConfigDict


class FacilityRead(BaseModel):
    """Read-only representation of a healthcare facility."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    facility_type: str
    district: str | None = None
    state: str | None = None