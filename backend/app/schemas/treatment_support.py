"""Schemas for the Phase 13 evidence-cited treatment decision support module.

This module is a clinician-review aid only. It evaluates the patient's recorded
data against declarative, evidence-cited considerations; it never selects drugs,
doses, or diagnoses, and its output is never merged with the Phase 7-10 machine
learning readmission estimate.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SeverityTag = Literal["informational", "consider_review", "urgent_review"]
MissingReason = Literal["missing", "stale"]


class TreatmentSupportRequest(BaseModel):
    """Input for a treatment-support evaluation of an existing patient."""

    patient_id: int = Field(ge=1)


class Consideration(BaseModel):
    """One evidence-cited clinical consideration triggered for the patient.

    ``reason`` is the human-readable clinical text from the rule, rendered with
    the evaluated input values. ``inputs_evaluated`` lists the names of the
    patient inputs that rule used; values are intentionally not repeated there
    so raw clinical data stays out of structured audit fields.
    """

    rule_id: str
    title: str
    severity_tag: SeverityTag
    reason: str
    evidence_source: str
    requires_clinician_review: bool
    inputs_evaluated: list[str]


class MissingInformation(BaseModel):
    """A clinical input that could not be evaluated.

    ``reason`` is ``missing`` when no value is recorded at all, or ``stale``
    when the most recent value is older than the guideline's recommended
    recency window (e.g. an A1C older than six months per ADA). ``last_available``
    carries the recorded timestamp of the most recent value for ``stale`` items.
    """

    field: str
    reason: MissingReason
    last_available: datetime | None = None


class TreatmentSupportResponse(BaseModel):
    """Result of a treatment-support evaluation for one patient."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    decision_support_only: bool
    clinical_validation_required: bool
    guideline_version: str
    generated_at: datetime
    considerations: list[Consideration]
    missing_information: list[MissingInformation]
    interpretation_note: str
    safety_message: str
