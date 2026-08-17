"""Phase 7 data-preparation orchestrator.

Pipeline stages (in order):

1. load raw release (read-only) and validate invariants
2. derive the Phase 2 target ``early_readmission``
3. profile rows, missingness, duplicates and target distribution
4. grouped train/validation/test split by patient number
5. fit preprocessing on the training split ONLY
6. apply the fitted pipeline to train/validation/test
7. write processed CSVs, the fitted pipeline and dataset metadata

The pipeline is reproducible: a fixed seed, a fixed feature list/order and
train-only fitted transformations. Re-running ``prepare_dataset`` overwrites
``data/processed`` but never touches ``data/raw``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Callable

import pandas as pd

from app.ml import ingestion, preprocessing, split
from app.ml.config import (
    ACQUISITION_DATE,
    AGE_ORDER,
    DATASET_CITATION,
    DATASET_DOI,
    DATASET_DOWNLOAD_URL,
    DATASET_INTRO_PUBLICATION,
    DATASET_LICENSE,
    DATASET_NAME,
    DATASET_PUBLISHER,
    DATASET_URL,
    EXCLUDED_FEATURES,
    FEATURES,
    ID_COLUMNS,
    METADATA_FILE,
    PREPROCESSING_VERSION,
    PROCESSED_DATA_DIR,
    RANDOM_SEED,
    RAW_ARCHIVE_FILE,
    RAW_CSV_SHA256,
    RAW_DATA_FILE,
    RAW_IDS_MAPPING_FILE,
    SPLIT_FILES,
    TARGET_COLUMN,
    TARGET_DERIVED,
)

SPLIT_LABELS = {"train": "train", "validation": "validation", "test": "test"}


def _split_inventory(split_name: str, frame: pd.DataFrame) -> dict:
    early = int((frame[TARGET_DERIVED] == 1).sum())
    return {
        "name": split_name,
        "rows": int(len(frame)),
        "unique_patients": int(frame["patient_nbr"].nunique()),
        "early_readmission_rows": early,
        "early_readmission_rate": round(early / len(frame), 6),
    }


def _file_sha256(path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def _atomic_write(path, writer: Callable[[Path], None]) -> None:
    """Write via a temp file and atomically replace the target.

    On Windows, files in synced folders (OneDrive) can be transiently locked;
    an atomic replace avoids partial writes and retries on lock contention.
    """
    temp = path.with_name(f".{path.name}.tmp")
    try:
        writer(temp)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def prepare_dataset(
    *,
    force: bool = False,
    seed: int = RANDOM_SEED,
    strategy: Callable[..., tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] | None = None,
) -> dict:
    """Run the full data-preparation pipeline and return a summary dict."""
    if not force:
        for path in [RAW_DATA_FILE, RAW_IDS_MAPPING_FILE]:
            if not path.exists():
                raise FileNotFoundError(
                    f"Raw dataset missing: {path}. "
                    "Run:  python scripts/prepare_dataset.py --download"
                )

    raw = ingestion.load_raw_data()
    frame = ingestion.derive_target(raw)
    profile = ingestion.profile_frame(frame)

    splitter = strategy or split.grouped_train_valid_test_split
    train, validation, test = splitter(frame, seed=seed)

    feature_columns = [feature for feature in FEATURES if feature in frame.columns]
    preprocessor = preprocessing.fit_preprocessor(train[feature_columns])

    train_encoded = preprocessing.apply_preprocessor(preprocessor, train[feature_columns])
    validation_encoded = preprocessing.apply_preprocessor(
        preprocessor, validation[feature_columns]
    )
    test_encoded = preprocessing.apply_preprocessor(preprocessor, test[feature_columns])

    feature_order = list(preprocessor.get_feature_names_out())

    def _write(split_name: str, encoded: pd.DataFrame, source: pd.DataFrame) -> None:
        out = pd.concat(
            [
                source[ID_COLUMNS].reset_index(drop=True),
                encoded.reset_index(drop=True),
                source[[TARGET_DERIVED]].reset_index(drop=True),
            ],
            axis=1,
        )

        def _dump(target: Path) -> None:
            out.to_csv(target, index=False)

        _atomic_write(SPLIT_FILES[split_name], _dump)

    _write("train", train_encoded, train)
    _write("validation", validation_encoded, validation)
    _write("test", test_encoded, test)

    preprocessing.save_preprocessor(preprocessor)

    for encoded in (train_encoded, validation_encoded, test_encoded):
        if encoded.isna().any().any():
            raise ValueError("Encoded split contains unexpected missing values.")

    if train_encoded.shape[1] != len(feature_order):
        raise ValueError("Encoded train feature width does not match feature order.")

    metadata = _build_metadata(
        profile=profile,
        feature_order=feature_order,
        splits={
            "train": _split_inventory("train", train),
            "validation": _split_inventory("validation", validation),
            "test": _split_inventory("test", test),
        },
        seed=seed,
    )
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _write_metadata(target: Path) -> None:
        target.write_text(
            json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
        )

    _atomic_write(METADATA_FILE, _write_metadata)

    return {
        "profile": profile,
        "feature_order": feature_order,
        "encoded_feature_count": len(feature_order),
        "splits": metadata["splits"],
        "metadata_written": str(METADATA_FILE),
    }


def _build_metadata(
    *,
    profile: dict,
    feature_order: list[str],
    splits: dict,
    seed: int,
) -> dict:
    return {
        "dataset": {
            "name": DATASET_NAME,
            "publisher": DATASET_PUBLISHER,
            "source_url": DATASET_URL,
            "download_url": DATASET_DOWNLOAD_URL,
            "doi": DATASET_DOI,
            "license": DATASET_LICENSE,
            "citation": DATASET_CITATION,
            "introductory_publication": DATASET_INTRO_PUBLICATION,
            "acquisition_date": ACQUISITION_DATE,
            "raw_file": str(RAW_DATA_FILE),
            "raw_archive_sha256": _file_sha256(RAW_ARCHIVE_FILE),
            "raw_csv_sha256": _file_sha256(RAW_DATA_FILE),
            "expected_raw_csv_sha256": RAW_CSV_SHA256,
        },
        "preprocessing": {
            "version": PREPROCESSING_VERSION,
            "random_seed": seed,
            "split_strategy": (
                "grouped by patient_nbr (two-stage GroupShuffleSplit); "
                "ordered train/validation/test"
            ),
            "target": TARGET_DERIVED,
            "source_target_column": TARGET_COLUMN,
            "early_readmission_definition": "readmitted == '<30'",
            "missing_value_sentinel": ["?"],
            "imputation": {
                "numeric": "median (fitted on train only)",
                "nominal": "most_frequent (fitted on train only)",
                "race": "constant 'Unknown' (fitted on train only)",
                "ordinal": "most_frequent (fitted on train only)",
            },
            "scaling": "StandardScaler on numeric features (fitted on train only)",
            "encoding": {
                "nominal": "one-hot (handle_unknown='ignore')",
                "ordinal": f"ordinal encoding for age bins {AGE_ORDER}",
            },
        },
        "data": {
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
            "unique_patients": profile["unique_patients"],
            "repeated_patient_encounters": profile["repeated_patient_encounters"],
            "target_distribution_raw": profile["target_distribution"],
            "early_readmission_count": profile["early_readmission_count"],
            "early_readmission_rate": profile["early_readmission_rate"],
            "missing_by_feature": profile["missing_by_feature"],
            "duplicate_rows": 0,
        },
        "selected_features": FEATURES,
        "encoded_feature_order": feature_order,
        "encoded_feature_count": len(feature_order),
        "excluded_features": EXCLUDED_FEATURES,
        "splits": splits,
        "known_limitations": [
            "Cohort is diabetes-coded US hospital encounters (1999-2008); "
            "it is NOT a clinically validated Type 2-only cohort. Research gate "
            "(requirements.md) requires clinical review of ICD-9 code mapping "
            "before any Type 2-specific claim; the pipeline intentionally does "
            "not apply an unvalidated Type 2 filter.",
            "age is binned, not exact.",
            "coarse glucose categories (max_glu_serum, A1Cresult) and large "
            "'test not performed' (None) share.",
            "Dataset provides no treatment-response evidence; no causality claims.",
        ],
        "generated_at": date.today().isoformat(),
    }


if __name__ == "__main__":  # pragma: no cover
    summary = prepare_dataset(force=True)
    print(json.dumps(summary, indent=2, sort_keys=True))