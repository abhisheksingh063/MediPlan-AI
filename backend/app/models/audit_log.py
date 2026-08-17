"""Audit log model.

Append-only record of analysis and clinician-review activity (FR-AUD-001).
Stores references rather than sensitive clinical payloads (FR-AUD-002).
``patient_reference`` is deliberately a plain string, not a foreign key, so the
audit trail remains readable and stable if patient rows are later removed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """One attributable analysis or review event."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_patient_reference_created_at", "patient_reference", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(64))
    patient_reference: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r}>"