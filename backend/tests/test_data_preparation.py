"""Focused tests for the Phase 7 data-preparation pipeline.

These tests run against the preserved raw release under ``data/raw`` and the
generated outputs under ``data/processed``. They cover the Phase 7 checklist:
loading, target, feature inventory, missing-value handling, encoding, scaling,
split reproducibility, no test-data influence on fitted preprocessing, no
unexpected missing values, and run-to-run determinism.
"""

import pandas as pd
import pytest

from app.ml import ingestion, prepare, preprocessing, split
from app.ml.config import (
    FEATURES,
    NUMERIC_FEATURES,
    PREPROCESSOR_FILE,
    RANDOM_SEED,
    RAW_CSV_SHA256,
    RAW_DATA_FILE,
    SPLIT_FILES,
    TARGET_COLUMN,
    TARGET_DERIVED,
)
from app.ml.prepare import _file_sha256

RAW_ROW_COUNT = 101766
EARLY_COUNT = 11357


@pytest.fixture(scope="module")
def raw_frame() -> pd.DataFrame:
    return ingestion.load_raw_data()


@pytest.fixture(scope="module")
def target_frame(raw_frame) -> pd.DataFrame:
    return ingestion.derive_target(raw_frame)


class TestIngestion:
    def test_raw_data_loads(self, raw_frame):
        assert raw_frame is not None
        assert len(raw_frame) == RAW_ROW_COUNT

    def test_target_exists(self, target_frame):
        assert TARGET_COLUMN in target_frame.columns
        assert TARGET_DERIVED in target_frame.columns
        assert set(target_frame[TARGET_DERIVED].unique()).issubset({0, 1})

    def test_expected_features_present(self, raw_frame):
        missing = set(FEATURES) - set(raw_frame.columns)
        assert not missing

    def test_target_distribution_matches_release(self, target_frame):
        assert int((target_frame[TARGET_DERIVED] == 1).sum()) == EARLY_COUNT
        assert abs(
            target_frame[TARGET_DERIVED].mean() - EARLY_COUNT / RAW_ROW_COUNT
        ) < 1e-6

    def test_only_question_mark_is_missing(self, raw_frame):
        missing = raw_frame[FEATURES].isna().sum()
        assert (missing == 0).all() or set(missing.index[missing > 0]) == {"race"}
        assert missing.get("race", 0) == 2273


class TestPreprocessing:
    @pytest.fixture(scope="class")
    def fitted(self, target_frame):
        train, _, _ = split.grouped_train_valid_test_split(target_frame, seed=RANDOM_SEED)
        preprocessor = preprocessing.fit_preprocessor(train[FEATURES])
        encoded = preprocessing.apply_preprocessor(preprocessor, train[FEATURES])
        return preprocessor, train, encoded

    def test_missing_value_handling(self, fitted):
        preprocessor, train, encoded = fitted
        assert "race_Unknown" in encoded.columns
        expected_missing = int(train["race"].isna().sum())
        assert int((encoded["race_Unknown"] == 1).sum()) == expected_missing
        assert expected_missing > 0

    def test_categorical_encoding_works(self, fitted):
        _, _, encoded = fitted
        gender_block = [c for c in encoded.columns if c.startswith("gender_")]
        assert gender_block
        assert (encoded[gender_block].sum(axis=1) == 1).all()
        age_values = set(encoded["age"].unique())
        assert age_values.issubset({0, 1, 2, 3, 4, 5, 6, 7, 8, 9})

    def test_numerical_preprocessing_works(self, fitted):
        preprocessor, _, encoded = fitted
        for feature in NUMERIC_FEATURES:
            values = encoded[feature]
            assert abs(values.mean()) < 0.05
            assert abs(values.std() - 1.0) < 0.05
        transformer = preprocessor.named_transformers_["numeric"]
        assert transformer.named_steps["scaler"].with_mean

    def test_no_test_or_validation_used_to_fit(self, fitted):
        preprocessor, train, _ = fitted
        fitted_median = preprocessor.named_transformers_[
            "numeric"
        ].named_steps["imputer"].statistics_[0]
        assert fitted_median == train["time_in_hospital"].median()


class TestSplit:
    def test_split_reproducible(self, target_frame):
        first = split.grouped_train_valid_test_split(target_frame, seed=RANDOM_SEED)
        second = split.grouped_train_valid_test_split(target_frame, seed=RANDOM_SEED)
        for a, b in zip(first, second):
            assert a.index.equals(b.index)
            assert a["patient_nbr"].equals(b["patient_nbr"])
            assert a[TARGET_DERIVED].equals(b[TARGET_DERIVED])

    def test_split_partitions_all_rows(self, target_frame):
        train, validation, test = split.grouped_train_valid_test_split(
            target_frame, seed=RANDOM_SEED
        )
        assert len(train) + len(validation) + len(test) == len(target_frame)
        assert (
            len(set(train["patient_nbr"]) & set(validation["patient_nbr"])) == 0
        )
        assert len(set(train["patient_nbr"]) & set(test["patient_nbr"])) == 0
        assert len(set(validation["patient_nbr"]) & set(test["patient_nbr"])) == 0


class TestPrepareEndToEnd:
    def test_pipeline_repeatable_and_no_unexpected_missing(self):
        raw_before = _file_sha256(RAW_DATA_FILE)

        summary = prepare.prepare_dataset(force=True)

        first_bytes = {name: path.read_bytes() for name, path in SPLIT_FILES.items()}
        prepare.prepare_dataset(force=True)
        second_bytes = {
            name: path.read_bytes() for name, path in SPLIT_FILES.items()
        }

        for name in SPLIT_FILES:
            assert first_bytes[name] == second_bytes[name], f"{name} differs"

        for name, path in SPLIT_FILES.items():
            frame = pd.read_csv(path)
            assert not frame.isna().any().any(), f"{name} has missing values"

        assert summary["encoded_feature_count"] > 0
        assert PREPROCESSOR_FILE.exists()
        assert raw_before == RAW_CSV_SHA256

    def test_split_files_balance(self):
        validation = pd.read_csv(SPLIT_FILES["validation"])
        test = pd.read_csv(SPLIT_FILES["test"])
        train = pd.read_csv(SPLIT_FILES["train"])
        assert len(train) + len(validation) + len(test) == RAW_ROW_COUNT
        for frame in (train, validation, test):
            assert not frame["encounter_id"].duplicated().any()
            assert frame["early_readmission"].isin({0, 1}).all()
            assert not frame["patient_nbr"].duplicated().all()