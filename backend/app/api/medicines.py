"""HTTP API exposing the Phase 14 medicine information/affordability module.

Read-only reference endpoints. Every response carries the geographic scope
(India), currency (INR), and the standard safety message. The compare endpoint
groups medicines by generic ingredient before any price comparison and never
recommends a product.
"""

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.medicine import (
    MedicineCompareRead,
    MedicineDetailRead,
    MedicineListRead,
    MedicineRead,
    MedicineSummaryRead,
)
from app.services import medicines as service

router = APIRouter(prefix="/medicines", tags=["medicines"])

_NOT_FOUND_DETAIL = "Medicine not found"


@router.get("", response_model=MedicineListRead)
def list_medicines() -> MedicineListRead:
    """List all curated medicines with their reported prices."""
    payload = service.build_list_response()
    payload["medicines"] = [
        MedicineSummaryRead(**item) for item in payload["medicines"]
    ]
    return MedicineListRead(**payload)


@router.get("/compare", response_model=MedicineCompareRead)
def compare_medicines(
    generic: str | None = Query(default=None, max_length=128),
    therapeutic_class: str | None = Query(default=None, max_length=128),
) -> MedicineCompareRead:
    """Compare reported prices within clinically equivalent groups.

    Medicines are grouped by generic ingredient, strength and form before any
    comparison; prices from different sources are shown together, unresolved.
    Ranking reflects the reported price only and is not a clinical preference.
    """
    payload = service.build_compare_response(generic, therapeutic_class)
    for group in payload["groups"]:
        group["medicines"] = [MedicineRead(**item) for item in group["medicines"]]
    return MedicineCompareRead(**payload)


@router.get("/{medicine_id}", response_model=MedicineDetailRead)
def get_medicine(medicine_id: str) -> MedicineDetailRead:
    """Return one medicine's full record, including every reported price."""
    payload = service.build_detail_response(medicine_id)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND_DETAIL
        )
    payload["medicine"] = MedicineRead(**payload["medicine"])
    return MedicineDetailRead(**payload)