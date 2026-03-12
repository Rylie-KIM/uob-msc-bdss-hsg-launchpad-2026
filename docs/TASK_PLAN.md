# ClearHealth — Task Plan
> Mental Health Platform | HSG Launchpad 2026
> Deadline: Friday midnight (UK) | Pitch: Saturday 1–6:30pm

---

## Confirmation Required First
Before implementation begins, confirm:
- [ ] Review `docs/app_structure.md` → approve Python backend structure
- [ ] Review `docs/database_schema.sql` → approve DB schema, then paste into Supabase SQL editor
- [ ] Review `docs/healthkit_guide.md` → set up HealthKit data pipeline on Yeon's iPhone
- [ ] Review `docs/lovable_guide.md` → use prompts inside Lovable AI

**Say "start" only after all confirmations are done.**

---

## Phase 0 — Infrastructure Setup
> Do this first before any coding

| # | Task | Owner | Tool |
|---|------|-------|------|
| 0.1 | Create Supabase project, paste `database_schema.sql` | All | Supabase |
| 0.2 | Create Python project structure (see `docs/app_structure.md`) | Dev | Local |
| 0.3 | Install dependencies: `pip install -r requirements.txt` | Dev | Terminal |
| 0.4 | Set up `.env` file with Supabase URL/key, AI API key | Dev | Local |
| 0.5 | Start ngrok tunnel: `ngrok http 8000` | Dev | ngrok |
| 0.6 | Create Lovable project, connect to Supabase | UI | Lovable |

**Estimated time: 1–2 hours**

---

## Phase 1 — Auth & Sign-up
> Supabase Auth + onboarding questionnaire

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 1.1 | Supabase Auth: email/password sign-up | Lovable | Built-in Supabase Auth |
| 1.2 | Onboarding questionnaire UI (6–8 questions) | Lovable | See questions below |
| 1.3 | Data sharing agreement / consent page | Lovable | GDPR-compliant text |
| 1.4 | Save questionnaire answers to `user_profiles` table | Lovable → Supabase | Direct Supabase client |
| 1.5 | `POST /api/profile` endpoint in Python (optional fallback) | Python | FastAPI |

**Questionnaire questions:**
1. University name
2. Year of study
3. Are you an international student? (Y/N)
4. How many hours of sleep do you usually get?
5. Do you have trouble falling asleep or staying asleep?
6. What time do you usually go to bed / wake up?
7. Do you consent to sharing Apple Health walking data?

**Estimated time: 2–3 hours**

---

## Phase 2 — LLM Chatbot (CBT-i RAG Agent)
> Main feature: mental health support chat

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 2.1 | Collect CBT-i PDF/text documents | Team | Free NHS/NICE resources |
| 2.2 | Build RAG pipeline: chunk → embed → store in vector DB | Python | `rag/cbti_loader.py` |
| 2.3 | `POST /api/chat` endpoint with safety guardrails | Python | `api/routers/chat.py` |
| 2.4 | Chat UI (message bubbles, input box) | Lovable | Connect to `/api/chat` |
| 2.5 | Save chat sessions to `chat_sessions` table | Python | `api/services/llm_agent.py` |

**Safety rules (hardcoded in system prompt):**
- Never make a diagnosis
- Never suggest medication
- If self-harm mentioned → redirect to Samaritans (116 123) and campus GP
- Always frame as "support tool, not a doctor"

**See `docs/llm_safety_instructions.md` for full system prompt**

**Estimated time: 3–4 hours**

---

## Phase 3 — Sleep Pattern Prediction (ML + HealthKit)
> Personalised sleep tracking using walking data from iPhone

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 3.1 | Set up HealthKit → ngrok pipeline (see `docs/healthkit_guide.md`) | Yeon | iPhone + Shortcuts app |
| 3.2 | `POST /api/healthkit` endpoint to receive walking data | Python | `api/routers/healthkit.py` |
| 3.3 | Walking-stop logic: "in bed" = walking stopped for 20+ mins | Python | `api/services/sleep_predictor.py` |
| 3.4 | Sleep diary input form (bed time, wake time, notes) | Lovable | Connect to `/api/sleep/diary` |
| 3.5 | `POST /api/sleep/diary` to save diary to Supabase | Python | `api/routers/sleep.py` |
| 3.6 | ML model: predict sleep quality score from features | Python | `ml/sleep_model.py` |
| 3.7 | `GET /api/sleep/prediction` endpoint | Python | Returns score + advice |
| 3.8 | Sleep dashboard UI: chart + prediction card + diary | Lovable | Connect to prediction API |
| 3.9 | LLM analysis of sleep pattern (weekly summary) | Python | `api/services/llm_agent.py` |

**ML features:**
- `walk_stop_time` → estimated sleep start (from HealthKit)
- `first_walk_time` → estimated wake time (from HealthKit)
- `sleep_duration` → diary or derived
- `steps_daytime` → activity level
- `international_student` → jet lag flag
- `day_of_week`

**Priority:** If HealthKit not ready, use diary input only for demo.

**Estimated time: 4–6 hours**

---

## Phase 4 — Social Page
> No Python API needed — built entirely in Lovable + Supabase

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 4.1 | Posts feed UI (list + create post) | Lovable | Direct Supabase queries |
| 4.2 | Post detail + comments UI | Lovable | Direct Supabase queries |
| 4.3 | Anonymous posting option | Lovable | Toggle in UI |

**Estimated time: 1–2 hours**

---

## Phase 5 — University Staff Dashboard
> One-page monitoring dashboard

| # | Task | Owner | Notes |
|---|------|-------|-------|
| 5.1 | Staff login (separate Supabase role) | Lovable | Supabase RLS |
| 5.2 | Dashboard: list of students + sleep score + alert level | Lovable | Direct Supabase queries |
| 5.3 | `POST /api/alert` endpoint: trigger email when student is high-risk | Python | `api/routers/alerts.py` |
| 5.4 | Email alert (Supabase Edge Function or simple SMTP) | Python/Supabase | On critical risk score |

**Estimated time: 2 hours**

---

## Phase 6 — Demo Prep & Pitch Polish
> Final 4 hours before deadline

| # | Task | Notes |
|---|------|-------|
| 6.1 | Full end-to-end walkthrough on Yeon's iPhone | Fix any broken flows |
| 6.2 | Seed demo data (fake students + sleep scores) in Supabase | Makes dashboard look real |
| 6.3 | Prepare 5-min pitch script using `pitch_deck/outline.md` | |
| 6.4 | Prepare Q&A answers using `qa_prep.md` | BCG, YC, data science Qs |
| 6.5 | Rehearse demo flow: sign up → chat → sleep tracker → social | Keep it under 2 min |

---

## Build Order Summary

```
Phase 0 (Setup) → Phase 1 (Auth) → Phase 2 (Chat) → Phase 3 (Sleep) → Phase 4 (Social) → Phase 5 (Dashboard) → Phase 6 (Demo)
```

Lovable and Python backend can be built in **parallel** once Phase 0 is done.

---

## Documents Checklist
- [ ] `TASK_PLAN.md` — this file
- [ ] `docs/app_structure.md` — Python backend file structure
- [ ] `docs/database_schema.sql` — Supabase SQL schema
- [ ] `docs/healthkit_guide.md` — HealthKit → Python integration steps
- [ ] `docs/lovable_guide.md` — Lovable AI prompts + API integration guide
- [ ] `docs/llm_safety_instructions.md` — LLM system prompt + safety rules
