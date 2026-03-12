from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from api.services.supabase_client import get_client, verify_user_token

router = APIRouter()


class AlertRequest(BaseModel):
    student_id: str
    triggered_by: str
    risk_level: str
    message: str | None = None


@router.post("/alert")
def create_alert(body: AlertRequest, x_user_token: str = Header(...)):
    try:
        verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()
    db.table("staff_alerts").insert({
        "student_id": body.student_id,
        "triggered_by": body.triggered_by,
        "risk_level": body.risk_level,
        "message": body.message,
    }).execute()

    return {"status": "ok"}


@router.get("/alerts")
def get_alerts(x_user_token: str = Header(...)):
    """Staff only — get unresolved alerts."""
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()

    # Verify staff role
    profile = db.table("user_profiles").select("role").eq("id", user_id).execute()
    if not profile.data or profile.data[0].get("role") != "staff":
        raise HTTPException(status_code=403, detail="Staff only")

    result = (
        db.table("staff_alerts")
        .select("*")
        .eq("resolved", False)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


@router.patch("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str, x_user_token: str = Header(...)):
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()

    profile = db.table("user_profiles").select("role").eq("id", user_id).execute()
    if not profile.data or profile.data[0].get("role") != "staff":
        raise HTTPException(status_code=403, detail="Staff only")

    db.table("staff_alerts").update({"resolved": True}).eq("id", alert_id).execute()
    return {"status": "ok"}
