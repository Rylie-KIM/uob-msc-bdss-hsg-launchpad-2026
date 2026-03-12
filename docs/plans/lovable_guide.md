# Lovable AI Integration Guide
> Prompts to build the ClearHealth UI + how to connect to Python API

---

## Setup in Lovable

1. Go to lovable.dev → create new project
2. Name it: **ClearHealth**
3. Connect Supabase: Settings → Supabase → paste your project URL + anon key
4. Add your Python API base URL as an environment variable: `VITE_API_BASE=https://your-ngrok-url.ngrok.io`

---

## Page Structure to Build

```
/ (Landing/Login)
/signup                → Supabase Auth sign-up
/onboarding            → questionnaire form
/home                  → main dashboard (sleep score + quick actions)
/chat                  → LLM chatbot
/sleep                 → sleep tracker + diary + chart
/social                → community forum
/social/:postId        → post detail + comments
/staff                 → university staff dashboard (protected route)
```

---

## Lovable Prompts — Copy & Paste These

---

### Prompt 1 — Initial App Setup

```
Build a React web app called ClearHealth — a mental health platform for UK university students focused on sleep support.

Use:
- Tailwind CSS for styling
- React Router for navigation
- Supabase for auth and database
- A calm, professional colour scheme: deep navy (#1a2744), soft lavender (#b8a9d4), white backgrounds, green (#22c55e) for positive states

Create the base layout with:
- A sidebar nav (mobile-responsive hamburger) with links: Home, Chat, Sleep Tracker, Community, Profile
- A top header showing the app name and user avatar
- Protected routes: redirect to /login if not authenticated
- An environment variable VITE_API_BASE for the Python backend URL
```

---

### Prompt 2 — Sign-up & Onboarding

```
Build the sign-up and onboarding flow:

Page 1: /signup
- Email + password sign-up using Supabase Auth
- Link to login page

Page 2: /onboarding (shown once after first sign-up)
- Progress bar (3 steps)
- Step 1: "Tell us about you"
  - University name (text input)
  - Year of study (dropdown: 1st, 2nd, 3rd, 4th, Postgrad)
  - Are you an international student? (Yes/No toggle)
- Step 2: "Your sleep"
  - How many hours of sleep do you usually get? (slider 3–10)
  - Do you have trouble sleeping? (Yes/No/Sometimes)
  - Usual bedtime (time picker)
  - Usual wake time (time picker)
- Step 3: "Data & privacy"
  - Explanation of what data we collect (Apple Health walking data, sleep diary)
  - Consent checkbox: "I agree to share my Apple Health data to improve my sleep predictions"
  - GDPR notice: "Your data is stored securely and never shared with third parties without consent"
  - Button: "Get Started"
- On submit: POST to Supabase `user_profiles` table with all answers
```

---

### Prompt 3 — Home Dashboard

```
Build the /home page (main dashboard) with:

1. Welcome card: "Good morning, [name]" with current date
2. Sleep score card (large, centre):
   - Circular progress ring showing score 0–100
   - Score fetched from GET ${VITE_API_BASE}/api/sleep/prediction/${userId}
   - Show loading spinner while fetching
   - If no data: "No sleep data yet — start your sleep diary"
   - Colour: green (≥70), amber (50–69), red (<50)
3. Quick action buttons:
   - "Chat with your sleep coach" → /chat
   - "Log last night's sleep" → /sleep#diary
   - "Community" → /social
4. Tip of the day card: short CBT-i tip (static text, rotate daily by day-of-week)
```

---

### Prompt 4 — CBT-i Chatbot

```
Build the /chat page:

- Clean chat interface with message bubbles
  - User messages: right-aligned, navy background, white text
  - Assistant messages: left-aligned, light grey background, dark text
- Input bar at bottom with send button
- "Powered by CBT-i guidelines" subtitle under the header

API integration:
- On send: POST ${VITE_API_BASE}/api/chat
  Body: { user_id: string, message: string, session_id: string }
  Response: { reply: string, safety_flagged: boolean }
- If safety_flagged is true: show a banner "If you're in crisis, please call Samaritans: 116 123"
- Show typing indicator (animated dots) while waiting for response
- On page load: GET ${VITE_API_BASE}/api/chat/history/${userId} to load previous messages
- Disclaimer banner at top: "This is a support tool, not a medical service. It cannot diagnose or treat conditions."
```

---

### Prompt 5 — Sleep Tracker

```
Build the /sleep page with two tabs: "Overview" and "Diary"

Tab 1 — Overview:
- Line chart showing sleep duration for last 7 days
  Data from GET ${VITE_API_BASE}/api/sleep/history/${userId}
- Today's prediction card (same as home dashboard)
- LLM advice text card: shows the llm_advice field from prediction API
- "Connect Apple Health" info banner linking to instructions

Tab 2 — Diary:
- Form to log last night's sleep:
  - Date (default: yesterday)
  - "What time did you get into bed?" (time picker)
  - "What time did you fall asleep?" (time picker)
  - "What time did you wake up?" (time picker)
  - "What time did you get out of bed?" (time picker)
  - Sleep quality rating (1–5 stars)
  - Notes (optional textarea)
- Submit button: POST ${VITE_API_BASE}/api/sleep/diary
  Body: { user_id, entry_date, bed_time, sleep_time, wake_time, out_of_bed_time, sleep_quality, notes }
- Show success toast on save
- Below form: table showing last 7 diary entries
```

---

### Prompt 6 — Social Community Page

```
Build the /social page — a judgement-free community forum:

(This page connects DIRECTLY to Supabase, no Python API needed)

Page layout:
- "Community" header with tagline "Share your story. Support others. You're not alone."
- "New Post" button (opens modal)
- Posts feed: card list sorted by newest first
  - Each card shows: title, preview (first 100 chars), author (or "Anonymous"), likes count, comments count, timestamp
  - Tap/click → goes to /social/:postId

New Post modal:
- Title input
- Content textarea
- "Post anonymously" checkbox
- Submit: INSERT into Supabase `social_posts` table

/social/:postId page:
- Full post content
- Like button (increment likes_count)
- Comments section below
  - List of comments with author + time
  - Comment input box + "Post anonymously" checkbox
  - Submit: INSERT into Supabase `social_comments` table
```

---

### Prompt 7 — University Staff Dashboard

```
Build the /staff page (only accessible if user.role === 'staff' in user_profiles table):

If not staff role: redirect to /home with "Access denied" toast.

Dashboard layout:
- Header: "Student Wellbeing Dashboard — [University Name]"
- Summary stats row:
  - Total students monitored
  - Students with critical risk today (red badge)
  - Average sleep score this week

- Student table with columns:
  Name | Sleep Score (today) | Risk Level | Last Active | Action

  Risk level badge colours:
  - Low: green
  - Medium: amber
  - High: red
  - Critical: dark red, pulsing

  Action: "View Profile" button

- Fetch data from Supabase: JOIN user_profiles + sleep_predictions WHERE prediction_date = today

- Auto-refresh every 5 minutes
```

---

## Connecting Lovable to Python API — Code Pattern

Add this utility to your Lovable project (in `src/lib/api.ts`):

```typescript
const API_BASE = import.meta.env.VITE_API_BASE

export async function apiPost(path: string, body: object, token: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Token': token
    },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function apiGet(path: string, token: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'X-User-Token': token }
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}
```

---

## What Connects Where

| Feature | Data source |
|---|---|
| Auth (login/signup) | Supabase Auth directly |
| User profile | Supabase `user_profiles` table directly |
| Chat messages | Python API `/api/chat` |
| Sleep diary | Python API `/api/sleep/diary` |
| Sleep prediction | Python API `/api/sleep/prediction` |
| Sleep history chart | Python API `/api/sleep/history` |
| Social posts/comments | Supabase `social_posts` + `social_comments` directly |
| Staff dashboard | Supabase `user_profiles` + `sleep_predictions` directly |
