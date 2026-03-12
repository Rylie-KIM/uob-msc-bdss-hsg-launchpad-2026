"""
HealthKit routes.

Shortcut sends 8 separate POST /api/healthkit/sync calls (one per data type).
Samples are buffered in memory. When all 8 types arrive, training triggers
automatically — no separate /train endpoint needed.

Daily automation (iOS Shortcut at 18:00):
  Shortcut fetches 6 weeks of data → sends 8 POSTs → last type received
  triggers training on all completed nights (up to and including last night).
  Predicts tonight's expected sleep quality.
"""

from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, model_validator
from typing import Any

from api.services.supabase_client import get_client, verify_user_token
from api.services.sleep_predictor import process_nights_from_memory, train_user_model

router = APIRouter()

VALID_DATA_TYPES = {
    "steps",
    "walking_distance",
    "walking_step_length",
    "active_energy",
    "basal_energy",
    "flights_climbed",
    "headphone_audio",
    "environmental_audio",
}

# ---------------------------------------------------------------------------
# In-memory buffer: {user_id: {data_type: [{"startDate": ..., "value": ...}]}}
# Cleared per-user once all 8 types arrive and training completes.
# ---------------------------------------------------------------------------
_buffers: dict[str, dict[str, list]] = defaultdict(dict)
_lock = Lock()


class HealthSample(BaseModel):
    startDate: str
    value: float

    @model_validator(mode="before")
    @classmethod
    def normalise_shortcuts_fields(cls, data: Any) -> Any:
        """iOS Shortcuts sends 'Start Date' and 'Value' (Title Case)."""
        if not isinstance(data, dict):
            return data
        if "Start Date" in data and "startDate" not in data:
            data["startDate"] = str(data.pop("Start Date")).strip()
        if "Value" in data and "value" not in data:
            data["value"] = data.pop("Value")
        return data


class SyncPayload(BaseModel):
    data_type: str
    samples: list[HealthSample] = []


# ---------------------------------------------------------------------------
# Single endpoint: buffer → auto-train when all 8 types received
# ---------------------------------------------------------------------------

@router.post("/healthkit/sync")
def sync_one_type(body: SyncPayload, x_user_token: str = Header(...)):
    """
    Shortcut calls this once per data type (8 times total at 18:00 daily).

    Each call buffers samples in memory. When the 8th type arrives,
    training runs automatically on completed nights (up to last night).

    Returns:
      - training_triggered: false  → still waiting for more data types
      - training_triggered: true   → all 8 received, trained, prediction included
    """
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if body.data_type not in VALID_DATA_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown data_type: {body.data_type}")

    # Store this data type in user's buffer
    with _lock:
        _buffers[user_id][body.data_type] = [
            {"startDate": s.startDate, "value": s.value}
            for s in body.samples
        ]
        all_received = VALID_DATA_TYPES.issubset(_buffers[user_id].keys())
        if all_received:
            buffer_snapshot = dict(_buffers.pop(user_id))

    if not all_received:
        return {
            "status": "ok",
            "data_type": body.data_type,
            "received": len(body.samples),
            "types_buffered": len(_buffers[user_id]),
            "training_triggered": False,
        }

    # All 8 types received — process nights and train
    db = get_client()
    nights_processed = process_nights_from_memory(user_id, buffer_snapshot, db)
    latest_prediction = train_user_model(user_id, db)

    return {
        "status": "ok",
        "data_type": body.data_type,
        "received": len(body.samples),
        "training_triggered": True,
        "nights_processed": nights_processed,
        "latest_prediction": latest_prediction,
    }
