# ClearHealth — Sleep Disorder Support Platform
> MSc Data Science team | HSG Launchpad 2026

**B2B mental health platform for UK universities. Prevents student dropout caused by sleep disorders.**

---

## Quick Start (Demo Setup)

### Prerequisites
- Python 3.11+
- ngrok account (free tier)
- Supabase project (free tier)
- Anthropic API key

---

## Step 1 — Environment Setup

```bash
cd clearhealth-api
cp .env.example .env
```

Edit `.env`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-service-role-key     # Settings → API → service_role
OPEN_AI_API_KEY=sk-ant-...
APP_SECRET=any-random-string
```

---

## Step 2 — Supabase Database

1. Go to **Supabase Dashboard → SQL Editor**
2. Paste the entire contents of `docs/scripts/database_schema.sql`
3. Click **Run**

This creates all tables: `user_profiles`, `sleep_diary`, `training_samples`, `sleep_predictions`, `chat_sessions`, `chat_messages`, `social_posts`, `social_comments`, `staff_alerts`

---

## Step 3 — Install & Run the API

```bash
cd clearhealth-api

# Install Python dependencies
pip install -r requirements.txt

# Seed CBT-i knowledge base into ChromaDB (first time only, takes ~10 seconds)
python rag/cbti_loader.py

# Start the API server
uvicorn main:app --reload --port 8000
```

API is now running at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

---

## Step 4 — Expose to Internet (ngrok)

Open a new terminal:
```bash
ngrok http 8000
```

Copy the HTTPS URL shown (e.g. `https://abc123.ngrok-free.app`) — this is your `API_BASE_URL`.

You need this for:
- iOS Shortcut → HealthKit sync
- Lovable UI → API calls

---

## Step 5 — iOS Shortcut (HealthKit Sync)

> Syncs Yeon's iPhone health data to the API daily at 18:00

See full instructions: **`docs/healthkit_guide.md`**

**Summary:**
1. Open **Shortcuts** app on iPhone
2. Create shortcut "ClearHealth — Sync" with 16 actions (8× Find Health Samples → POST pairs)
3. Set Automation → **6:00 PM daily** → runs the shortcut automatically
4. First run: 6 weeks of data synced → model trained → prediction stored

After running, check `http://localhost:8000/docs` → `GET /api/sleep/prediction/{user_id}` for result.

---

## Step 6 — Lovable UI

See **`docs/lovable_guide.md`** for full Lovable prompts.

In Lovable, set environment variable:
```
VITE_API_BASE=https://abc123.ngrok-free.app
```

---

## Demo Day Checklist

```
□ .env filled in with real keys
□ Supabase schema created (Step 2)
□ pip install -r requirements.txt done
□ python rag/cbti_loader.py done (once)
□ uvicorn main:app --port 8000 running
□ ngrok http 8000 running
□ ngrok URL updated in iPhone Shortcut
□ iPhone Shortcut run manually → check /docs for prediction
□ Lovable UI connected to ngrok URL
```

---

## Project Structure

```
clearhealth-api/        ← Python FastAPI backend
docs/
  app_structure.md      ← API endpoints reference
  healthkit_guide.md    ← iOS Shortcut setup (HealthKit → API)
  scripts/
    database_schema.sql ← Paste into Supabase SQL Editor
```

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |
| POST | `/api/profile` | Save onboarding data |
| GET | `/api/profile` | Get user profile |
| POST | `/api/chat` | Claude chatbot (CBT-i RAG + safety) |
| GET | `/api/chat/history/{user_id}` | Chat history |
| POST | `/api/sleep/diary` | Save sleep diary + retrain model |
| GET | `/api/sleep/prediction/{user_id}` | Latest sleep score (0–100) |
| GET | `/api/sleep/history/{user_id}` | 14-night history for chart |
| POST | `/api/healthkit/sync` | HealthKit data sync (×8, auto-trains) |
| POST | `/api/alert` | Create staff alert |
| GET | `/api/alerts` | Staff: unresolved alerts |
| PATCH | `/api/alerts/{id}/resolve` | Staff: resolve alert |

Full interactive docs: `http://localhost:8000/docs`


To run the backend right now:                       
                                                     
  # 1. Fill in your .env                           
  cd clearhealth-api && cp .env.example .env          
  # Open .env and enter SUPABASE_URL, 
  SUPABASE_SECRET_KEY, ANTHROPIC_API_KEY, OPEN_AI_API_KEY             
                                                    
  # 2. Paste docs/scripts/database_schema.sql into    
  Supabase SQL Editor and Run                       

  # 3. Start the server
  pip install -r requirements.txt
  python rag/cbti_loader.py   # first time only
  uvicorn main:app --reload --port 8000

  # 4. In a new terminal
  ngrok http 8000

  Then open http://localhost:8000/docs to test all API
   endpoints interactively.

  The README.md now has the full step-by-step
  instructions in English — Steps 1 through 6 covering
   environment setup, Supabase schema, server startup,
   ngrok, iOS Shortcut, and Lovable UI connection,
  plus a Demo Day checklist.