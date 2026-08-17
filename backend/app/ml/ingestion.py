"""Raw-data loading, validation and target derivation for the Phaase 7 dataset.

Reads the preserved UCI ``diabetic_data.csv`` exactly as released (no in-place
changes), treats only ``?`` as missing, and derives the Phase 2 target
``early_readmission`` from ``readmitted``.
"""

from __future__ import annotations

import pandas as pd

from app.ml.config import (
    EARLY_VALUE,
    FEATURES,
    ID_COLUMNS,
    NA_VALUES,
    RAW_DATA_FILE,
    TARGET_COLUMN,
    TARGET_DERIVED,
)

DTYPE_SPEC = {
    "encounter_id": "int64",
    "patient_nbr": "int64",
    "race": "str",
    "gender": "str",
    "age": "str",
    "admission_type_id": "str",
    "admission_source_id": "str",
    "discharge_disposition_id": "str",
    "max_glu_serum": "str",
    "A1Cresult": "str",
    "diabetesMed": "str",
    "change": "str",
    "time_in_hospital": "int64",
    "num_lab_procedures": "int64",
    "num_procedures": "int64",
    "num_medications": "int64",
    "number_outpatient": "int64",
    "number_emergency": "int64",
    "number_inpatient": "int64",
    "number_diagnoses": "int64",
    "readmitted": "str",
}

MODEL_COLUMNS = ID_COLUMNS + FEATURES + [TARGET_COLUMN]

REQUIRED_RAW_COLUMNS = set(DTYPE_SPEC)
VALID_READMITTED = {"NO", "<30", ">30"}


class RawDataError(ValueError):
    """Raised when the raw dataset does not match the documented release."""


def load_raw_data(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Load the raw release and return the encounter-level model frame.

    Only the columns needed for modelling (identifiers, selected Phase 2
    features and the target) are read; ``None`` remains a string category and
    only ``?`` becomes a missing value. The source file is never modified.
    """
    if frame is None:
        if not RAW_DATA_FILE.exists():
            raise RawDataError(
                f"Raw dataset not found at {RAW_DATA_FILE}. "
                "Run:  python scripts/prepare_dataset.py --download"
            )
        frame = pd.read_csv(
            RAW_DATA_FILE,
            dtype=DTYPE_SPEC,
            usecols=lambda column: column in REQUIRED_RAW_COLUMNS,
            na_values=NA_VALUES,
            keep_default_na=False,
        )
    else:
        missing = REQUIRED_RAW_COLUMNS - set(frame.columns)
        if missing:
            raise RawDataError(f"Missing required columns: {sorted(missing)}")

    frame = frame.copy()
    validate_raw_data(frame)
    return frame


def validate_raw_data(frame: pd.DataFrame) -> None:
    """Validate the release invariants before any cleaning or modelling."""
    if frame[ID_COLUMNS[0]].duplicated().any():
        raise RawDataError("encounter_id is not unique in the raw release.")
    if frame.duplicated().any():
        raise RawDataError("Duplicate full rows found in the raw release.")
    invalid_target = set(frame[TARGET_COLUMN].dropna().unique()) - VALID_READMITTED
    if invalid_target:
        raise RawDataError(
            f"Unexpected target values: {sorted(invalid_target)}"
        )


def derive_target(frame: pd.DataFrame) -> pd.DataFrame:
    """Add ``early_readmission`` (1 when ``readmitted == <30``, else 0)."""
    out = frame.copy()
    out[TARGET_DERIVED] = (
        out[TARGET_COLUMN].map(lambda value: int(value == EARLY_VALUE)).astype("int8")
    )
    if out[TARGET_DERIVED].isna().any():
        raise RawDataError("Target could not be fully derived; missing rows found.")
    return out


def profile_frame(frame: pd.DataFrame) -> dict:
    """Compute the profiling/summary statistics used by the report and metadata."""
    rows = len(frame)
    features_with_missing = (
        frame[FEATURES].isna().sum()[frame[FEATURES].isna().sum() > 0].to_dict()
    )
    target_counts = frame[TARGET_COLUMN].value_counts().sort_index().to_dict()
    early = int((frame[TARGET_DERIVED] == 1).sum())
    return {
        "row_count": rows,
        "column_count": len(frame.columns),
        "unique_patients": int(frame["patient_nbr"].nunique()),
        "repeated_patient_encounters": int(
            (frame["patient_nbr"].duplicated(keep=False)).sum()
        ),
        "target_distribution": target_counts,
        "early_readmission_count": early,
        "early_readmission_rate": round(early / rows, 6),
        "missing_by_feature": {
            key: int(value) for key, value in features_with_missing.items()
        },
    }