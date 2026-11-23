"""Inference service for the trained AgriPredict mandi price benchmark model.

Exposes predict() for single-query inference and returns structured dicts
with price estimate, confidence bounds, and honest model metadata.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

import numpy as np
import pandas as pd

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
_MODEL_FILE = os.path.join(_ARTIFACTS_DIR, "mandi_price_model.joblib")
_META_FILE = os.path.join(_ARTIFACTS_DIR, "model_metadata.json")


@lru_cache(maxsize=1)
def _load_pipeline():
    """Load model lazily at first use; cached for reuse."""
    import joblib
    if not os.path.exists(_MODEL_FILE):
        return None
    return joblib.load(_MODEL_FILE)


@lru_cache(maxsize=1)
def _load_metadata() -> dict:
    if not os.path.exists(_META_FILE):
        return {}
    with open(_META_FILE, encoding="utf-8") as f:
        return json.load(f)


def predict(
    commodity: str,
    grade: str,
    state: str,
    district: str,
    market: str,
) -> dict:
    """Return a price benchmark estimate with confidence interval.

    Returns
    -------
    dict with:
        estimated_price  (float | None)   Modal price benchmark in Rs/quintal
        lower_bound      (float)           Estimated floor (−1 std dev)
        upper_bound      (float)           Estimated ceiling (+1 std dev)
        unit             "quintal"
        model_version    str
        limitations      list[str]
        model_available  bool
    """
    pipeline = _load_pipeline()
    meta = _load_metadata()

    if pipeline is None:
        return {
            "estimated_price": None,
            "lower_bound": None,
            "upper_bound": None,
            "unit": "quintal",
            "model_version": "unavailable",
            "limitations": ["Trained model not found. Run apps/api/app/ml/train.py first."],
            "model_available": False,
        }

    row = pd.DataFrame([{
        "Commodity": commodity,
        "Grade": grade,
        "State": state,
        "District": district,
        "Market": market,
    }])

    try:
        pred_log = pipeline.predict(row)[0]
        pred_price = float(np.expm1(pred_log))
    except Exception:
        pred_price = None

    if pred_price is None:
        return {
            "estimated_price": None,
            "lower_bound": None,
            "upper_bound": None,
            "unit": "quintal",
            "model_version": meta.get("model_version", "unknown"),
            "limitations": ["Could not generate estimate for this commodity/market combination."],
            "model_available": True,
        }

    residual_std = meta.get("metrics", {}).get("ml_model", {}).get("residual_std", 0.0)
    lower = max(1.0, pred_price - residual_std)
    upper = pred_price + residual_std

    return {
        "commodity": commodity,
        "grade": grade,
        "state": state,
        "district": district,
        "market": market,
        "estimated_price": round(pred_price, 2),
        "lower_bound": round(lower, 2),
        "upper_bound": round(upper, 2),
        "unit": "quintal",
        "model_version": meta.get("model_version", "v1"),
        "trained_at": meta.get("trained_at"),
        "metrics": meta.get("metrics", {}).get("ml_model"),
        "limitations": meta.get("data_limitations", []),
        "model_available": True,
    }
