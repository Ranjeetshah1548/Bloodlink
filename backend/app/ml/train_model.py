"""
Trains the Random Forest donor response-likelihood model and saves it with
joblib to model.pkl, alongside a small metadata JSON with evaluation
metrics. Run directly:

    python -m app.ml.train_model

or, to retrain with a real historical dataset once you have one:

    python -m app.ml.train_model --csv path/to/real_donor_responses.csv
"""
import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)

from app.ml.generate_training_data import generate_dataset, FEATURE_COLUMNS, TARGET_COLUMN

MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / "model.pkl"
METADATA_PATH = MODEL_DIR / "model_metadata.json"


def load_dataset(csv_path: str | None) -> pd.DataFrame:
    if csv_path:
        df = pd.read_csv(csv_path)
        missing = set(FEATURE_COLUMNS + [TARGET_COLUMN]) - set(df.columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")
        return df
    return generate_dataset()


def train(csv_path: str | None = None) -> dict:
    df = load_dataset(csv_path)

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred), 4),
        "recall": round(recall_score(y_test, y_pred), 4),
        "f1": round(f1_score(y_test, y_pred), 4),
        "roc_auc": round(roc_auc_score(y_test, y_proba), 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "feature_importances": dict(
            sorted(
                zip(FEATURE_COLUMNS, [round(v, 4) for v in model.feature_importances_]),
                key=lambda kv: kv[1], reverse=True,
            )
        ),
        "trained_on": "synthetic" if not csv_path else f"real_data:{csv_path}",
        "feature_order": FEATURE_COLUMNS,
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_order": FEATURE_COLUMNS}, MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(metrics, indent=2))

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to a real historical donor-response CSV to train on instead of synthetic data")
    args = parser.parse_args()

    result = train(args.csv)
    print(json.dumps(result, indent=2))
    print(f"\nModel saved to {MODEL_PATH}")
