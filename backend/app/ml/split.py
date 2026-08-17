"""Grouped train/validation/test splitting.

Phase 7 uses a grouped split by ``patient_nbr`` so repeated encounters of one
patient never straddle train/validation/test (research.md: group splits when
repeated encounters occur). A two-stage ``GroupShuffleSplit`` with a fixed seed
approximates stratification at the group level; exact row-wise stratification
is impossible while keeping patients intact.
"""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from app.ml.config import (
    RANDOM_SEED,
    TARGET_DERIVED,
    TEST_FRACTION,
    TRAIN_FRACTION,
    VALIDATION_FRACTION,
)

TEMP_FRACTION = (
    (VALIDATION_FRACTION + TEST_FRACTION) / (TRAIN_FRACTION + VALIDATION_FRACTION + TEST_FRACTION)
)
VAL_OF_TEMP = VALIDATION_FRACTION / (VALIDATION_FRACTION + TEST_FRACTION)


def grouped_train_valid_test_split(
    frame: pd.DataFrame, *, seed: int = RANDOM_SEED
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split an encounter frame into train/validation/test keeping patients whole.

    Returns ``(train, validation, test)`` row subsets. Every row of the input
    frame appears in exactly one output partition.
    """
    groups = frame["patient_nbr"]
    target = frame[TARGET_DERIVED]

    first = GroupShuffleSplit(
        n_splits=1, test_size=TEMP_FRACTION, random_state=seed
    )
    train_idx, temp_idx = next(iter(first.split(frame, target, groups)))

    second = GroupShuffleSplit(
        n_splits=1, test_size=VAL_OF_TEMP, random_state=seed
    )
    val_idx, test_idx = next(
        iter(second.split(frame.iloc[temp_idx], frame.iloc[temp_idx][TARGET_DERIVED], frame.iloc[temp_idx]["patient_nbr"]))
    )
    candidate_val = frame.iloc[temp_idx].index[val_idx]
    candidate_test = frame.iloc[temp_idx].index[test_idx]

    train = frame.iloc[train_idx]
    validation = frame.loc[candidate_val]
    test = frame.loc[candidate_test]

    _assert_no_overlap(train, validation, test)
    return train, validation, test


def _assert_no_overlap(
    train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame
) -> None:
    if train.index.intersection(validation.index).size:
        raise AssertionError("train/validation overlap")
    if train.index.intersection(test.index).size:
        raise AssertionError("train/test overlap")
    if validation.index.intersection(test.index).size:
        raise AssertionError("validation/test overlap")
    train_patients = set(train["patient_nbr"])
    if set(validation["patient_nbr"]) & train_patients:
        raise AssertionError("patient group appears in both train and validation")
    if set(test["patient_nbr"]) & train_patients:
        raise AssertionError("patient group appears in both train and test")
    if set(validation["patient_nbr"]) & set(test["patient_nbr"]):
        raise AssertionError("patient group appears in both validation and test")