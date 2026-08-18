"""Medicine information and affordability comparison service (Phase 14).

Serves curated, source-verified medicine and price reference data loaded from
``app/medicines/medicines.json``. The module answers "what medicine
information and pricing exists" and never "what should this patient receive":
it is deliberately isolated from ``app.services.inference``,
``app.services.explainability``, and ``app.services.treatment_support``.

Geographic scope (India) and currency (INR) are carried declaratively on every
record and every response. This scope is independent of the origin of the
clinical dataset used to train the ML model (UCI Diabetes 130-US Hospitals).
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from json import load
from pathlib import Path

SAFETY_MESSAGE = (
    "Medicine information and affordability comparison only. This does not "
    "constitute a prescription or treatment recommendation."
)

SCOPE_NOTE = (
    "Pricing scope is India (INR) and is independent of the origin of the "
    "clinical dataset (UCI Diabetes 130-US Hospitals) used for the ML model; "
    "this system does not claim the priced medicines apply specifically to the "
    "US hospital population."
)

COMPARISON_NOTE = (
    "Prices are reported exactly as published by each cited source and are "
    "shown together without the system resolving them. Medicines are compared "
    "only within a group of otherwise clinically equivalent options (same "
    "generic ingredient, strength and form). Ranking is by reported price "
    "only and implies nothing about clinical suitability; resolving any "
    "price conflict or choosing a product requires clinician judgment."
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "medicines"


class MedicineDataError(Exception):
    """Base error for medicine reference-data failures."""


class MedicineDataUnavailableError(MedicineDataError):
    """Raised when the medicine reference data cannot be loaded."""


@lru_cache(maxsize=1)
def _load_medicine_data() -> dict:
    try:
        with (_DATA_DIR / "medicines.json").open(encoding="utf-8") as handle:
            return load(handle)
    except (OSError, ValueError) as exc:
        raise MedicineDataUnavailableError(
            "Medicine reference data unavailable."
        ) from exc


def clear_medicine_cache() -> None:
    """Drop cached medicine data so tests can reload updated data files."""
    _load_medicine_data.cache_clear()


def all_medicines() -> list[dict]:
    return _load_medicine_data().get("medicines", [])


def as_of_date() -> date:
    return date.fromisoformat(_load_medicine_data()["as_of_date"])


def staleness_rule_days() -> int:
    return int(_load_medicine_data()["staleness_rule_days"])


def scope_fields() -> dict[str, str]:
    data = _load_medicine_data()
    return {
        "geographic_scope": data["geographic_scope"],
        "currency": data["currency"],
    }


def _enrich_price(price: dict, cutoff: date, medicine: dict) -> dict:
    enriched = dict(price)
    enriched["geographic_scope"] = medicine.get("geographic_scope")
    enriched["currency"] = medicine.get("currency")
    base_date = price.get("source_date")
    if base_date:
        try:
            stale = cutoff - date.fromisoformat(base_date) > timedelta(
                days=staleness_rule_days()
            )
        except ValueError:
            stale = False
    else:
        stale = False
    enriched["stale"] = stale
    return enriched


def get_medicine(medicine_id: str) -> dict | None:
    """Return a single medicine with enriched price records, or None."""
    for medicine in all_medicines():
        if medicine["medicine_id"] == medicine_id:
            cutoff = as_of_date()
            medicine = dict(medicine)
            medicine["prices"] = [
                _enrich_price(price, cutoff, medicine)
                for price in medicine["prices"]
            ]
            _aggregate_price_fields(medicine)
            return medicine
    return None


def list_medicines() -> list[dict]:
    """Return all medicines with enriched prices and aggregate price fields."""
    cutoff = as_of_date()
    result = []
    for medicine in all_medicines():
        medicine = dict(medicine)
        medicine["prices"] = [
            _enrich_price(price, cutoff, medicine) for price in medicine["prices"]
        ]
        _aggregate_price_fields(medicine)
        result.append(medicine)
    return result


def group_key(medicine: dict) -> str:
    """Comparability key: same generic + strength + form."""
    return (
        f"{medicine['generic_name']} {medicine['strength']} "
        f"{medicine['form']}".lower()
    )


def _unit_price(price: dict, pack_size_units: int) -> float | None:
    if price.get("price") is None:
        return None
    try:
        units = int(pack_size_units or 0)
    except (TypeError, ValueError):
        units = 0
    if units <= 0:
        return None
    return round(float(price["price"]) / units, 2)


def _aggregate_price_fields(medicine: dict) -> None:
    """Fill price-per-unit, lowest reported price, and availability summary."""
    valid = []
    for index, price in enumerate(medicine["prices"]):
        unit = _unit_price(price, medicine.get("pack_size_units"))
        medicine["prices"][index]["unit_price"] = unit
        if price.get("price") is not None and unit is not None:
            valid.append((unit, index, price))
    if valid:
        valid.sort(key=lambda item: item[0])
        lowest = valid[0][2]
        medicine["has_price"] = True
        medicine["lowest_reported_price"] = lowest["price"]
        medicine["lowest_reported_unit_price"] = valid[0][0]
        medicine["lowest_price_source"] = lowest["source"]
        medicine["lowest_price_source_date"] = lowest["source_date"]
    else:
        medicine["has_price"] = False
        medicine["lowest_reported_price"] = None
        medicine["lowest_reported_unit_price"] = None
        medicine["lowest_price_source"] = None
        medicine["lowest_price_source_date"] = None
    medicine["stale_available"] = any(
        price["stale"] for price in medicine["prices"] if not price.get("price") is None
    )


def _medicine_summary(medicine: dict) -> dict:
    fields = {
        "medicine_id",
        "generic_name",
        "brand_name",
        "strength",
        "form",
        "pack_size",
        "therapeutic_class",
        "manufacturer",
        "geographic_scope",
        "currency",
        "has_price",
        "lowest_reported_price",
        "lowest_reported_unit_price",
        "lowest_price_source",
        "lowest_price_source_date",
        "stale_available",
    }
    return {field: medicine.get(field) for field in fields}


def build_list_response() -> dict:
    scope = scope_fields()
    medicines = list_medicines()
    return {
        **scope,
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "count": len(medicines),
        "medicines": [_medicine_summary(medicine) for medicine in medicines],
    }


def build_detail_response(medicine_id: str) -> dict | None:
    medicine = get_medicine(medicine_id)
    if medicine is None:
        return None
    scope = scope_fields()
    return {
        **scope,
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "medicine": medicine,
    }


def group_medicines_for_compare(
    generic: str | None = None, therapeutic_class: str | None = None
) -> list[dict]:
    """Group medicines by comparability key and build compare structures.

    Medicines are grouped before any price comparison; a flat list mixing
    unrelated medicines by price is never produced. Within a group, items are
    ordered with the lowest reported unit price first and price-unavailable
    items last. Prices from different sources are kept separate, unresolved.
    """
    drugs = list_medicines()
    if generic:
        needle = generic.strip().lower()
        drugs = [
            m
            for m in drugs
            if needle in m["generic_name"].lower()
            or needle in group_key(m)
        ]
    if therapeutic_class:
        needle = therapeutic_class.strip().lower()
        drugs = [
            m
            for m in drugs
            if needle in (m.get("therapeutic_class") or "").lower()
        ]

    buckets: dict[str, list[dict]] = {}
    for medicine in drugs:
        buckets.setdefault(group_key(medicine), []).append(medicine)

    groups = []
    for key in sorted(buckets):
        items = buckets[key]
        items.sort(
            key=lambda m: (
                m.get("lowest_reported_unit_price") is None,
                m.get("lowest_reported_unit_price") or float("inf"),
                (m.get("brand_name") or "").lower(),
            )
        )
        groups.append(
            {
                "group_key": key,
                "generic_name": items[0]["generic_name"],
                "strength": items[0]["strength"],
                "form": items[0]["form"],
                "medicines": items,
            }
        )
    return groups


def build_compare_response(
    generic: str | None = None, therapeutic_class: str | None = None
) -> dict:
    groups = group_medicines_for_compare(generic, therapeutic_class)
    scope = scope_fields()
    return {
        **scope,
        "as_of_date": as_of_date(),
        "staleness_rule_days": staleness_rule_days(),
        "safety_message": SAFETY_MESSAGE,
        "scope_note": SCOPE_NOTE,
        "comparison_note": COMPARISON_NOTE,
        "group_count": len(groups),
        "groups": groups,
    }