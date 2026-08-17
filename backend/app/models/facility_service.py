"""Facility service model.

A facility-specific service/test availability. Status is one of
``available``, ``unavailable``, or ``unknown``; ``unknown`` must never be
treated as ``unavailable`` (FR-FAC-002).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class FacilityService(Base):
    """Availability of one service/test at one named facility."""

    __tablename__ = "facility_services"
    __table_args__ = (
        UniqueConstraint(
            "facility_id", "service_name", name="uq_facility_services_service"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(
        ForeignKey("facilities.id", ondelete="CASCADE"), index=True
    )
    service_name: Mapped[str] = mapped_column(String(256))
    availability_status: Mapped[str] = mapped_column(String(16), default="unknown")

    facility: Mapped["Facility"] = relationship(back_populates="facility_services")

    def __repr__(self) -> str:
        return (
            f"<FacilityService id={self.id} facility_id={self.facility_id} "
            f"service={self.service_name!r}>"
        )