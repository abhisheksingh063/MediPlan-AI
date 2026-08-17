"""Read-only facility reference API.

A minimal facility lookup so patient creation can reference a current facility.
This is reference data only; facility capability/referral intelligence is a
later phase.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Facility
from app.schemas.facility import FacilityRead

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityRead])
def list_facilities(db: Session = Depends(get_db)) -> list[FacilityRead]:
    """List known facilities ordered by name."""
    rows = db.scalars(select(Facility).order_by(Facility.name)).all()
    return [FacilityRead.model_validate(f) for f in rows]