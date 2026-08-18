"""Pydantic schemas for the ML inference endpoint.

Allowed categorical values match the categories the fitted Phase 7
preprocessor learned from the training partition (see the ``OneHotEncoder`` and
``OrdinalEncoder`` category lists). Numeric bounds are data-sanity limits from
the evaluated dataset's observed ranges; they are not clinical thresholds.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Race = Literal[
    "AfricanAmerican", "Asian", "Caucasian", "Hispanic", "Other", "Unknown"
]
Gender = Literal["Female", "Male", "Unknown/Invalid"]
AgeBin = Literal[
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
MaxGluSerum = Literal[">200", ">300", "None", "Norm"]
A1CResult = Literal[">7", ">8", "None", "Norm"]
DiabetesMed = Literal["No", "Yes"]
MedicationChange = Literal["Ch", "No"]

ALLOWED_ADMISSION_SOURCE_IDS = {
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    13,
    14,
    17,
    20,
    22,
    25,
}


class InferenceRequest(BaseModel):
    """Structured clinical input for the 17-field Phase 7 feature set."""

    race: Race
    gender: Gender
    age: AgeBin
    admission_type_id: int = Field(ge=1, le=8)
    admission_source_id: int = Field(ge=1)
    time_in_hospital: int = Field(ge=1, le=30)
    num_lab_procedures: int = Field(ge=1, le=200)
    num_procedures: int = Field(ge=0, le=20)
    num_medications: int = Field(ge=1, le=100)
    number_outpatient: int = Field(ge=0, le=100)
    number_emergency: int = Field(ge=0, le=100)
    number_inpatient: int = Field(ge=0, le=50)
    number_diagnoses: int = Field(ge=1, le=50)
    max_glu_serum: MaxGluSerum
    A1Cresult: A1CResult
    diabetesMed: DiabetesMed
    change: MedicationChange

    @field_validator("admission_source_id")
    @classmethod
    def validate_admission_source_id(cls, value: int) -> int:
        if value not in ALLOWED_ADMISSION_SOURCE_IDS:
            allowed = ", ".join(str(item) for item in sorted(ALLOWED_ADMISSION_SOURCE_IDS))
            raise ValueError(
                f"admission_source_id must be one of: {allowed}"
            )
        return value


class CalibrationInfo(BaseModel):
    """Calibration configuration applied to the model probability."""

    method: str
    version: str


class InferenceResponse(BaseModel):
    """Decision-support inference result. Never a diagnosis/recommendation."""

    model_version: str
    probability: float = Field(ge=0.0, le=1.0)
    threshold: float
    review_required: bool
    calibration: CalibrationInfo
    safety_message: str