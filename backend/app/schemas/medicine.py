"""Pydantic schemas for the Phase 14 medicine information/affordability module.

Curated, source-verified reference data only. The module is read-only and
never produces a prescription, dosage, or treatment recommendation.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PriceAvailability = Literal["jan_aushadhi", "brand", "unknown"]


class MedicinePriceRead(BaseModel):
    """One reported price from one cited source for one medicine."""

    model_config = ConfigDict(from_attributes=True)

    price: float | None
    price_unit: str
    unit_price: float | None
    source: str
    source_url: str | None
    source_date: date
    retrieved_date: date
    availability: PriceAvailability
    stale: bool
    geographic_scope: str
    currency: str
    notes: str | None = None


class MedicineRead(BaseModel):
    """Full medicine record including all its separately-reported prices."""

    medicine_id: str
    generic_name: str
    brand_name: str | None
    strength: str
    form: str
    pack_size: str
    therapeutic_class: str
    manufacturer: str | None
    geographic_scope: str
    currency: str
    has_price: bool
    lowest_reported_price: float | None
    lowest_reported_unit_price: float | None
    lowest_price_source: str | None
    lowest_price_source_date: date | None
    stale_available: bool
    prices: list[MedicinePriceRead]


class MedicineSummaryRead(BaseModel):
    """Compact medicine record for list responses."""

    medicine_id: str
    generic_name: str
    brand_name: str | None
    strength: str
    form: str
    pack_size: str
    therapeutic_class: str
    manufacturer: str | None
    geographic_scope: str
    currency: str
    has_price: bool
    lowest_reported_price: float | None
    lowest_reported_unit_price: float | None
    lowest_price_source: str | None
    lowest_price_source_date: date | None
    stale_available: bool


class MedicineListRead(BaseModel):
    """List response envelope; scope, currency and safety travel with it."""

    geographic_scope: str
    currency: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    count: int
    medicines: list[MedicineSummaryRead]


class MedicineDetailRead(BaseModel):
    """Detail response envelope."""

    geographic_scope: str
    currency: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    medicine: MedicineRead


class ComparisonGroupRead(BaseModel):
    """A group of clinically equivalent medicines compared by price only."""

    group_key: str
    generic_name: str
    strength: str
    form: str
    medicines: list[MedicineRead]


class MedicineCompareRead(BaseModel):
    """Comparison response envelope; groups are price-ranked, not choice-ranked."""

    geographic_scope: str
    currency: str
    as_of_date: date
    staleness_rule_days: int
    safety_message: str
    scope_note: str
    comparison_note: str
    group_count: int
    groups: list[ComparisonGroupRead]


class MedicineNotFoundError(BaseModel):
    """Controlled 404 body; carries no patient or pricing detail."""

    detail: str
    generated_at: datetime | None = None