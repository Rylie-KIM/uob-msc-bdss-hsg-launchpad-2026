"""
Per-user sleep quality model.

train_from_samples(user_id, samples) — called by sleep_predictor after HealthKit sync.
  - samples: list of training_samples rows from Supabase
  - trains a GradientBoostingRegressor
  - saves model to ml/model_store/{user_id}.pkl
  - returns the fitted model

Feature vector (10 features, order must match _sample_to_feature_vector in sleep_predictor.py):
  0  estimated_duration_hours
  1  steps_daytime
  2  day_of_week
  3  active_energy_kcal
  4  avg_step_length_cm
  5  flights_climbed
  6  headphone_audio_evening_db
  7  environmental_audio_night_db
  8  walking_distance_metres
  9  basal_energy_kcal

Target: quality_label (0–100)
  - diary: sleep_quality (1–5) × 20
  - healthkit only: heuristic from duration
"""

import pickle
import numpy as np
from pathlib import Path
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

MODEL_DIR = Path(__file__).parent / "model_store"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_NAMES = [
    "estimated_duration_hours",
    "steps_daytime",
    "day_of_week",
    "active_energy_kcal",
    "avg_step_length_cm",
    "flights_climbed",
    "headphone_audio_evening_db",
    "environmental_audio_night_db",
    "walking_distance_metres",
    "basal_energy_kcal",
]


def _row_to_vector(s: dict) -> list[float]:
    return [float(s.get(f) or 0) for f in FEATURE_NAMES]


def train_from_samples(user_id: str, samples: list[dict]) -> GradientBoostingRegressor:
    """
    Train a per-user model from training_samples rows.
    Diary-sourced labels are weighted more heavily than HealthKit-estimated labels.
    """
    X, y, weights = [], [], []

    for s in samples:
        label = s.get("quality_label")
        if label is None:
            continue
        X.append(_row_to_vector(s))
        y.append(float(label))
        # Diary labels are ground truth — weight them 3×
        weights.append(3.0 if s.get("data_source") == "diary" else 1.0)

    if len(X) < 3:
        raise ValueError(f"Not enough training samples: {len(X)} (need at least 3)")

    X = np.array(X)
    y = np.array(y)
    weights = np.array(weights)

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
    )

    if len(X) >= 6:
        X_train, X_test, y_train, y_test, w_train, _ = train_test_split(
            X, y, weights, test_size=0.2, random_state=42
        )
        model.fit(X_train, y_train, sample_weight=w_train)
        mae = mean_absolute_error(y_test, model.predict(X_test))
        print(f"[{user_id[:8]}] Trained on {len(X_train)} samples | MAE: {mae:.1f} pts")
    else:
        # Too few samples to split — train on all
        model.fit(X, y, sample_weight=weights)
        print(f"[{user_id[:8]}] Trained on {len(X)} samples (no test split)")

    _save_model(user_id, model)
    return model


def load_user_model(user_id: str) -> GradientBoostingRegressor | None:
    path = MODEL_DIR / f"{user_id}.pkl"
    if not path.exists():
        return None
    with open(path, "rb") as fh:
        return pickle.load(fh)


def _save_model(user_id: str, model: GradientBoostingRegressor):
    path = MODEL_DIR / f"{user_id}.pkl"
    with open(path, "wb") as fh:
        pickle.dump(model, fh)
    print(f"Saved model → {path}")
