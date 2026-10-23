"""
Loads the trained Random Forest model (via joblib) and exposes
`predict_response_likelihood`, used by matching_service.py to rank
already-eligible donors. This module NEVER decides blood-group
compatibility - that is handled exclusively by compatibility_service.py.
"""
from pathlib import Path
from functools import lru_cache

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"


class ModelNotTrainedError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_bundle():
    if not MODEL_PATH.exists():
        raise ModelNotTrainedError(
            "No trained model found at app/ml/model.pkl. "
            "Run `python -m app.ml.train_model` first."
        )
    return joblib.load(MODEL_PATH)


def predict_response_likelihood(features: dict) -> float:
    """
    features must contain:
      donor_age, distance_km, is_available, days_since_last_donation,
      previous_requests, previous_accepts, historical_response_rate,
      emergency_level

    Returns a float in [0, 1]: predicted probability the donor responds
    positively. This is a PRIORITIZATION SIGNAL ONLY, never a guarantee.
    """
    bundle = _load_bundle()
    model = bundle["model"]
    feature_order = bundle["feature_order"]

    row = pd.DataFrame([{col: features[col] for col in feature_order}])
    proba = model.predict_proba(row)[0][1]
    return float(round(proba, 4))


def predict_batch(feature_rows: list[dict]) -> list[float]:
    if not feature_rows:
        return []
    bundle = _load_bundle()
    model = bundle["model"]
    feature_order = bundle["feature_order"]

    df = pd.DataFrame([{col: r[col] for col in feature_order} for r in feature_rows])
    probs = model.predict_proba(df)[:, 1]
    return [float(round(p, 4)) for p in probs]
