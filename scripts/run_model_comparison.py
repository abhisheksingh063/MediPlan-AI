"""Run the Phase 9 model comparison and persist the selected model.

Run from the repository root:

    python scripts/run_model_comparison.py
    python scripts/run_model_comparison.py --force   # overwrite selected artifact

Compares Logistic Regression (Phase 8 baseline) with Random Forest and Gradient
Boosting candidates on the Phase 7 training/validation partitions, selects a
model from validation metrics only, then evaluates the selected model once on
the untouched test partition and saves it to ``models/selected_model_v1.joblib``.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml import compare  # noqa: E402
from app.ml.config import (  # noqa: E402
    SELECTED_MODEL_FILE,
    SELECTED_MODEL_METADATA_FILE,
    SELECTED_MODEL_VERSION,
)


def existing_artifact_summary() -> str:
    import json as _json

    metadata = _json.loads(SELECTED_MODEL_METADATA_FILE.read_text(encoding="utf-8"))
    test = metadata["metrics"]["test"]
    return (
        f"  model: {metadata['model']['name']} ({metadata['model']['version']})\n"
        f"  trained: {metadata['training']['date']}\n"
        f"  test ROC-AUC: {test['roc_auc']}  PR-AUC: {test['average_precision']}\n"
        f"  accuracy: {test['accuracy']}  precision: {test['precision']}  "
        f"recall: {test['recall']}  F1: {test['f1']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing selected-model artifact without prompting.",
    )
    args = parser.parse_args()

    if SELECTED_MODEL_FILE.exists() and not args.force:
        print(f"A selected model already exists at {SELECTED_MODEL_FILE}:")
        print(existing_artifact_summary())
        print(
            "Re-running would overwrite it. Use --force to retrain and replace."
        )
        return 1

    summary = compare.run_comparison()
    print("\nModel comparison complete.")
    print(f"Selected model version: {summary['model_version']}")
    print(f"Selected: {summary['selected_display_name']}")
    print(f"Model file: {summary['model_file']}")
    print(f"Metadata file: {summary['metadata_file']}")
    print("\nValidation ranking (by PR-AUC):")
    for row in summary["ranking"]:
        print(
            f"  {row['candidate']:<34} "
            f"PR-AUC {row['validation_average_precision']:.6f}  "
            f"ROC-AUC {row['validation_roc_auc']:.6f}  "
            f"F1 {row['validation_f1']:.6f}  "
            f"gap {row['generalization_gap_roc_auc']:+.6f}"
        )
    print("\nSelection rationale:")
    print(summary["selection_rationale"])
    print(f"\nFinal test metrics: {json.dumps(summary['test_metrics'])}")
    print(
        "\nResearch/prototype risk estimate only; not a diagnosis, prescription "
        "or treatment decision."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())