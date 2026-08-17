"""Lab result model.

A single laboratory measurement. Reference ranges are stored as free text and
are never used as hard-coded rules in the database layer.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LabResult(Base):
    """A laboratory measurement associated with a clinical record."""

    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clinical_record_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_records.id", ondelete="CASCADE"), index=True
    )
    test_name: Mapped[str] = mapped_column(String(128))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    reference_range: Mapped[str | None] = mapped_column(String(256))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    clinical_record: Mapped["ClinicalRecord"] = relationship(
        back_populates="lab_results"
    )

    def __repr__(self) -> str:
        return f"<LabResult id={self.id} test={self.test_name!r}>"