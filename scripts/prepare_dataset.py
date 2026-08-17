"""Acquire and prepare the Phase 7 dataset.

Run from the repository root:

    python scripts/prepare_dataset.py --download
    python scripts/prepare_dataset.py

``--download`` fetches the exact UCI release (Diabetes 130-US Hospitals for
Years 1999-2008), preserves it under ``data/raw/``, verifies documented SHA-256
checksums and writes provenance. The preparation step then profiles and
preprocesses the data into ``data/processed/`` (dataset_metadata.json,
preprocessor.joblib, train/validation/test CSVs) without modifying the raw
release. Model training is deliberately not part of this phase.
"""

import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path
from datetime import date

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.config import (  # noqa: E402
    ACQUISITION_DATE,
    DATASET_CITATION,
    DATASET_DOI,
    DATASET_DOWNLOAD_URL,
    DATASET_LICENSE,
    DATASET_NAME,
    DATASET_PUBLISHER,
    DATASET_URL,
    RAW_ACQUISITION_FILE,
    RAW_ARCHIVE_FILE,
    RAW_ARCHIVE_SHA256,
    RAW_CSV_SHA256,
    RAW_DATA_DIR,
    RAW_DATA_FILE,
    RAW_IDS_MAPPING_FILE,
)
from app.ml.prepare import prepare_dataset  # noqa: E402

EXPECTED_RAW_FILES = {
    RAW_DATA_FILE: RAW_CSV_SHA256,
    RAW_IDS_MAPPING_FILE: None,
}


def sha256_hex(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def download_raw() -> None:
    """Download and verify the exact UCI release under ``data/raw``."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_ARCHIVE_FILE.exists():
        actual = sha256_hex(RAW_ARCHIVE_FILE)
        if actual == RAW_ARCHIVE_SHA256:
            print(f"Archive already present and verified: {RAW_ARCHIVE_FILE.name}")
            extract_raw()
            write_acquisition_record()
            return
        print(
            f"Existing archive checksum mismatch ({actual}); re-downloading."
        )

    temp_archive = RAW_ARCHIVE_FILE.with_suffix(".zip.part")
    print(f"Downloading {DATASET_NAME} from UCI...")
    urllib.request.urlretrieve(DATASET_DOWNLOAD_URL, temp_archive)
    actual = sha256_hex(temp_archive)
    if actual != RAW_ARCHIVE_SHA256:
        temp_archive.unlink(missing_ok=True)
        raise SystemExit(
            f"Downloaded archive checksum mismatch. Expected "
            f"{RAW_ARCHIVE_SHA256}, got {actual}. Aborting to protect data/raw."
        )
    temp_archive.replace(RAW_ARCHIVE_FILE)
    print(f"Downloaded and verified archive ({RAW_ARCHIVE_FILE.name}).")
    extract_raw()
    write_acquisition_record()


def extract_raw() -> None:
    """Extract the protected archive without touching existing raw files."""
    with zipfile.ZipFile(RAW_ARCHIVE_FILE) as archive:
        members = [
            member for member in archive.namelist() if member.endswith(".csv")
        ]
        if not members:
            raise SystemExit("Archive contains no CSV files.")
        for member in members:
            output = RAW_DATA_DIR / Path(member).name
            with archive.open(member) as source, open(output, "wb") as target:
                target.write(source.read())

    for path, expected in EXPECTED_RAW_FILES.items():
        if not path.exists():
            raise SystemExit(f"Extracted file missing: {path}")
        if expected:
            actual = sha256_hex(path)
            if actual != expected:
                raise SystemExit(
                    f"Checksum mismatch for {path.name}: expected {expected}, "
                    f"got {actual}."
                )
    print("Extracted raw CSV files; checksums verified.")


def write_acquisition_record() -> None:
    """Write the provenance/ACQUISITION.txt next to the preserved raw data."""
    RAW_ACQUISITION_FILE.write_text(
        "\n".join(
            [
                "ACQUISITION RECORD - MediPlan AI Phase 7",
                "=" * 40,
                f"Dataset: {DATASET_NAME}",
                f"Publisher: {DATASET_PUBLISHER}",
                f"Source URL: {DATASET_URL}",
                f"Download URL: {DATASET_DOWNLOAD_URL}",
                f"DOI: {DATASET_DOI}",
                f"License: {DATASET_LICENSE}",
                f"Citation: {DATASET_CITATION}",
                f"Acquired: {ACQUISITION_DATE}",
                f"Raw archive SHA-256: {RAW_ARCHIVE_SHA256}",
                f"Raw CSV SHA-256: {RAW_CSV_SHA256}",
                "",
                "The raw files below are preserved exactly as released and are",
                "never modified in place. Processed outputs live in data/processed/.",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote provenance: {RAW_ACQUISITION_FILE}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download / verify the raw UCI release before preparing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute processed outputs even if already present.",
    )
    args = parser.parse_args()

    if args.download:
        download_raw()
    elif not RAW_DATA_FILE.exists():
        print(
            "Raw data not found under data/raw/. "
            "Run:  python scripts/prepare_dataset.py --download"
        )
        return 1

    summary = prepare_dataset(force=args.force)
    print("\nData preparation complete.")
    print(f"Rows: {summary['profile']['row_count']}")
    print(
        "Target "
        f"early_readmission rate: {summary['profile']['early_readmission_rate']}"
    )
    for name in ("train", "validation", "test"):
        split = summary["splits"][name]
        print(
            f"  {name}: rows={split['rows']} patients={split['unique_patients']} "
            f"early_rate={split['early_readmission_rate']}"
        )
    print(f"Encoded features: {summary['encoded_feature_count']}")
    print(f"Metadata: {summary['metadata_written']}")
    print("\nModel training is intentionally NOT part of Phase 7.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())