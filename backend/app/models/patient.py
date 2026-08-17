"""Patient model.

Stores synthetic patient demographic context only. Clinical detail lives in
ClinicalRecord; facility linkage is optional and reference-only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Patient(Base):
    """A synthetic patient record for the clinician-review workflow."""

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_reference: Mapped[str] = mapped_column(String(32), unique=True)
    age: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str | None] = mapped_column(String(16))
    height: Mapped[float | None] = mapped_column(Numeric(6, 2))
    weight: Mapped[float | None] = mapped_column(Numeric(6, 2))
    current_facility_id: Mapped[int | None] = mapped_column(
        ForeignKey("facilities.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    clinical_records: Mapped[list["ClinicalRecord"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    predictions: Mapped[list["TreatmentPrediction"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    referrals: Mapped[list["Referral"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    current_facility: Mapped["Facility | None"] = relationship(
        back_populates="patients"
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} reference={self.external_reference!r}>"