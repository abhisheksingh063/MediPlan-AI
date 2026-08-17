"""Clinical record model.

A clinician-entered snapshot of a patient's clinical context at a point in
time. Measurements are captured separately as LabResult rows.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ClinicalRecord(Base):
    """A dated clinical snapshot belonging to a single patient."""

    __tablename__ = "clinical_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    condition: Mapped[str | None] = mapped_column(String(256))
    history_text: Mapped[str | None] = mapped_column(Text)
    allergies: Mapped[str | None] = mapped_column(Text)
    current_medications: Mapped[str | None] = mapped_column(Text)
    previous_treatments: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(back_populates="clinical_records")
    lab_results: Mapped[list["LabResult"]] = relationship(
        back_populates="clinical_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ClinicalRecord id={self.id} patient_id={self.patient_id}>"