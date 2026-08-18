"""Generate the Phase 12 global SHAP feature-importance summary (offline).

Run from the repository root:

    python scripts/global_explainability.py
    python scripts/global_explainability.py --force   # overwrite existing summary

Computes exact interventional SHAP values for the selected Logistic Regression
over the Phase 7 validation partition, aggregates transformed contributions
back to the 17 original clinical features, and saves ONLY aggregate statistics
to ``models/explainability_global_v1.json``. No individual patient or
encounter records are stored or exposed.

SHAP explains model behaviour; it does not establish clinical causation.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np  # noqa: E402
import shap  # noqa: E402

from app.ml import train as baseline  # noqa: E402
from app.ml.compare import load_selected_model  # noqa: E402
from app.ml.config import (  # noqa: E402
    DATASET_NAME,
    EXPLAINABILITY_GLOBAL_FILE,
    EXPLAINABILITY_GLOBAL_VERSION,
    SELECTED_MODEL_VERSION,
)
from app.services import explainability  # noqa: E402


def existing_artifact_summary() -> str:
    config = json.loads(EXPLAINABILITY_GLOBAL_FILE.read_text(encoding="utf-8"))
    top = config["features"][0]
    return (
        f"  version: {config['artifact']['version']}\n"
        f"  created: {config['artifact']['created']}\n"
        f"  rows: {config['dataset']['validation_rows']} (validation)\n"
        f"  top feature: {top['feature']}  "
        f"mean_abs_shap: {top['mean_abs_shap']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing summary without prompting.",
    )
    args = parser.parse_args()

    if EXPLAINABILITY_GLOBAL_FILE.exists() and not args.force:
        print(f"A global summary already exists at {EXPLAINABILITY_GLOBAL_FILE}:")
        print(existing_artifact_summary())
        print("Re-running would overwrite it. Use --force to recompute and replace.")
        return 1

    model = load_selected_model()
    X_val, _, _ = baseline.load_split("validation")
    groups = explainability._feature_groups()

    masker = shap.maskers.Independent(
        explainability._load_background(), max_samples=100
    )
    explainer = shap.LinearExplainer(model, masker)
    shap_values = explainer.shap_values(X_val)
    print(f"Computed SHAP values: {shap_values.shape}")

    features = []
    for feature, start, count in groups:
        row_contributions = shap_values[:, start : start + count].sum(axis=1)
        features.append(
            {
                "feature": feature,
                "mean_abs_shap": float(np.abs(row_contributions).mean()),
                "mean_shap": float(row_contributions.mean()),
            }
        )
    features.sort(key=lambda row: -row["mean_abs_shap"])

    summary = {
        "artifact": {
            "created": date.today().isoformat(),
            "description": (
                "Global SHAP feature importance for the selected Logistic "
                "Regression, aggregated from transformed features back to the "
                "original clinical inputs. Aggregates only; no patient data."
            ),
            "version": EXPLAINABILITY_GLOBAL_VERSION,
        },
        "model": {"name": "Logistic Regression (selected)", "version": SELECTED_MODEL_VERSION},
        "dataset": {
            "name": DATASET_NAME,
            "dataset_version": "phase7-preprocessing-v1.0.0",
            "validation_rows": int(len(X_val)),
        },
        "explainer": {
            "name": "LinearExplainer (interventional, exact for linear models)",
            "output_space": "log-odds (decision function of the selected model)",
            "background": (
                f"first 100 rows of the validation partition "
                f"(mean log-odds {float(explainer.expected_value):.6f})"
            ),
        },
        "features": features,
        "note": (
            "mean_abs_shap is the mean absolute SHAP contribution per original "
            "feature; mean_shap is the mean signed contribution. Values are in "
            "log-odds units of the underlying model. SHAP explains model "
            "behaviour; it does not establish clinical causation, and the "
            "displayed probability is calibrated after the model output."
        ),
    }

    EXPLAINABILITY_GLOBAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = EXPLAINABILITY_GLOBAL_FILE.with_name(f".{EXPLAINABILITY_GLOBAL_FILE.name}.tmp")
    try:
        temp.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(EXPLAINABILITY_GLOBAL_FILE)
    finally:
        temp.unlink(missing_ok=True)

    print("\nGlobal explainability summary complete.")
    print(f"Version: {summary['artifact']['version']}")
    print(f"File: {EXPLAINABILITY_GLOBAL_FILE}")
    for row in features[:5]:
        print(
            f"  {row['feature']:<20} mean_abs_shap={row['mean_abs_shap']:.6f} "
            f"mean_shap={row['mean_shap']:+.6f}"
        )
    print("\nSHAP explains model behaviour; it does not establish clinical causation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
