"""Medicine price model.

Prices are reference MRP values (never stock availability) with explicit
provenance and verification date, as required by FR-MED-001 and NFR-DATA-001.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MedicinePrice(Base):
    """A verified reference price for one medicine product from one source."""

    __tablename__ = "medicine_prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    medicine_id: Mapped[int] = mapped_column(
        ForeignKey("medicines.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(
        String(3), default="INR", server_default="INR"
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    jan_aushadhi_status: Mapped[str | None] = mapped_column(String(32))

    medicine: Mapped["Medicine"] = relationship(back_populates="prices")

    def __repr__(self) -> str:
        return f"<MedicinePrice id={self.id} medicine_id={self.medicine_id}>"