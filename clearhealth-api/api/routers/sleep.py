from datetime import datetime, timedelta
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from api.services.supabase_client import get_client, verify_user_token
from api.services.sleep_predictor import train_user_model
from api.services.llm_agent import generate_sleep_advice

router = APIRouter()


class SleepDiaryEntry(BaseModel):
    entry_date: str            # YYYY-MM-DD
    bed_time: str | None = None
    sleep_time: str | None = None
    wake_time: str | None = None
    out_of_bed_time: str | None = None
    sleep_quality: int | None = None   # 1–5
    notes: str | None = None


# ---------------------------------------------------------------------------
# POST /api/sleep/diary
# Save diary entry → update training_samples with diary label → retrain model
# ---------------------------------------------------------------------------

@router.post("/sleep/diary")
def save_sleep_diary(entry: SleepDiaryEntry, x_user_token: str = Header(...)):
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()

    # 1. Save diary entry
    db.table("sleep_diary").upsert({
        "user_id": user_id,
        **entry.model_dump(),
    }).execute()

    # 2. If sleep_time + wake_time are provided, upgrade the training_samples row
    #    for this date to use diary labels (higher quality ground truth)
    if entry.sleep_time and entry.wake_time:
        duration = _calc_duration(entry.sleep_time, entry.wake_time)
        update_fields: dict = {
            "sleep_start": entry.sleep_time,
            "wake_time": entry.wake_time,
            "estimated_duration_hours": duration,
            "data_source": "diary",
        }
        if entry.sleep_quality:
            update_fields["quality_label"] = float(entry.sleep_quality * 20)

        existing = (
            db.table("training_samples")
            .select("id")
            .eq("user_id", user_id)
            .eq("sample_date", entry.entry_date)
            .execute()
        )
        if existing.data:
            db.table("training_samples").update(update_fields).eq(
                "user_id", user_id
            ).eq("sample_date", entry.entry_date).execute()

            # 3. Retrain immediately with the improved label
            train_user_model(user_id, db)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /api/sleep/prediction/{user_id}
# Return latest prediction (computed by HealthKit sync or diary update)
# ---------------------------------------------------------------------------

@router.get("/sleep/prediction/{user_id}")
def get_prediction(user_id: str, x_user_token: str = Header(...)):
    try:
        token_user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if token_user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db = get_client()

    # Return the most recent prediction (HealthKit sync writes this daily at 18:00)
    result = (
        db.table("sleep_predictions")
        .select("*")
        .eq("user_id", user_id)
        .order("prediction_date", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return {"message": "No prediction yet — sync HealthKit data first (run the Shortcut)"}

    prediction = result.data[0]

    # Attach LLM advice if score is poor and not already stored
    if not prediction.get("llm_advice") and (prediction.get("sleep_score") or 100) < 65:
        recent = (
            db.table("sleep_predictions")
            .select("sleep_score, estimated_duration_hours")
            .eq("user_id", user_id)
            .order("prediction_date", desc=True)
            .limit(7)
            .execute()
        )
        scores = [r["sleep_score"] for r in (recent.data or []) if r.get("sleep_score")]
        avg_score = sum(scores) / len(scores) if scores else prediction["sleep_score"]
        durations = [r["estimated_duration_hours"] for r in (recent.data or []) if r.get("estimated_duration_hours")]
        avg_dur = sum(durations) / len(durations) if durations else None

        profile = db.table("user_profiles").select("is_international_student").eq("id", user_id).execute()
        is_intl = profile.data[0].get("is_international_student", False) if profile.data else False

        advice = generate_sleep_advice(user_id, {
            "avg_score": round(avg_score, 1),
            "avg_duration_hours": avg_dur,
            "is_international": is_intl,
            "poor_days": sum(1 for s in scores if s < 50),
        })
        db.table("sleep_predictions").update({"llm_advice": advice}).eq(
            "id", prediction["id"]
        ).execute()
        prediction["llm_advice"] = advice

    return prediction


# ---------------------------------------------------------------------------
# GET /api/sleep/history/{user_id}
# Return last 14 nights for chart display
# ---------------------------------------------------------------------------

@router.get("/sleep/history/{user_id}")
def get_sleep_history(user_id: str, x_user_token: str = Header(...)):
    try:
        token_user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if token_user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db = get_client()
    result = (
        db.table("sleep_predictions")
        .select("prediction_date, sleep_score, estimated_duration_hours, risk_level, data_source")
        .eq("user_id", user_id)
        .order("prediction_date", desc=True)
        .limit(14)
        .execute()
    )
    return result.data or []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calc_duration(sleep_time: str, wake_time: str) -> float | None:
    try:
        s = datetime.fromisoformat(sleep_time)
        w = datetime.fromisoformat(wake_time)
        if w < s:
            w += timedelta(days=1)
        return round((w - s).total_seconds() / 3600, 2)
    except Exception:
        return None
