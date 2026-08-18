"""Phase 7 data-preparation configuration.

Fixed, versioned constants for the selected Phase 2 dataset (UCI Diabetes
130-US Hospitals for Years 1999-2008). The dataset, target and feature list are
the Phase 2 decision from ``docs/research.md``; this module does not re-make
that decision.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DATA_DIR = REPO_ROOT / "data" / "raw" / "diabetes_130_us_hospitals"
RAW_DATA_FILE = RAW_DATA_DIR / "diabetic_data.csv"
RAW_IDS_MAPPING_FILE = RAW_DATA_DIR / "IDS_mapping.csv"
RAW_ARCHIVE_FILE = RAW_DATA_DIR / "diabetes_130_us_hospitals_1999_2008.zip"
RAW_ACQUISITION_FILE = RAW_DATA_DIR / "ACQUISITION.txt"

PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"
PREPROCESSOR_FILE = PROCESSED_DATA_DIR / "preprocessor.joblib"
METADATA_FILE = PROCESSED_DATA_DIR / "dataset_metadata.json"
SPLIT_FILES = {
    "train": PROCESSED_DATA_DIR / "train.csv",
    "validation": PROCESSED_DATA_DIR / "validation.csv",
    "test": PROCESSED_DATA_DIR / "test.csv",
}

# Phase 8 model artifacts (versioned; never patient data).
MODELS_DIR = REPO_ROOT / "models"
MODEL_FILE = MODELS_DIR / "logistic_regression_baseline_v1.joblib"
MODEL_METADATA_FILE = MODELS_DIR / "baseline_model_metadata.json"
MODEL_VERSION = "baseline-logistic-v1"

# Phase 9 model artifacts (versioned; never patient data).
SELECTED_MODEL_FILE = MODELS_DIR / "selected_model_v1.joblib"
SELECTED_MODEL_METADATA_FILE = MODELS_DIR / "selected_model_metadata.json"
SELECTED_MODEL_VERSION = "selected-model-v1"

# Phase 10 validation artifacts (versioned; never patient data).
VALIDATION_CONFIG_FILE = MODELS_DIR / "model_validation_v1.json"
VALIDATION_CONFIG_VERSION = "validation-config-v1"
SELECTED_CALIBRATOR_FILE = MODELS_DIR / "selected_model_calibrator_v1.joblib"

# Phase 12 explainability artifacts (versioned; aggregates only, never
# individual patient records).
EXPLAINABILITY_GLOBAL_FILE = MODELS_DIR / "explainability_global_v1.json"
EXPLAINABILITY_GLOBAL_VERSION = "explainability-global-v1"

# UCI download source (verified page terms, CC BY 4.0).
DATASET_NAME = "Diabetes 130-US Hospitals for Years 1999-2008"
DATASET_PUBLISHER = "UCI Machine Learning Repository"
DATASET_URL = "https://archive.ics.uci.edu/dataset/296/diabetes-130-us-hospitals-for-years-1999-2008"
DATASET_DOWNLOAD_URL = (
    "https://archive.ics.uci.edu/static/public/296/"
    "diabetes+130-us+hospitals+for+years+1999-2008.zip"
)
DATASET_DOI = "10.24432/C5230J"
DATASET_LICENSE = "CC BY 4.0"
DATASET_CITATION = (
    "Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014). "
    "Diabetes 130-US Hospitals for Years 1999-2008 [Dataset]. "
    "UCI Machine Learning Repository. https://doi.org/10.24432/C5230J"
)
DATASET_INTRO_PUBLICATION = (
    "Strack, B., DeShazo, J., Gennings, C., Olmo, J., Ventura, S., Cios, K., "
    "& Clore, J. (2014). Impact of HbA1c Measurement on Hospital Readmission "
    "Rates: Analysis of 70,000 Clinical Database Patient Records. "
    "BioMed Research International, 2014, 781670."
)

# Date on which the release was acquired and preserved under data/raw/.
ACQUISITION_DATE = "2026-08-17"

# Raw data-guard rules.
RAW_ARCHIVE_SHA256 = (
    "F82AC129DA2DDD2299391FF6FBAE3A6A58B3EDCF59AC9D7BD480C00FE453112A"
)
RAW_CSV_SHA256 = "0689E7EC031237DC63031B938805C48377748761A3B26ACAB621567AFA24DF97"

# Sentinel loaded as NaN. ``None`` is a real category here (test not performed).
NA_VALUES = ["?"]

# Phase 2 decision.
TARGET_COLUMN = "readmitted"
TARGET_DERIVED = "early_readmission"
EARLY_VALUE = "<30"

# Identifiers keep for provenance; never features.
ID_COLUMNS = ["encounter_id", "patient_nbr"]

# Selected Phase 2 feature list (exact order from docs/research.md).
FEATURES = [
    "race",
    "gender",
    "age",
    "admission_type_id",
    "admission_source_id",
    "time_in_hospital",
    "num_lab_procedures",
    "num_procedures",
    "num_medications",
    "number_outpatient",
    "number_emergency",
    "number_inpatient",
    "number_diagnoses",
    "max_glu_serum",
    "A1Cresult",
    "diabetesMed",
    "change",
]

# All raw columns that exist but are deliberately excluded, with reasons.
EXCLUDED_FEATURES = {
    "weight": "Missing for ~97% of rows and not part of the Phase 2 feature set.",
    "payer_code": "Not in the Phase 2 feature set; payer context is not discharge-time model input.",
    "medical_specialty": "Not in the Phase 2 feature set; high-cardinality admittance context.",
    "diag_1": "Not in the Phase 2 feature set; diagnosis context.",
    "diag_2": "Not in the Phase 2 feature set; diagnosis context.",
    "diag_3": "Not in the Phase 2 feature set; diagnosis context.",
    "discharge_disposition_id": "Leakage: determined at discharge and may encode care pathway/outcome.",
    "metformin": "Not in the Phase 2 feature set.",
    "repaglinide": "Not in the Phase 2 feature set.",
    "nateglinide": "Not in the Phase 2 feature set.",
    "chlorpropamide": "Not in the Phase 2 feature set.",
    "glimepiride": "Not in the Phase 2 feature set.",
    "acetohexamide": "Not in the Phase 2 feature set.",
    "glipizide": "Not in the Phase 2 feature set.",
    "glyburide": "Not in the Phase 2 feature set.",
    "tolbutamide": "Not in the Phase 2 feature set.",
    "pioglitazone": "Not in the Phase 2 feature set.",
    "rosiglitazone": "Not in the Phase 2 feature set.",
    "acarbose": "Not in the Phase 2 feature set.",
    "miglitol": "Not in the Phase 2 feature set.",
    "troglitazone": "Not in the Phase 2 feature set.",
    "tolazamide": "Not in the Phase 2 feature set.",
    "examide": "Not in the Phase 2 feature set.",
    "citoglipton": "Not in the Phase 2 feature set.",
    "insulin": "Not in the Phase 2 feature set.",
    "glyburide-metformin": "Not in the Phase 2 feature set.",
    "glipizide-metformin": "Not in the Phase 2 feature set.",
    "glimepiride-pioglitazone": "Not in the Phase 2 feature set.",
    "metformin-rosiglitazone": "Not in the Phase 2 feature set.",
    "metformin-pioglitazone": "Not in the Phase 2 feature set.",
}

NUMERIC_FEATURES = [
    "time_in_hospital",
    "num_lab_procedures",
    "num_procedures",
    "num_medications",
    "number_outpatient",
    "number_emergency",
    "number_inpatient",
    "number_diagnoses",
]

# Ordinal categories for ``age`` (bin order is meaningful).
AGE_ORDER = [
    "[0-10)",
    "[10-20)",
    "[20-30)",
    "[30-40)",
    "[40-50)",
    "[50-60)",
    "[60-70)",
    "[70-80)",
    "[80-90)",
    "[90-100)",
]

ORDINAL_FEATURES = {"age": AGE_ORDER}

NOMINAL_FEATURES = [
    "race",
    "gender",
    "admission_type_id",
    "admission_source_id",
    "max_glu_serum",
    "A1Cresult",
    "diabetesMed",
    "change",
]

# Split strategy (grouped by patient; see docs/data-preparation.md).
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
TEST_FRACTION = 0.15
RANDOM_SEED = 42
PREPROCESSING_VERSION = "1.0.0"