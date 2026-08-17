"""Facility model.

A named healthcare facility. The level is stored as a plain string so the
PHC/CHC/District Hospital hierarchy is supported without hard-coding
capabilities into the model (see FR-FAC-001 and the research decision to keep
service status facility-specific).
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Facility(Base):
    """A named public or reference healthcare facility."""

    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    facility_type: Mapped[str] = mapped_column(String(64))
    district: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(128))

    patients: Mapped[list["Patient"]] = relationship(
        back_populates="current_facility"
    )
    facility_services: Mapped[list["FacilityService"]] = relationship(
        back_populates="facility",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    referrals_from: Mapped[list["Referral"]] = relationship(
        back_populates="current_facility"
    )

    def __repr__(self) -> str:
        return f"<Facility id={self.id} name={self.name!r}>"