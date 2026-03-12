from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from api.services.supabase_client import get_client, verify_user_token

router = APIRouter()


class UserProfile(BaseModel):
    university_name: str | None = None
    year_of_study: int | None = None
    is_international_student: bool = False
    usual_sleep_hours: float | None = None
    has_sleep_issues: bool = False
    usual_bedtime: str | None = None       # HH:MM format
    usual_wake_time: str | None = None     # HH:MM format
    healthkit_consent: bool = False


@router.post("/profile")
def save_profile(profile: UserProfile, x_user_token: str = Header(...)):
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()
    db.table("user_profiles").upsert({
        "id": user_id,
        **profile.model_dump(),
    }).execute()

    return {"status": "ok"}


@router.get("/profile")
def get_profile(x_user_token: str = Header(...)):
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()
    result = db.table("user_profiles").select("*").eq("id", user_id).single().execute()
    return result.data
