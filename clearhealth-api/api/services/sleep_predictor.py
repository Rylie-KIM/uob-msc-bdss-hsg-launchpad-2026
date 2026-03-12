"""
Sleep prediction service.

Flow (Shortcut sends 8 POSTs at 18:00 daily, training auto-triggers on the last):
  POST /api/healthkit/sync  ×8  → in-memory buffer (per user_id)
  8th type received           → process_nights_from_memory() → train_user_model()

Training data: completed nights only (wake_date <= today).
Tonight's sleep hasn't happened yet — it's predicted, not trained.
"""

import pickle
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from pathlib import Path

MODEL_DIR = Path(__file__).parent.parent.parent / "ml" / "model_store"

# Sleep detection window (UK time): 18:00 → 06:00 next day
# Daytime inactivity (06:00–18:00) is ignored — could be a nap, lecture, etc.
SLEEP_WINDOW_START = 18   # 6pm — earliest plausible bedtime
SLEEP_WINDOW_END = 6      # 6am — latest plausible wake time

INACTIVITY_THRESHOLD_STEPS = 10   # steps/interval below this = inactive
INACTIVITY_MINUTES = 20           # consecutive inactive minutes = asleep

EVENING_START = 20  # 8pm — headphone audio pre-sleep window (until midnight)


# ---------------------------------------------------------------------------
# Entry point 1: convert in-memory buffer dict → process nights
# ---------------------------------------------------------------------------

def process_nights_from_memory(user_id: str, buffer: dict[str, list], db) -> int:
    """
    buffer: {data_type: [{"startDate": "2026-03-11T22:00:00+00:00", "value": 42.0}]}

    Converts to payload-like object, then delegates to process_nights_from_payload.
    Only processes completed nights (wake_date <= today).
    """
    if not buffer.get("steps"):
        return 0

    def _make_samples(data_type: str):
        return [
            type("S", (), {"startDate": r["startDate"], "value": r["value"]})()
            for r in buffer.get(data_type, [])
        ]

    class _Payload:
        pass

    payload = _Payload()
    payload.steps               = _make_samples("steps")
    payload.walking_distance    = _make_samples("walking_distance")
    payload.walking_step_length = _make_samples("walking_step_length")
    payload.active_energy       = _make_samples("active_energy")
    payload.basal_energy        = _make_samples("basal_energy")
    payload.flights_climbed     = _make_samples("flights_climbed")
    payload.headphone_audio     = _make_samples("headphone_audio")
    payload.environmental_audio = _make_samples("environmental_audio")

    return process_nights_from_payload(user_id, payload, db)


# ---------------------------------------------------------------------------
# Entry point 1b: process raw HealthKit payload into training_samples rows
# ---------------------------------------------------------------------------

def process_nights_from_payload(user_id: str, payload, db) -> int:
    """
    Group 6-week HealthKit data into nightly windows (18:00→06:00).
    For each night:
      - extract features from HealthKit data
      - check sleep_diary for that date (diary labels take priority)
      - upsert one row into training_samples
    Returns: number of nights processed.
    """
    # Convert payload into {data_type: DataFrame} for easy slicing
    data = _payload_to_dataframes(payload)

    if data["steps"].empty:
        return 0

    # Determine all unique nights covered by the step data
    nights = _get_night_dates(data["steps"])

    processed = 0
    for night_date in nights:
        row = _build_training_row(user_id, night_date, data, db)
        if row is None:
            continue
        db.table("training_samples").upsert(row).execute()
        processed += 1

    return processed


# ---------------------------------------------------------------------------
# Entry point 2: retrain model and return latest prediction
# ---------------------------------------------------------------------------

def train_user_model(user_id: str, db) -> dict | None:
    """
    Fetch all training_samples for this user, retrain the model,
    save it to disk, run prediction for the most recent night,
    and upsert into sleep_predictions.
    """
    from ml.sleep_model import train_from_samples

    samples_result = (
        db.table("training_samples")
        .select("*")
        .eq("user_id", user_id)
        .order("sample_date", desc=False)
        .execute()
    )
    samples = samples_result.data or []

    if len(samples) < 3:
        return None  # not enough data to train yet

    model = train_from_samples(user_id, samples)

    # Run prediction for the most recent night
    latest = max(samples, key=lambda s: s["sample_date"])
    features = _sample_to_feature_vector(latest)
    score = float(np.clip(model.predict([features])[0], 0, 100))
    risk = _get_risk_level(score)

    prediction = {
        "user_id": user_id,
        "prediction_date": latest["sample_date"],
        "sleep_score": round(score, 2),
        "estimated_sleep_start": latest.get("sleep_start"),
        "estimated_wake_time": latest.get("wake_time"),
        "estimated_duration_hours": latest.get("estimated_duration_hours"),
        "data_source": latest.get("data_source", "healthkit"),
        "risk_level": risk,
    }
    db.table("sleep_predictions").upsert(prediction).execute()

    if risk == "critical":
        db.table("staff_alerts").insert({
            "student_id": user_id,
            "triggered_by": "sleep_prediction",
            "risk_level": "critical",
            "message": f"Sleep score {score:.0f}/100 on {latest['sample_date']}",
        }).execute()

    return prediction


# ---------------------------------------------------------------------------
# Internal: night grouping
# ---------------------------------------------------------------------------

def _get_night_dates(steps_df: pd.DataFrame) -> list[date]:
    """
    Return sorted list of unique 'wake dates' (the morning side of each night).
    Night 18:00→06:00: the wake date = the date of the 06:00 end.
    e.g. 2026-03-11 22:00 → 2026-03-12 05:00 → wake_date = 2026-03-12

    Only returns completed nights (wake_date <= today).
    Tonight's sleep window hasn't finished — it's predicted, not trained.
    """
    today = date.today()
    dates = set()
    for ts in steps_df["time"]:
        h = ts.hour
        if h >= SLEEP_WINDOW_START:
            wake_date = (ts + timedelta(days=1)).date()
        elif h < SLEEP_WINDOW_END:
            wake_date = ts.date()
        else:
            continue  # daytime hours (06:00–18:00) not relevant for night grouping
        if wake_date <= today:  # exclude tomorrow (tonight's wake-up hasn't happened)
            dates.add(wake_date)
    return sorted(dates)


def _build_training_row(user_id: str, night_date: date, data: dict, db) -> dict | None:
    """Build one training_samples row for a given night."""
    start_dt = datetime.combine(night_date - timedelta(days=1), datetime.min.time()).replace(hour=18)
    end_dt = datetime.combine(night_date, datetime.min.time()).replace(hour=6)

    def slice_night(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        return df[(df["time"] >= start_dt) & (df["time"] <= end_dt)]

    steps_night = slice_night(data["steps"])

    # Need at least some step data to determine sleep
    if steps_night.empty:
        return None

    # --- Sleep time labels: diary takes priority over HealthKit ---
    diary = (
        db.table("sleep_diary")
        .select("sleep_time, wake_time, out_of_bed_time, sleep_quality")
        .eq("user_id", user_id)
        .eq("entry_date", night_date.isoformat())
        .execute()
    )
    diary_entry = diary.data[0] if diary.data else None

    if diary_entry and diary_entry.get("sleep_time") and diary_entry.get("wake_time"):
        sleep_start = diary_entry["sleep_time"]
        wake_time = diary_entry["wake_time"]
        duration = _calc_duration(sleep_start, wake_time)
        data_source = "diary"
        diary_quality = diary_entry.get("sleep_quality")
    else:
        # Estimate from HealthKit step data
        times = estimate_sleep_times(
            [{"startDate": row["time"].isoformat(), "value": row["value"]} for _, row in steps_night.iterrows()]
        )
        sleep_start = times["estimated_sleep_start"]
        wake_time = times["estimated_wake_time"]
        duration = times["estimated_duration_hours"]
        data_source = "healthkit"
        diary_quality = None

    if not duration:
        return None

    # --- Features from HealthKit ---
    steps_day = slice_night(data["steps"])  # same as steps_night for simplicity (already filtered to night)
    daytime_steps = data["steps"][
        (data["steps"]["time"].dt.date == (night_date - timedelta(days=1))) &
        (data["steps"]["time"].dt.hour.between(6, 18))
    ]["value"].sum()

    def night_mean(df: pd.DataFrame) -> float:
        s = slice_night(df)
        return float(s["value"].mean()) if not s.empty else 0.0

    def night_sum(df: pd.DataFrame) -> float:
        s = slice_night(df)
        return float(s["value"].sum()) if not s.empty else 0.0

    def daytime_sum(df: pd.DataFrame) -> float:
        prev_day = night_date - timedelta(days=1)
        s = df[(df["time"].dt.date == prev_day) & (df["time"].dt.hour.between(6, 18))]
        return float(s["value"].sum()) if not s.empty else 0.0

    # Headphone audio — evening window (8pm–midnight) only
    headphone_evening = 0.0
    if not data["headphone_audio"].empty:
        hpe = slice_night(data["headphone_audio"])
        hpe = hpe[hpe["time"].dt.hour >= EVENING_START]
        headphone_evening = float(hpe["value"].mean()) if not hpe.empty else 0.0

    # Environmental audio — midnight to 6am (deepest sleep window)
    env_night = 0.0
    if not data["environmental_audio"].empty:
        ea = slice_night(data["environmental_audio"])
        ea = ea[ea["time"].dt.hour < SLEEP_WINDOW_END]
        env_night = float(ea["value"].mean()) if not ea.empty else 0.0

    # Quality label: diary quality * 20, or heuristic from duration
    if diary_quality:
        quality_label = float(diary_quality * 20)
    else:
        quality_label = _heuristic_label(duration)

    return {
        "user_id": user_id,
        "sample_date": night_date.isoformat(),
        "sleep_start": sleep_start,
        "wake_time": wake_time,
        "estimated_duration_hours": duration,
        "steps_daytime": float(daytime_steps),
        "walking_distance_metres": daytime_sum(data["walking_distance"]),
        "avg_step_length_cm": float(data["walking_step_length"]["value"].mean()) if not data["walking_step_length"].empty else 0.0,
        "active_energy_kcal": daytime_sum(data["active_energy"]),
        "basal_energy_kcal": night_sum(data["basal_energy"]),
        "flights_climbed": daytime_sum(data["flights_climbed"]),
        "headphone_audio_evening_db": headphone_evening,
        "environmental_audio_night_db": env_night,
        "day_of_week": (night_date - timedelta(days=1)).weekday(),
        "data_source": data_source,
        "quality_label": quality_label,
    }


# ---------------------------------------------------------------------------
# Sleep time estimation from step data (18:00–06:00 window only)
# ---------------------------------------------------------------------------

def estimate_sleep_times(samples: list[dict]) -> dict:
    """
    Derive sleep start and wake time from step count samples.
    Only looks within the 18:00–06:00 night window.
    Daytime inactivity (06:00–18:00) is ignored.
    """
    empty = {"estimated_sleep_start": None, "estimated_wake_time": None, "estimated_duration_hours": None}
    if not samples:
        return empty

    df = pd.DataFrame(samples)
    df["time"] = pd.to_datetime(df["startDate"])
    df = df.sort_values("time").reset_index(drop=True)
    df["hour"] = df["time"].dt.hour

    # Night window: 18:00–23:59 OR 00:00–05:59
    night = df[(df["hour"] >= SLEEP_WINDOW_START) | (df["hour"] < SLEEP_WINDOW_END)].copy()

    if night.empty:
        return empty

    night = night.reset_index(drop=True)
    night["is_inactive"] = night["value"] < INACTIVITY_THRESHOLD_STEPS

    sleep_start = None
    inactive_since = None

    for _, row in night.iterrows():
        if sleep_start is None:
            if row["is_inactive"]:
                if inactive_since is None:
                    inactive_since = row["time"]
                elapsed = (row["time"] - inactive_since).total_seconds() / 60
                if elapsed >= INACTIVITY_MINUTES:
                    sleep_start = inactive_since
            else:
                inactive_since = None
        else:
            if not row["is_inactive"]:
                wake_time = row["time"]
                duration = round((wake_time - sleep_start).total_seconds() / 3600, 2)
                return {
                    "estimated_sleep_start": sleep_start.isoformat(),
                    "estimated_wake_time": wake_time.isoformat(),
                    "estimated_duration_hours": duration,
                }

    return {
        "estimated_sleep_start": sleep_start.isoformat() if sleep_start else None,
        "estimated_wake_time": None,
        "estimated_duration_hours": None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _payload_to_dataframes(payload) -> dict[str, pd.DataFrame]:
    def to_df(samples: list) -> pd.DataFrame:
        if not samples:
            return pd.DataFrame(columns=["time", "value"])
        rows = [{"time": pd.to_datetime(s.startDate), "value": s.value} for s in samples]
        return pd.DataFrame(rows).sort_values("time").reset_index(drop=True)

    return {
        "steps":               to_df(payload.steps),
        "walking_distance":    to_df(payload.walking_distance),
        "walking_step_length": to_df(payload.walking_step_length),
        "active_energy":       to_df(payload.active_energy),
        "basal_energy":        to_df(payload.basal_energy),
        "flights_climbed":     to_df(payload.flights_climbed),
        "headphone_audio":     to_df(payload.headphone_audio),
        "environmental_audio": to_df(payload.environmental_audio),
    }


def _sample_to_feature_vector(s: dict) -> list:
    return [
        s.get("estimated_duration_hours") or 0,
        s.get("steps_daytime") or 0,
        s.get("day_of_week") or 0,
        s.get("active_energy_kcal") or 0,
        s.get("avg_step_length_cm") or 0,
        s.get("flights_climbed") or 0,
        s.get("headphone_audio_evening_db") or 0,
        s.get("environmental_audio_night_db") or 0,
        s.get("walking_distance_metres") or 0,
        s.get("basal_energy_kcal") or 0,
    ]


def _heuristic_label(duration_hours: float) -> float:
    """Estimate quality label (0–100) from sleep duration alone."""
    if 7 <= duration_hours <= 9:
        return 80.0
    elif 6 <= duration_hours < 7:
        return 65.0
    elif 9 < duration_hours <= 10:
        return 70.0
    elif 5 <= duration_hours < 6:
        return 45.0
    elif duration_hours < 5:
        return 25.0
    return 50.0


def _calc_duration(sleep_time: str, wake_time: str) -> float | None:
    try:
        s = datetime.fromisoformat(sleep_time)
        w = datetime.fromisoformat(wake_time)
        if w < s:
            w += timedelta(days=1)
        return round((w - s).total_seconds() / 3600, 2)
    except Exception:
        return None


def _get_risk_level(score: float) -> str:
    if score >= 70:
        return "low"
    elif score >= 50:
        return "medium"
    elif score >= 30:
        return "high"
    return "critical"


def compute_sleep_score(features: dict) -> float:
    """Fallback heuristic scorer — used by sleep diary POST when no HealthKit data."""
    duration = features.get("estimated_duration_hours") or 0
    label = _heuristic_label(duration)
    diary_q = features.get("sleep_quality")
    if diary_q:
        label = (label + diary_q * 20) / 2
    return float(np.clip(label, 0, 100))


def get_risk_level(score: float) -> str:
    return _get_risk_level(score)
