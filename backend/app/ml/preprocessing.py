"""Reproducible, leakage-safe preprocessing pipeline.

A single sklearn ``ColumnTransformer`` defines every learned transformation.
It is fitted once on the training split only, then applied to validation, test
and (later) inference data. No validation/test information influences imputed
values, encodings or scalings.

Handlers:
- numeric:   median imputation + standard scaling
- nominal:   most-frequent imputation + one-hot encoding (unknown ignored)
- ordinal:   most-frequent imputation + ordinal encoding with explicit order
"""

from __future__ import annotations

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from app.ml.config import (
    AGE_ORDER,
    NOMINAL_FEATURES,
    NUMERIC_FEATURES,
    ORDINAL_FEATURES,
    PREPROCESSOR_FILE,
)

RACE_MISSING_CATEGORY = "Unknown"


def _numeric_transformer() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )


def _nominal_transformer() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent", fill_value=None)),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                    dtype="float64",
                ),
            ),
        ]
    )


def _race_transformer() -> Pipeline:
    """``race`` uses an explicit missing category instead of assuming the mode."""
    return Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="constant", fill_value=RACE_MISSING_CATEGORY),
            ),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore", sparse_output=False, dtype="float64"
                ),
            ),
        ]
    )


def _ordinal_transformer(categories: list[str]) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent", fill_value=None)),
            (
                "encoder",
                OrdinalEncoder(
                    categories=[categories],
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    dtype="float64",
                ),
            ),
        ]
    )


def build_preprocessor() -> ColumnTransformer:
    """Build the fitted-on-train-only preprocessing pipeline."""
    nominal_features = [feature for feature in NOMINAL_FEATURES if feature != "race"]
    transformers = [
        ("numeric", _numeric_transformer(), NUMERIC_FEATURES),
        ("race", _race_transformer(), ["race"]),
        ("nominal", _nominal_transformer(), nominal_features),
    ]
    for feature, categories in ORDINAL_FEATURES.items():
        transformers.append((f"ordinal_{feature}", _ordinal_transformer(categories), [feature]))

    return ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=False,
    )


def fit_preprocessor(
    features: pd.DataFrame, preprocessor: ColumnTransformer | None = None
) -> ColumnTransformer:
    """Fit the pipeline on training features only and return the fitted object."""
    pipeline = preprocessor if preprocessor is not None else build_preprocessor()
    return pipeline.fit(features)


def apply_preprocessor(
    preprocessor: ColumnTransformer, features: pd.DataFrame
) -> pd.DataFrame:
    """Apply a fitted pipeline and return a named-feature DataFrame."""
    columns = list(preprocessor.get_feature_names_out())
    return pd.DataFrame(
        preprocessor.transform(features),
        columns=columns,
        index=features.index,
    )


def save_preprocessor(preprocessor: ColumnTransformer) -> None:
    """Persist the fitted pipeline for Phase 8 and inference reuse."""
    PREPROCESSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = PREPROCESSOR_FILE.with_name(f".{PREPROCESSOR_FILE.name}.tmp")
    try:
        joblib.dump(preprocessor, temp)
        temp.replace(PREPROCESSOR_FILE)
    finally:
        temp.unlink(missing_ok=True)


def load_preprocessor() -> ColumnTransformer:
    """Load the fitted pipeline saved by :func:`save_preprocessor`."""
    return joblib.load(PREPROCESSOR_FILE)