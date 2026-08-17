"""Medicine model.

A product-level medicine entry. Prices are provenance- and date-verified and
therefore live in a separate MedicinePrice table.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Medicine(Base):
    """A medicine product described by generic name and optional brand context."""

    __tablename__ = "medicines"
    __table_args__ = (
        UniqueConstraint(
            "generic_name",
            "brand_name",
            "strength",
            "form",
            "pack_size",
            name="uq_medicines_product",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generic_name: Mapped[str] = mapped_column(String(256))
    brand_name: Mapped[str | None] = mapped_column(String(256))
    strength: Mapped[str | None] = mapped_column(String(64))
    form: Mapped[str | None] = mapped_column(String(64))
    pack_size: Mapped[str | None] = mapped_column(String(64))

    prices: Mapped[list["MedicinePrice"]] = relationship(
        back_populates="medicine",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Medicine id={self.id} generic={self.generic_name!r}>"