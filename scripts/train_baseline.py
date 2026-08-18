"""Train, evaluate and save the Phase 8 baseline Logistic Regression model.

Run from the repository root:

    python scripts/train_baseline.py
    python scripts/train_baseline.py --force   # overwrite an existing artifact

The model is trained on the Phase 7 training partition only. Validation is used
for assessment and the test partition only for the final evaluation. The saved
model is a research/prototype readmission-risk estimator, not a clinical tool.
"""

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.config import MODEL_FILE, MODEL_METADATA_FILE, MODEL_VERSION  # noqa: E402
from app.ml.train import train_baseline  # noqa: E402


def existing_artifact_summary() -> str:
    import json as _json

    metadata = _json.loads(MODEL_METADATA_FILE.read_text(encoding="utf-8"))
    test = metadata["metrics"]["test"]
    return (
        f"  version: {metadata['model']['version']}\n"
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
        help="Overwrite an existing baseline artifact without prompting.",
    )
    args = parser.parse_args()

    if MODEL_FILE.exists() and not args.force:
        print(f"A baseline model already exists at {MODEL_FILE}:")
        print(existing_artifact_summary())
        print(
            "Re-running would overwrite it. Use --force to retrain and replace."
        )
        return 1

    summary = train_baseline()
    print("\nBaseline training complete.")
    print(f"Model version: {summary['model_version']}")
    print(f"Model file: {summary['model_file']}")
    print(f"Metadata file: {summary['metadata_file']}")
    print(f"\nTrain metrics: {json.dumps(summary['train_metrics'])}")
    print(f"Validation metrics: {json.dumps(summary['validation_metrics'])}")
    print(f"Final test metrics: {json.dumps(summary['test_metrics'])}")
    print(
        "\nResearch/prototype risk estimate only; not a diagnosis, prescription "
        "or treatment decision."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())