"""Run the Phase 10 model validation and calibration analysis.

Run from the repository root:

    python scripts/validate_model.py
    python scripts/validate_model.py --force   # overwrite an existing config

Uses the Phase 9 selected model and the Phase 7 training/validation partitions
to analyse probability thresholds and calibration, freezes a prototype review
threshold (and calibration method, if beneficial), then evaluates the frozen
configuration once on the untouched test partition. The configuration is saved
to ``models/model_validation_v1.json``.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml import validate  # noqa: E402
from app.ml.config import VALIDATION_CONFIG_FILE, VALIDATION_CONFIG_VERSION  # noqa: E402


def existing_artifact_summary() -> str:
    import json as _json

    config = _json.loads(VALIDATION_CONFIG_FILE.read_text(encoding="utf-8"))
    test = config["metrics"]["test"]["at_selected_threshold"]
    return (
        f"  version: {config['artifact']['version']}\n"
        f"  created: {config['artifact']['created']}\n"
        f"  threshold: {config['threshold']['selected']}  "
        f"calibration: {config['calibration']['method']}\n"
        f"  test F1: {test['f1']}  recall: {test['recall']}  "
        f"precision: {test['precision']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing validation config without prompting.",
    )
    args = parser.parse_args()

    if VALIDATION_CONFIG_FILE.exists() and not args.force:
        print(f"A validation config already exists at {VALIDATION_CONFIG_FILE}:")
        print(existing_artifact_summary())
        print("Re-running would overwrite it. Use --force to recompute and replace.")
        return 1

    summary = validate.run_validation()
    print("\nModel validation complete.")
    print(f"Config version: {summary['artifact_version']}")
    print(f"Config file: {summary['config_file']}")
    print(f"\nSelected threshold: {summary['selected_threshold']}")
    print(summary["threshold_rationale"])
    print(f"\nCalibration method: {summary['calibration_method']}")
    print(summary["calibration_rationale"])
    print(
        f"Validation Brier: "
        f"{summary['calibration_assessment']['uncalibrated']['brier_score']}"
    )
    print(f"\nValidation metrics: {json.dumps(summary['validation_metrics'])}")
    print(
        "Test at selected threshold: "
        f"{json.dumps(summary['test_metrics_at_selected_threshold'])}"
    )
    print(
        "Test at 0.50 (raw probabilities): "
        f"{json.dumps(summary['test_metrics_at_default_0_50'])}"
    )
    print(
        "\nResearch/prototype risk estimate only; the threshold is a prototype "
        "review threshold, not a clinically validated boundary."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())