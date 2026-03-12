import os
import sys
from pathlib import Path
from openai import OpenAI
from .supabase_client import get_client

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag"))
from vector_store import query as rag_query

SAFETY_KEYWORDS = [
    "kill myself", "end my life", "don't want to live", "dont want to live",
    "suicidal", "self harm", "self-harm", "hurt myself", "not worth living",
    "want to die", "no point going on", "end it all", "take my own life",
]

SAFETY_RESPONSE = (
    "I'm really glad you felt able to share that with me. "
    "Please reach out for immediate support right now:\n\n"
    "• **Samaritans**: 116 123 (free, 24/7)\n"
    "• **Crisis text**: text SHOUT to 85258\n"
    "• **Your university counselling service**\n"
    "• **Emergency**: call 999\n\n"
    "You matter, and there are people who want to help."
)

SYSTEM_PROMPT = """You are a sleep support companion for ClearHealth, a mental health platform for UK university students.

You are trained on Cognitive Behavioural Therapy for Insomnia (CBT-i) principles and NHS sleep health guidelines.

YOUR ROLE:
- Provide evidence-based sleep hygiene advice based on CBT-i
- Help students identify patterns affecting their sleep
- Offer practical, actionable suggestions for improving sleep quality
- Be empathetic, non-judgemental, and supportive
- Encourage sleep diary tracking and pattern awareness

STRICT RULES — NEVER VIOLATE:
1. NEVER make a medical diagnosis
2. NEVER recommend specific medications or dosages
3. NEVER dismiss or minimise distress — validate feelings first
4. If self-harm or suicidal thoughts are mentioned: immediately provide crisis resources (Samaritans 116 123, text SHOUT to 85258, 999 for emergencies)
5. NEVER encourage harmful behaviours
6. NEVER claim to be a human, doctor, therapist, or counsellor
7. Keep responses to 2-4 sentences unless explaining a technique

TONE: Warm, calm, encouraging. Non-clinical language. Use "we" framing.

CBT-i TECHNIQUES YOU KNOW:
- Sleep restriction, stimulus control, sleep hygiene, relaxation, cognitive restructuring, sleep diary"""


def is_safety_flagged(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in SAFETY_KEYWORDS)


def get_chat_response(user_id: str, session_id: str, message: str, history: list[dict]) -> dict:
    if is_safety_flagged(message):
        _save_messages(user_id, session_id, message, SAFETY_RESPONSE, safety_flagged=True)
        return {"reply": SAFETY_RESPONSE, "safety_flagged": True, "session_id": session_id}

    client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"])

    # Pull relevant CBT-i knowledge from ChromaDB
    try:
        rag_chunks = rag_query(message, n_results=3)
        rag_context = "\n\n".join(rag_chunks) if rag_chunks else ""
    except Exception:
        rag_context = ""

    system = SYSTEM_PROMPT
    if rag_context:
        system += f"\n\nRELEVANT CBT-i KNOWLEDGE:\n{rag_context}"

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=512,
        messages=messages,
    )

    reply = response.choices[0].message.content
    _save_messages(user_id, session_id, message, reply, safety_flagged=False)
    return {"reply": reply, "safety_flagged": False, "session_id": session_id}


def generate_sleep_advice(user_id: str, sleep_summary: dict) -> str:
    client = OpenAI(api_key=os.environ["OPEN_AI_API_KEY"])

    prompt = f"""A university student's sleep data this week:
- Average sleep duration: {sleep_summary.get('avg_duration_hours', 'unknown')} hours
- Average sleep score: {sleep_summary.get('avg_score', 'unknown')}/100
- Is international student: {sleep_summary.get('is_international', False)}
- Days with poor sleep (score < 50): {sleep_summary.get('poor_days', 0)}

Write a short, warm, 3-4 sentence personalised sleep advice message based on this data.
Focus on one specific CBT-i technique they could try. Be encouraging, not clinical."""

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _save_messages(user_id: str, session_id: str, user_msg: str, assistant_msg: str, safety_flagged: bool):
    db = get_client()
    rows = [
        {"session_id": session_id, "user_id": user_id, "role": "user", "content": user_msg, "safety_flagged": False},
        {"session_id": session_id, "user_id": user_id, "role": "assistant", "content": assistant_msg, "safety_flagged": safety_flagged},
    ]
    db.table("chat_messages").insert(rows).execute()
