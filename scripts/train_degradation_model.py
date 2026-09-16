"""
Train the XGBoost Asset Degradation Velocity model for the TCI.

Specification Section 2 — Asset Degradation Velocity (S_degrad):
    "This is calculated using a predictive machine learning model that estimates
     the Time-To-Failure (TTF) based on historical stress cycles, such as the
     gross million tonnes of traffic carried over that specific track segment."

    Named features (spec Sec 2 table):
      - Cumulative Gross Million Tonnes (GMT)
      - Historical frequency of localised tamping
      - Localised weather extremes (affecting thermal expansion)
      - Asset metallurgical age

    Plus (spec narrative): dynamic load impact of freight trains, environmental
    temperature variations contributing to rail fractures, and the historical
    efficacy of previous maintenance on that track geometry.

IMPORTANT — provenance of the training data.
This script synthesises a physics-informed label from the same degradation
mechanics that drive `AssetConditionTelemetry.risk_index`. It produces a real,
working, inspectable model so the XGBoost code path is exercised end-to-end,
but it is NOT a substitute for real history. For production the model must be
retrained on actual TMS defect logs and USFD history; `build_training_frame()`
accepts a real DataFrame via `--from-csv` for exactly that.

Usage:
    python scripts/train_degradation_model.py
    python scripts/train_degradation_model.py --from-csv data/tci_degradation_history.csv
    python scripts/train_degradation_model.py --samples 20000 --out models/tci_degradation_xgb.model
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_ml.criticality_scorer import TaskCriticalityScorer  # noqa: E402

FEATURE_NAMES: List[str] = TaskCriticalityScorer.DEGRADATION_FEATURE_NAMES
DEFAULT_OUT_PATH = os.path.join("models", "tci_degradation_xgb.model")
DEFAULT_REPORT_PATH = os.path.join("models", "tci_degradation_xgb.report.json")


# ---------------------------------------------------------------------------
# Label model
# ---------------------------------------------------------------------------
def degradation_velocity_label(row: List[float]) -> float:
    """
    Physics-informed degradation velocity in [0, 1].

    Weighting mirrors the domain composite in `AssetConditionTelemetry.risk_index`
    (TQI 0.35 / USFD 0.30 / GMT 0.20 / tamping 0.15) extended with thermal and
    metallurgical-age terms, plus a non-linear interaction for severe flaws on
    heavily loaded track — an IMR defect under high GMT propagates far faster
    than either factor alone would suggest.
    """
    (
        gmt,
        days_since_tamping,
        trc_tqi,
        usfd_code,
        asset_age_years,
        ambient_temp,
        rail_temp,
        rail_delta,
        fog_visibility,
        monsoon_flag,
    ) = row

    g = min(1.0, max(0.0, gmt / 80.0))                  # traffic loading
    d = min(1.0, max(0.0, days_since_tamping / 200.0))  # tamping frequency
    t = min(1.0, max(0.0, trc_tqi / 65.0))              # geometry quality (higher = worse)
    u = min(1.0, max(0.0, usfd_code / 3.0))             # flaw severity
    a = min(1.0, max(0.0, asset_age_years / 40.0))      # metallurgical age
    th = min(1.0, abs(rail_delta) / 28.0)               # thermal expansion stress

    base = (
        0.20 * g
        + 0.16 * d
        + 0.18 * t
        + 0.20 * u
        + 0.10 * a
        + 0.08 * th
        + 0.05 * monsoon_flag
    )

    # Non-linear interaction: severe flaw on a heavily loaded segment.
    if usfd_code >= 2.0 and g > 0.60:
        base += 0.08

    # Winter rail contraction also drives fracture risk, not just summer heat.
    if rail_delta < -15.0 and u > 0.0:
        base += 0.03

    return max(0.02, min(0.98, base))


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------
def synthesise_frame(n_samples: int, seed: int = 42) -> Tuple[List[List[float]], List[float]]:
    """Deterministic sample of the Indian Railways operating envelope."""
    rng = random.Random(seed)
    X: List[List[float]] = []
    y: List[float] = []

    for _ in range(n_samples):
        ambient = rng.uniform(5.0, 48.0)
        # Rail runs hotter than ambient in sun, cooler at night.
        rail = ambient + rng.uniform(-6.0, 22.0)
        destress = 40.0
        row = [
            rng.uniform(5.0, 90.0),            # cumulative_gmt
            rng.uniform(0.0, 400.0),           # days_since_tamping
            rng.uniform(10.0, 70.0),           # trc_tqi_score
            float(rng.choice([0.0, 0.0, 0.0, 1.0, 1.0, 2.0, 3.0])),  # usfd_severity_code
            rng.uniform(0.0, 45.0),            # asset_age_years
            ambient,
            rail,
            rail - destress,                   # rail_temp_delta_from_destress
            rng.uniform(50.0, 2000.0),         # fog_visibility_meters
            1.0 if rng.random() < 0.18 else 0.0,  # monsoon_flag
        ]
        label = degradation_velocity_label(row)
        # Measurement noise on the observed target.
        label = max(0.0, min(1.0, label + rng.gauss(0.0, 0.03)))
        X.append(row)
        y.append(label)

    return X, y


def load_frame_from_csv(path: str) -> Tuple[List[List[float]], List[float]]:
    """
    Load real historical data.

    Expected columns: the 10 feature names plus a ``degradation_velocity``
    target column in [0, 1].
    """
    import pandas as pd

    df = pd.read_csv(path)
    missing = [c for c in FEATURE_NAMES + ["degradation_velocity"] if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV missing required columns: {missing}")
    df = df.dropna(subset=FEATURE_NAMES + ["degradation_velocity"])
    return df[FEATURE_NAMES].values.tolist(), df["degradation_velocity"].astype(float).tolist()


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------
def train(
    X: List[List[float]],
    y: List[float],
    test_fraction: float = 0.2,
    seed: int = 42,
) -> Tuple[Any, Dict[str, Any]]:
    import numpy as np
    import xgboost as xgb

    arr_x = np.asarray(X, dtype=float)
    arr_y = np.asarray(y, dtype=float)

    n = len(arr_x)
    n_test = max(1, int(round(n * test_fraction)))
    indices = list(range(n))
    random.Random(seed).shuffle(indices)
    test_idx = indices[:n_test]
    train_idx = indices[n_test:]

    params = {
        "max_depth": 5,
        "eta": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "lambda": 1.0,
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "seed": seed,
        "nthread": 1,
    }
    dtrain = xgb.DMatrix(arr_x[train_idx], label=arr_y[train_idx], feature_names=FEATURE_NAMES)
    model = xgb.train(params, dtrain, num_boost_round=400)

    preds = model.predict(
        xgb.DMatrix(arr_x[test_idx], feature_names=FEATURE_NAMES)
    )
    truth = arr_y[test_idx]
    residuals = preds - truth
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((truth - truth.mean()) ** 2))
    metrics = {
        "rmse": round(float(math.sqrt(ss_res / len(truth))), 5),
        "mae": round(float(np.mean(np.abs(residuals))), 5),
        "r2": round(1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0, 5),
        "train_samples": int(len(train_idx)),
        "test_samples": int(len(test_idx)),
    }

    gain_scores = model.get_score(importance_type="gain")
    # Normalise gain to a share so the report is readable regardless of scale.
    total_gain = sum(gain_scores.values()) or 1.0
    metrics["feature_importances"] = {
        name: round(float(gain_scores.get(name, 0.0) / total_gain), 5)
        for name in sorted(FEATURE_NAMES, key=lambda n: gain_scores.get(n, 0.0), reverse=True)
    }
    return model, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=DEFAULT_OUT_PATH)
    parser.add_argument("--report", default=DEFAULT_REPORT_PATH)
    parser.add_argument("--from-csv", default=None, help="Train on real history instead of synthetic data")
    args = parser.parse_args()

    try:
        import xgboost  # noqa: F401
    except ImportError:
        print("ERROR: xgboost is not installed. Run: pip install -r requirements.txt")
        return 1

    if args.from_csv:
        X, y = load_frame_from_csv(args.from_csv)
        source = f"csv:{args.from_csv}"
    else:
        X, y = synthesise_frame(args.samples, seed=args.seed)
        source = f"synthetic:{args.samples}"

    print(f"Training samples: {len(X)}  features: {len(FEATURE_NAMES)}  source: {source}")

    model, metrics = train(X, y, seed=args.seed)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    model.save_model(args.out)

    with open(args.out, "rb") as fh:
        checksum = hashlib.sha256(fh.read()).hexdigest()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_path": args.out,
        "sha256": checksum,
        "feature_names": FEATURE_NAMES,
        "feature_schema_version": TaskCriticalityScorer.FEATURE_SCHEMA_VERSION,
        "training_source": source,
        "metrics": metrics,
        "provenance_note": (
            "Trained on a physics-informed synthetic label derived from IR degradation "
            "mechanics. Retrain on real TMS/USFD history before operational use."
        ),
    }
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(f"Model written to {args.out}")
    print(f"  RMSE {metrics['rmse']}   MAE {metrics['mae']}   R2 {metrics['r2']}")
    print(f"  sha256: {checksum}")
    print("  top features:")
    for name, imp in list(metrics["feature_importances"].items())[:5]:
        print(f"    {name:34s} {imp}")
    print(f"Report written to {args.report}")
    print("")
    print("Add this checksum to config/settings.yaml -> tci.xgboost_model_checksum")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
