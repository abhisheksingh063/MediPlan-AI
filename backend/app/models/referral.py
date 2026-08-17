"""Referral model.

A clinician-reviewable candidate referral generated when a required service is
unavailable or unconfirmed at the current facility. It is logistics/decision
support, not an automatic referral or a medical directive (FR-REF-001).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Referral(Base):
    """A candidate referral record for clinician review."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    required_service: Mapped[str] = mapped_column(String(256))
    current_facility_id: Mapped[int | None] = mapped_column(
        ForeignKey("facilities.id", ondelete="SET NULL"), index=True
    )
    recommended_facility_level: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(back_populates="referrals")
    current_facility: Mapped["Facility | None"] = relationship(
        back_populates="referrals_from"
    )

    def __repr__(self) -> str:
        return f"<Referral id={self.id} patient_id={self.patient_id}>"