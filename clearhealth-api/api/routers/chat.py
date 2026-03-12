import uuid
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from api.services.supabase_client import get_client, verify_user_token
from api.services.llm_agent import get_chat_response

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
def chat(body: ChatRequest, x_user_token: str = Header(...)):
    try:
        user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_client()

    # Create session if new
    session_id = body.session_id or str(uuid.uuid4())
    if not body.session_id:
        db.table("chat_sessions").insert({"id": session_id, "user_id": user_id}).execute()

    # Load recent history for context
    history_result = (
        db.table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(20)
        .execute()
    )
    history = history_result.data or []

    result = get_chat_response(user_id, session_id, body.message, history)
    return result


@router.get("/chat/history/{user_id}")
def get_chat_history(user_id: str, x_user_token: str = Header(...)):
    try:
        token_user_id = verify_user_token(x_user_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if token_user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    db = get_client()
    sessions = (
        db.table("chat_sessions")
        .select("id, started_at, message_count")
        .eq("user_id", user_id)
        .order("started_at", desc=True)
        .limit(10)
        .execute()
    )
    return sessions.data or []
