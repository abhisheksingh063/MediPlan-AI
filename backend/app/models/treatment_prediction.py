"""Treatment prediction model.

Stores the result of running the versioned ML model for a patient. The Phase 2
ML decision is a conditional 30-day readmission-risk estimate; the schema must
not assume a drug prescription output. ``option_name`` labels the predicted
outcome/option (for example the readmission class), ``score`` holds the
probability, and ``explanation_json`` holds explainability payloads such as
feature contributions.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TreatmentPrediction(Base):
    """One versioned model run and its output for a patient."""

    __tablename__ = "treatment_predictions"
    __table_args__ = (
        Index(
            "ix_treatment_predictions_patient_id_created_at",
            "patient_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE")
    )
    model_version: Mapped[str] = mapped_column(String(64))
    option_name: Mapped[str] = mapped_column(String(128))
    score: Mapped[float] = mapped_column(Float)
    explanation_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(back_populates="predictions")

    def __repr__(self) -> str:
        return f"<TreatmentPrediction id={self.id} option={self.option_name!r}>"