# Python Backend — Application Structure
> FastAPI backend for ClearHealth mental health platform

---

## Directory Structure

```
clearhealth-api/
│
├── main.py                     # FastAPI app entry point, CORS, router registration
├── requirements.txt
├── .env                        # API keys, Supabase URL (never commit this)
├── .env.example                # Template for .env
│
├── api/
│   ├── __init__.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py             # POST /api/profile, GET /api/profile
│   │   ├── chat.py             # POST /api/chat, GET /api/chat/history/{user_id}
│   │   ├── sleep.py            # POST /api/sleep/diary, GET /api/sleep/prediction/{user_id}, GET /api/sleep/history/{user_id}
│   │   ├── healthkit.py        # POST /api/healthkit/sync (×8, auto-trains on last)
│   │   └── alerts.py           # POST /api/alert, GET /api/alerts, PATCH /api/alerts/{id}/resolve
│   │
│   └── services/
│       ├── __init__.py
│       ├── llm_agent.py        # Claude API calls, safety guardrails, sleep advice generation
│       ├── sleep_predictor.py  # Night processing, feature extraction, ML training pipeline
│       └── supabase_client.py  # Supabase client singleton + JWT verification
│
├── ml/
│   ├── __init__.py
│   ├── sleep_model.py          # GradientBoostingRegressor per-user model, train/load/save
│   ├── features.py             # Feature name constants (10 features)
│   └── model_store/            # Saved .pkl files (one per user_id)
│
├── rag/
│   ├── __init__.py
│   ├── cbti_loader.py          # Load CBT-i knowledge into ChromaDB (8 built-in modules + PDFs)
│   ├── vector_store.py         # ChromaDB wrapper (add_documents, query, is_empty)
│   └── cbti_docs/              # Drop CBT-i PDF/txt files here
│
└── tests/
    ├── test_chat.py
    ├── test_sleep.py
    └── test_healthkit.py
```

---

## API Endpoints

### Auth / Profile
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/profile` | Save onboarding answers to Supabase `user_profiles` |
| GET | `/api/profile` | Retrieve own profile |

### Chatbot
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message → Claude response with CBT-i RAG + safety guardrails |
| GET | `/api/chat/history/{user_id}` | Last 10 chat sessions |

### Sleep
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sleep/diary` | Save diary entry; if sleep_time+wake_time provided, updates `training_samples` and retrains model |
| GET | `/api/sleep/prediction/{user_id}` | Latest sleep score from `sleep_predictions` (computed by HealthKit sync at 18:00) |
| GET | `/api/sleep/history/{user_id}` | Last 14 nights for chart |

### HealthKit
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/healthkit/sync` | Receive one data type at a time (iOS Shortcut calls ×8). Buffers in memory. When all 8 types arrive, auto-processes nights → trains model → saves to `sleep_predictions` |

### Alerts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/alert` | Create staff alert (triggered internally by sleep_predictor on critical risk) |
| GET | `/api/alerts` | Staff only — unresolved alerts |
| PATCH | `/api/alerts/{alert_id}/resolve` | Staff only — mark resolved |

---

## Data Flow

```
Daily 18:00 (iOS Shortcut Automation)
  iPhone HealthKit (6 weeks)
    → POST /api/healthkit/sync ×8 (one per data type)
        → in-memory buffer per user
            → 8th type received: auto-triggers pipeline
                → process_nights_from_memory()
                    → groups step data into 18:00→06:00 night windows
                    → checks sleep_diary (diary labels take priority 3×)
                    → upserts features into training_samples (one row/night)
                → train_user_model()
                    → reads training_samples
                    → GradientBoostingRegressor per user
                    → saves model to ml/model_store/{user_id}.pkl
                    → predicts tonight's sleep quality
                    → upserts to sleep_predictions
                    → staff alert if risk = "critical"

Student writes diary entry
  → POST /api/sleep/diary
      → saves to sleep_diary
      → updates training_samples row with diary label
      → retrains model immediately
```

---

## Key Libraries

```
fastapi>=0.110.0
uvicorn>=0.27.0
python-dotenv>=1.0.0
supabase>=2.3.0
anthropic>=0.40.0
langchain>=0.1.0
chromadb>=0.4.0
scikit-learn>=1.4.0
pandas>=2.2.0
numpy>=1.26.0
pydantic>=2.0.0
httpx>=0.27.0
pypdf>=4.0.0
```

---

## Environment Variables (.env)

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-service-key
ANTHROPIC_API_KEY=your-anthropic-key
OPEN_AI_API_KEY=
APP_SECRET=your-random-secret
```

---

## How to Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Seed RAG knowledge base (first time only)
cd clearhealth-api && python rag/cbti_loader.py

# Start API server
uvicorn main:app --reload --port 8000

# Expose to internet (for HealthKit + Lovable)
ngrok http 8000
```

API docs: `http://localhost:8000/docs`

---

## Notes

- **Social Page** — Lovable queries Supabase directly (no Python API needed)
- **Auth / Sign-up** — Supabase Auth from Lovable; Python only saves profile data
- **HealthKit buffer** — in-memory only (not saved to DB); cleared after each successful 8-type sync
- **Model store** — one `.pkl` file per user in `ml/model_store/`. Min 3 nights of data to train.
- **Diary priority** — diary-sourced training labels are weighted 3× over HealthKit-estimated labels
