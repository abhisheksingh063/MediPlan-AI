"""Evidence-cited treatment decision support service (Phase 13).

Evaluates a patient's recorded clinical data against declarative rules loaded
from ``app/treatment_support/rules.json``. The clinical input catalog (field
aliases, units, guideline recency windows) lives in
``app/treatment_support/inputs.json``.

The module is deliberately isolated from ``app.services.inference`` and
``app.services.explainability``: machine-learning readmission estimates never
enter rule evaluation, so rule outcomes are independent of the Phase 7-10 model.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from json import load
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Patient
from app.services.patients import get_patient_or_404, list_clinical_records

_DATA_DIR = Path(__file__).resolve().parents[1] / "treatment_support"

_SAFETY_MESSAGE = (
    "Decision support only - clinician review required. This prototype "
    "evaluates the patient's recorded data against evidence-based "
    "considerations from the cited guidelines; it does not establish a "
    "diagnosis (the underlying dataset is not a clinically validated Type 2 "
    "diabetes cohort), does not select or dose medications, and does not "
    "replace clinical judgment. Model-estimated readmission risk (ML), "
    "evidence-based considerations (this module), and the final clinical "
    "decision (clinician) are kept separate and are never merged into a "
    "single automated conclusion."
)

_INTERPRETATION_NOTE = (
    "Considerations are returned independently and are not ranked or "
    "synthesized into a single plan. Where considerations point in different "
    "clinical directions, the system does not weigh them; resolving any such "
    "tension requires clinician judgment."
)


class TreatmentSupportError(Exception):
    """Base error for treatment-support evaluation failures."""


class RulesUnavailableError(TreatmentSupportError):
    """Raised when the declarative rule or input data cannot be loaded."""


@lru_cache(maxsize=1)
def _load_rules_data() -> dict:
    try:
        with (_DATA_DIR / "rules.json").open(encoding="utf-8") as handle:
            return load(handle)
    except (OSError, ValueError) as exc:
        raise RulesUnavailableError("Treatment-support rules unavailable.") from exc


@lru_cache(maxsize=1)
def _load_input_catalog() -> dict:
    try:
        with (_DATA_DIR / "inputs.json").open(encoding="utf-8") as handle:
            return load(handle)
    except (OSError, ValueError) as exc:
        raise RulesUnavailableError("Treatment-support input catalog unavailable.") from exc


def clear_rule_cache() -> None:
    """Drop cached rule data so tests can reload updated data files."""
    _load_rules_data.cache_clear()
    _load_input_catalog.cache_clear()


def _input_catalog() -> dict[str, dict]:
    data = _load_input_catalog()
    return {entry["field"]: entry for entry in data["inputs"]}


def _guideline_version() -> str:
    return _load_input_catalog()["guideline_version"]


def _rules() -> list[dict]:
    return _load_rules_data()["rules"]


def _normalise_test_name(test_name: str) -> str:
    return " ".join(test_name.strip().lower().split())


def _resolve_field(test_name: str, catalog: dict[str, dict]) -> str | None:
    """Map a free-text lab test name to a canonical catalog field."""
    normalised = _normalise_test_name(test_name)
    for field, entry in catalog.items():
        if normalised in {a.lower() for a in entry["aliases"]}:
            return field
    return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _compute_bmi(patient: Patient) -> float | None:
    """Return BMI (kg/m^2) from recorded height (cm) and weight (kg), or None."""
    if patient.height is None or patient.weight is None:
        return None
    try:
        height_m = float(patient.height) / 100.0
        if height_m <= 0:
            return None
        return round(float(patient.weight) / (height_m * height_m), 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _collect_lab_fields(
    db: Session, patient_id: int, catalog: dict[str, dict]
) -> dict[str, tuple[float, datetime]]:
    """Return the most recent value+timestamp per canonical lab field.

    The most recent result wins, determined by ``recorded_at`` (ties broken by
    record id). Only results whose test name maps to the catalog are kept.
    """
    latest: dict[str, tuple[float, datetime, int]] = {}
    for record in list_clinical_records(db, patient_id):
        for result in record.lab_results:
            field = _resolve_field(result.test_name, catalog)
            if field is None:
                continue
            timestamp = _as_utc(result.recorded_at)
            current = latest.get(field)
            if current is None or (timestamp, result.id) > (current[1], current[2]):
                latest[field] = (float(result.value), timestamp, result.id)
    return {field: (value, timestamp) for field, (value, timestamp, _) in latest.items()}


def _evaluate_trigger(trigger: dict, values: dict[str, float]) -> bool:
    """Evaluate a declarative trigger against evaluated input values.

    Supports ``all``/``any`` combinators whose clauses are themselves triggers,
    and leaf clauses of the form ``{"field", "op", "value"}``. Operators are
    ``gte``, ``gt``, ``lte``, ``lt``, ``eq``, ``ne``.
    """
    op = trigger["op"]
    if op in {"all", "any"}:
        results = [_evaluate_trigger(clause, values) for clause in trigger["clauses"]]
        return all(results) if op == "all" else any(results)
    field = trigger["field"]
    if field not in values:
        return False
    actual = values[field]
    expected = trigger["value"]
    if op == "gte":
        return actual >= expected
    if op == "gt":
        return actual > expected
    if op == "lte":
        return actual <= expected
    if op == "lt":
        return actual < expected
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    raise RulesUnavailableError(f"Unsupported rule operator: {op}")


def _format_value(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:g}"


def _render_output(template: str, values: dict[str, float]) -> str:
    """Render a rule's ``output_text`` with the evaluated input values."""
    rendered = template
    for field, value in values.items():
        rendered = rendered.replace("{" + field + "}", _format_value(value))
    return rendered


def _evidence_summary(evidence: dict) -> str:
    parts = [
        evidence["organization"],
        evidence["document"],
        evidence.get("version", ""),
    ]
    section = evidence.get("section", "")
    table = evidence.get("table_or_recommendation", "")
    if section:
        parts.append(section)
    if table:
        parts.append(table)
    if evidence.get("doi"):
        parts.append(f"DOI {evidence['doi']}")
    return ", ".join(part for part in parts if part)


def _evaluate_rule(
    rule: dict, values: dict[str, float], missing_fields: set[str]
) -> dict | None:
    required = set(rule.get("required_inputs", []))
    if not required.issubset(values.keys()) or required & missing_fields:
        return None
    if not _evaluate_trigger(rule["trigger"], values):
        return None
    return {
        "rule_id": rule["rule_id"],
        "title": rule["title"],
        "severity_tag": rule["severity_tag"],
        "reason": _render_output(rule["output_text"], values),
        "evidence_source": _evidence_summary(rule["evidence_source"]),
        "requires_clinician_review": rule.get("requires_clinician_review", True),
        "inputs_evaluated": sorted(required),
    }


def evaluate(db: Session, patient_id: int) -> dict:
    """Evaluate the treatment-support rules for a patient.

    Only the patient's recorded demographic and lab data are used. Values that
    are absent or older than the guideline recency window are recorded in
    ``missing_information`` and suppress the rules that need them.
    """
    catalog = _input_catalog()
    patient = get_patient_or_404(db, patient_id)

    now = datetime.now(timezone.utc)
    values: dict[str, float] = {}
    missing_information: list[dict] = []

    for field, entry in catalog.items():
        if field == "bmi":
            bmi = _compute_bmi(patient)
            if bmi is not None:
                values[field] = bmi
            else:
                missing_information.append({"field": field, "reason": "missing"})
            continue
        if field == "age":
            if patient.age is not None:
                values[field] = float(patient.age)
            else:
                missing_information.append({"field": field, "reason": "missing"})
            continue

    lab_fields = _collect_lab_fields(db, patient_id, catalog)
    for field, entry in catalog.items():
        if field in {"bmi", "age"}:
            continue
        recency = entry.get("recency_days")
        if field not in lab_fields:
            missing_information.append({"field": field, "reason": "missing"})
            continue
        value, recorded_at = lab_fields[field]
        if recency is not None and now - recorded_at > timedelta(days=recency):
            missing_information.append(
                {
                    "field": field,
                    "reason": "stale",
                    "last_available": recorded_at,
                }
            )
            continue
        values[field] = value

    missing_fields = {entry["field"] for entry in missing_information}
    considerations = [
        consideration
        for rule in _rules()
        if (consideration := _evaluate_rule(rule, values, missing_fields)) is not None
    ]

    return {
        "patient_id": patient_id,
        "decision_support_only": True,
        "clinical_validation_required": True,
        "guideline_version": _guideline_version(),
        "generated_at": now,
        "considerations": considerations,
        "missing_information": missing_information,
        "interpretation_note": _INTERPRETATION_NOTE,
        "safety_message": _SAFETY_MESSAGE,
    }
