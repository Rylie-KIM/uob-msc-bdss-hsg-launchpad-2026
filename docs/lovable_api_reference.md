# ClearHealth — API & Database Reference for Lovable

> Feed this entire document to Lovable as context before building the UI.

---

## Overview

- **Base URL (local):** `http://localhost:8000`
- **Base URL (production):** your ngrok HTTPS URL, e.g. `https://xxxx.ngrok-free.app`
- **Auth:** All protected endpoints require a Supabase JWT in the header:
  ```
  X-User-Token: <supabase_access_token>
  ```
- **Content-Type:** `application/json`

---

## Authentication

Auth is handled entirely by **Supabase Auth** on the frontend. After sign-in, pass the `access_token` from the Supabase session as the `X-User-Token` header on every API call.

```js
// Supabase client (frontend)
const { data: { session } } = await supabase.auth.getSession()
const token = session.access_token

// Use in API calls
fetch(`${API_BASE}/api/profile`, {
  headers: { 'X-User-Token': token }
})
```

**User roles:** `student` (default) or `staff`. Staff-only endpoints return `403` for students.

---

## Endpoints

### Health Check

```
GET /health
```
No auth required.

**Response:**
```json
{ "status": "ok" }
```

---

### Profile

#### Save / Update Profile
```
POST /api/profile
X-User-Token: <token>
```

**Request body:**
```json
{
  "university_name": "University of Birmingham",
  "year_of_study": 2,
  "is_international_student": false,
  "usual_sleep_hours": 7.0,
  "has_sleep_issues": true,
  "usual_bedtime": "23:30",
  "usual_wake_time": "07:00",
  "healthkit_consent": false
}
```
All fields are optional. Uses upsert (safe to call on re-onboarding).

**Response:**
```json
{ "status": "ok" }
```

---

#### Get Profile
```
GET /api/profile
X-User-Token: <token>
```

**Response:**
```json
{
  "id": "uuid",
  "university_name": "University of Birmingham",
  "year_of_study": 2,
  "is_international_student": false,
  "usual_sleep_hours": 7.0,
  "has_sleep_issues": true,
  "usual_bedtime": "23:30",
  "usual_wake_time": "07:00",
  "healthkit_consent": false,
  "role": "student",
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-03-10T08:00:00Z"
}
```

---

### Sleep Diary

#### Submit Sleep Diary Entry
```
POST /api/sleep/diary
X-User-Token: <token>
```

**Request body:**
```json
{
  "entry_date": "2026-03-11",
  "bed_time": "2026-03-10T23:00:00",
  "sleep_time": "2026-03-10T23:30:00",
  "wake_time": "2026-03-11T07:00:00",
  "out_of_bed_time": "2026-03-11T07:15:00",
  "sleep_quality": 3,
  "notes": "Woke up once at 3am"
}
```

- `entry_date`: YYYY-MM-DD (required)
- `sleep_quality`: integer 1–5 (1=very poor, 5=excellent)
- All time fields: ISO 8601 datetime string (optional)
- Submitting `sleep_time` + `wake_time` triggers automatic ML model retraining

**Response:**
```json
{ "status": "ok" }
```

---

### Sleep Prediction

#### Get Latest Sleep Score
```
GET /api/sleep/prediction/{user_id}
X-User-Token: <token>
```

**Response (prediction exists):**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "prediction_date": "2026-03-11",
  "sleep_score": 72.5,
  "estimated_sleep_start": "2026-03-10T23:30:00Z",
  "estimated_wake_time": "2026-03-11T07:00:00Z",
  "estimated_duration_hours": 7.5,
  "data_source": "diary",
  "llm_advice": "Your sleep duration looks good this week...",
  "risk_level": "low",
  "created_at": "2026-03-11T08:00:00Z"
}
```

- `sleep_score`: 0–100 (higher = better)
- `risk_level`: `"low"` | `"medium"` | `"high"` | `"critical"`
- `llm_advice`: GPT-4o generated personalised advice (only populated when score < 65)
- `data_source`: `"diary"` | `"healthkit"` | `"combined"`

**Response (no data yet):**
```json
{ "message": "No prediction yet — sync HealthKit data first (run the Shortcut)" }
```

---

#### Get 14-Night Sleep History (for chart)
```
GET /api/sleep/history/{user_id}
X-User-Token: <token>
```

**Response:**
```json
[
  {
    "prediction_date": "2026-03-11",
    "sleep_score": 72.5,
    "estimated_duration_hours": 7.5,
    "risk_level": "low",
    "data_source": "diary"
  },
  {
    "prediction_date": "2026-03-10",
    "sleep_score": 55.0,
    "estimated_duration_hours": 6.0,
    "risk_level": "medium",
    "data_source": "diary"
  }
]
```
Returns up to 14 entries, newest first. Use this to render the sleep score chart.

---

### Chat (CBT-i AI Companion)

#### Send a Message
```
POST /api/chat
X-User-Token: <token>
```

**Request body:**
```json
{
  "message": "I can't fall asleep, my mind keeps racing",
  "session_id": "uuid-or-null"
}
```
- `session_id`: pass `null` on first message to create a new session; pass the returned `session_id` to continue the conversation

**Response:**
```json
{
  "reply": "It sounds like you're experiencing racing thoughts at bedtime...",
  "safety_flagged": false,
  "session_id": "uuid"
}
```
- `safety_flagged`: `true` if crisis keywords detected — UI should display crisis resources prominently
- When `safety_flagged` is `true`, the `reply` always contains Samaritans (116 123), SHOUT (85258), and 999

---

#### Get Chat Session History
```
GET /api/chat/history/{user_id}
X-User-Token: <token>
```

**Response:**
```json
[
  {
    "id": "session-uuid",
    "started_at": "2026-03-11T20:00:00Z",
    "message_count": 8
  }
]
```
Returns up to 10 most recent sessions.

---

### Staff Alerts

#### Create Alert *(called by the app automatically)*
```
POST /api/alert
X-User-Token: <token>
```

**Request body:**
```json
{
  "student_id": "uuid",
  "triggered_by": "sleep_prediction",
  "risk_level": "high",
  "message": "Student has had 5 consecutive nights with sleep score < 40"
}
```
- `risk_level`: `"medium"` | `"high"` | `"critical"`
- `triggered_by`: e.g. `"sleep_prediction"`, `"chat_safety_flag"`

**Response:**
```json
{ "status": "ok" }
```

---

#### Get Unresolved Alerts *(staff only)*
```
GET /api/alerts
X-User-Token: <staff_token>
```

**Response:**
```json
[
  {
    "id": "uuid",
    "student_id": "uuid",
    "triggered_by": "chat_safety_flag",
    "risk_level": "critical",
    "message": "Student expressed suicidal ideation",
    "email_sent": false,
    "resolved": false,
    "created_at": "2026-03-11T21:00:00Z"
  }
]
```

---

#### Resolve Alert *(staff only)*
```
PATCH /api/alerts/{alert_id}/resolve
X-User-Token: <staff_token>
```

**Response:**
```json
{ "status": "ok" }
```

---

## Error Responses

| Status | Meaning |
|--------|---------|
| 401 | Missing or invalid `X-User-Token` |
| 403 | Forbidden (wrong user or non-staff accessing staff endpoint) |
| 422 | Validation error (check request body) |
| 500 | Server error |

---

## Database Schema

> These tables live in Supabase (PostgreSQL). Row Level Security (RLS) is enabled on all tables. The Python backend uses the `service_role` key to bypass RLS for writes.

### `user_profiles`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | = Supabase `auth.users.id` |
| `university_name` | TEXT | |
| `year_of_study` | INTEGER | |
| `is_international_student` | BOOLEAN | default false |
| `usual_sleep_hours` | NUMERIC(4,1) | |
| `has_sleep_issues` | BOOLEAN | default false |
| `usual_bedtime` | TIME | HH:MM |
| `usual_wake_time` | TIME | HH:MM |
| `healthkit_consent` | BOOLEAN | default false |
| `role` | TEXT | `'student'` or `'staff'` |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | auto-updated |

---

### `sleep_diary`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK) | → auth.users |
| `entry_date` | DATE | YYYY-MM-DD |
| `bed_time` | TIMESTAMPTZ | when got into bed |
| `sleep_time` | TIMESTAMPTZ | when fell asleep |
| `wake_time` | TIMESTAMPTZ | when woke up |
| `out_of_bed_time` | TIMESTAMPTZ | when got out of bed |
| `sleep_quality` | INTEGER | 1 (very poor) – 5 (excellent) |
| `notes` | TEXT | |
| `created_at` | TIMESTAMPTZ | |

---

### `sleep_predictions`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK) | |
| `prediction_date` | DATE | the morning date |
| `sleep_score` | NUMERIC(5,2) | 0–100 |
| `estimated_sleep_start` | TIMESTAMPTZ | |
| `estimated_wake_time` | TIMESTAMPTZ | |
| `estimated_duration_hours` | NUMERIC(4,1) | |
| `data_source` | TEXT | `diary` / `healthkit` / `combined` |
| `llm_advice` | TEXT | GPT-4o generated, only when score < 65 |
| `risk_level` | TEXT | `low` / `medium` / `high` / `critical` |
| `created_at` | TIMESTAMPTZ | |

---

### `chat_sessions`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK) | |
| `started_at` | TIMESTAMPTZ | |
| `ended_at` | TIMESTAMPTZ | nullable |
| `message_count` | INTEGER | default 0 |

---

### `chat_messages`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `session_id` | UUID (FK) | → chat_sessions |
| `user_id` | UUID (FK) | |
| `role` | TEXT | `'user'` or `'assistant'` |
| `content` | TEXT | |
| `safety_flagged` | BOOLEAN | true = crisis response triggered |
| `created_at` | TIMESTAMPTZ | |

---

### `staff_alerts`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `student_id` | UUID (FK) | |
| `triggered_by` | TEXT | e.g. `sleep_prediction`, `chat_safety_flag` |
| `risk_level` | TEXT | `medium` / `high` / `critical` |
| `message` | TEXT | |
| `email_sent` | BOOLEAN | default false |
| `resolved` | BOOLEAN | default false |
| `created_at` | TIMESTAMPTZ | |

---

### `social_posts`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `user_id` | UUID (FK) | |
| `title` | TEXT | |
| `content` | TEXT | |
| `is_anonymous` | BOOLEAN | default false |
| `likes_count` | INTEGER | default 0 |
| `comments_count` | INTEGER | default 0 |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

---

### `social_comments`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID (PK) | |
| `post_id` | UUID (FK) | → social_posts |
| `user_id` | UUID (FK) | |
| `content` | TEXT | |
| `is_anonymous` | BOOLEAN | default false |
| `created_at` | TIMESTAMPTZ | |

---

## Frontend Environment Variable

```
VITE_API_BASE=https://xxxx.ngrok-free.app
```

Replace with your ngrok URL. All API calls should use:
```js
const API_BASE = import.meta.env.VITE_API_BASE
```
