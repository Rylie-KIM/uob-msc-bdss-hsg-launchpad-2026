# HealthKit → Python Backend Integration Guide
> Using Yeon's iPhone to send health data to the Python API via ngrok

---

## Overview

```
iPhone (Apple Health)  [8 data types, sequential POST]
    → iOS Shortcuts app (automation)
        → POST /api/healthkit/sync  (×8, one per data type)
            → ngrok tunnel
                → FastAPI: buffer samples in memory (NOT saved to DB)
        → POST /api/healthkit/train  (triggered last)
            → feature extraction (sleep_predictor.py)
                → ML model → sleep score
                    → Supabase DB (prediction result only)
```

Raw HealthKit samples are **processed in-memory** and never written to Supabase.
Only the final sleep prediction (score + advice) is saved to the DB.

All data collected from a standard iPhone — **no wearable device needed**.

---

## What Data We Collect

| HealthKit Identifier | Shortcut Type Name | What It Gives Us | Unit | Used For |
|---|---|---|---|---|
| `HKQuantityTypeIdentifierStepCount` | Steps | Steps per 15-min interval | count | Sleep/wake detection |
| `HKQuantityTypeIdentifierDistanceWalkingRunning` | Walking + Running Distance | Distance moved | metres | Activity level |
| `HKQuantityTypeIdentifierWalkingStepLength` | Walking Step Length | Stride length | cm | Fatigue indicator |
| `HKQuantityTypeIdentifierActiveEnergyBurned` | Active Energy | Calories burned by activity | kcal | Daytime activity level |
| `HKQuantityTypeIdentifierBasalEnergyBurned` | Resting Energy | Base metabolic rate | kcal | Recovery quality |
| `HKQuantityTypeIdentifierFlightsClimbed` | Flights Climbed | Stairs climbed | count | Activity intensity |
| `HKQuantityTypeIdentifierHeadphoneAudioExposure` | Headphone Audio Levels | Evening audio stimulation | dBASPL | Pre-sleep stimulation |
| `HKQuantityTypeIdentifierEnvironmentalAudioExposure` | Environmental Sound Levels | Ambient noise | dBASPL | Sleep environment quality |

### How each feeds into sleep prediction

- **Steps / Distance / Flights** → detect sleep start/wake time (walking stops = in bed)
- **Step Length** → shorter strides indicate fatigue → higher sleep pressure
- **Active Energy** → more daytime activity = better sleep quality
- **Basal Energy** → tracks recovery; low basal rate after bad sleep
- **Headphone Audio (evening, 8pm–midnight)** → high exposure = stimulated brain → delayed sleep
- **Environmental Audio (midnight–6am)** → high noise during sleep window = fragmented sleep

---

## Step-by-Step Setup

### Step 1 — Prepare Your Python API

Make sure your FastAPI server is running:
```bash
cd clearhealth-api
uvicorn main:app --reload --port 8000
```

### Step 2 — Start ngrok Tunnel

```bash
ngrok http 8000
```

Copy the HTTPS URL shown, e.g.: `https://abc123.ngrok.io`
This is your `API_BASE_URL`.

### Step 3 — Set Up iOS Shortcut on Yeon's iPhone

> **사용할 액션: "Find Health Samples"** (검색창에서 "hea" 입력하면 나옴)
> - "Find Health Samples" ✅ — 기간 동안 여러 샘플 리스트 반환 (우리가 필요한 것)
> - "Get Details of Health Sample" ❌ — 샘플 하나에서 속성 꺼낼 때 사용, 우리한테 불필요
>
> ⚠️ **iOS Shortcuts 특성**: 두 번째 "Find Health Samples"부터 자동으로 "Filter Health Samples"로 바뀜.
> 이건 정상 동작 — Filter 액션에서 Type만 원하는 타입으로 바꾸면 됩니다.
> `/api/healthkit/train` 별도 호출 불필요 — 8번째 sync 도착 시 서버가 자동으로 학습합니다.

**Option A: Manual trigger (quickest for demo)**

1. Open **Shortcuts** app on iPhone
2. Tap **+** → create new shortcut → name it **"ClearHealth — Sync"**
3. 아래 패턴을 **Find → POST** 쌍으로 16개 추가 (학습은 자동):

```
① Find Health Samples
     Type is: Steps | Start Date is in the last: 6 Weeks
     Sort: Start Date | Oldest First | Limit: OFF

② Get Contents of URL
     URL: https://xxxx.ngrok.io/api/healthkit/sync
     Method: POST
     Headers: Content-Type: application/json
              X-User-Token: [Supabase JWT]
     Body: { "data_type": "steps", "samples": [Health Samples] }
           ↑ "Health Samples" = ①의 출력을 파란 토큰으로 드래그

③ Find / Filter Health Samples — Walking + Running Distance
④ POST → { "data_type": "walking_distance", "samples": [③] }

⑤ Find / Filter Health Samples — Walking Step Length
⑥ POST → { "data_type": "walking_step_length", "samples": [⑤] }

⑦ Find / Filter Health Samples — Active Energy
⑧ POST → { "data_type": "active_energy", "samples": [⑦] }

⑨ Find / Filter Health Samples — Resting Energy
⑩ POST → { "data_type": "basal_energy", "samples": [⑨] }

⑪ Find / Filter Health Samples — Flights Climbed
⑫ POST → { "data_type": "flights_climbed", "samples": [⑪] }

⑬ Find / Filter Health Samples — Headphone Audio Levels
⑭ POST → { "data_type": "headphone_audio", "samples": [⑬] }

⑮ Find / Filter Health Samples — Environmental Sound Levels
⑯ POST → { "data_type": "environmental_audio", "samples": [⑮] }
         ↑ 이게 도착하면 서버가 자동으로 학습 시작 (별도 트리거 불필요)
```

4. Tap **Done** → 총 **16개 액션**, 하나의 Shortcut 파일
5. 처음 실행: 6주치 전송 → ⑯ 응답에서 학습 결과 포함
6. 이후 **매일 18:00** Automation으로 자동 실행

> **확인**: ⑯ 응답에서
> `{ "training_triggered": true, "nights_processed": 38, "latest_prediction": {...} }`
> 보이면 성공. `training_triggered: false`면 아직 다른 타입 기다리는 중 (정상).

**Option B: Automatic trigger (runs every morning)**

1. Go to **Automation** tab in Shortcuts
2. Tap **+** → **Personal Automation**
3. Choose **Time of Day** → set to **6:00 PM** daily (18:00 UK time)
4. Add same actions as Option A
5. Turn off "Ask Before Running"

---

### Step 4 — API Endpoints (Python)

Two endpoints: `/sync` buffers each data type in memory, `/train` triggers ML once all 8 are received.

```python
# api/routers/healthkit.py

from fastapi import APIRouter, Header
from pydantic import BaseModel
from typing import List
from api.services.sleep_predictor import run_pipeline
from api.services.supabase_client import save_prediction

router = APIRouter()

# In-memory buffer: keyed by user_id
_buffer: dict[str, dict[str, list]] = {}

class HealthSample(BaseModel):
    startDate: str   # ISO 8601 e.g. "2026-03-12T23:00:00+00:00"
    endDate: str
    value: float
    unit: str = "count"

class HealthKitPayload(BaseModel):
    data_type: str   # "steps" | "walking_distance" | "active_energy" | ...
    samples: List[HealthSample]

@router.post("/api/healthkit/sync")
async def buffer_healthkit(payload: HealthKitPayload, x_user_token: str = Header(...)):
    """Receive one data type — store in memory only, NOT in DB."""
    user_id = x_user_token  # simplified; replace with JWT decode
    _buffer.setdefault(user_id, {})[payload.data_type] = [s.dict() for s in payload.samples]
    return {"status": "buffered", "data_type": payload.data_type, "count": len(payload.samples)}

@router.post("/api/healthkit/train")
async def train_from_buffer(x_user_token: str = Header(...)):
    """All 8 types received — run feature extraction + ML, save prediction to DB."""
    user_id = x_user_token
    data = _buffer.pop(user_id, {})  # clear buffer after use

    prediction = run_pipeline(data)  # feature extraction → ML model
    save_prediction(user_id, prediction)  # only this goes to Supabase

    return {
        "nights_processed": prediction["nights_processed"],
        "latest_prediction": prediction["latest"]
    }
```

---

### Step 5 — Sleep Time Estimation Logic

```python
# api/services/sleep_predictor.py

import pandas as pd

NIGHT_WINDOW_START = 21  # 9pm
NIGHT_WINDOW_END = 4     # 4am (next day)
SLEEP_INACTIVITY_MINUTES = 20  # threshold

def estimate_sleep_times(samples: list[dict]) -> dict:
    df = pd.DataFrame(samples)
    df['time'] = pd.to_datetime(df['startDate'])
    df['hour'] = df['time'].dt.hour
    df = df.sort_values('time')

    # Filter to night window (9pm–4am)
    night = df[
        (df['hour'] >= NIGHT_WINDOW_START) |
        (df['hour'] < NIGHT_WINDOW_END)
    ].copy()

    # Find first gap of 20+ minutes with zero/near-zero steps
    night['gap_minutes'] = night['time'].diff().dt.total_seconds() / 60
    night['is_inactive'] = night['value'] < 10  # < 10 steps = inactive

    sleep_start = None
    wake_time = None

    for i, row in night.iterrows():
        if row['is_inactive'] and row['gap_minutes'] >= SLEEP_INACTIVITY_MINUTES:
            if sleep_start is None:
                sleep_start = row['time']
        elif sleep_start is not None and not row['is_inactive']:
            wake_time = row['time']
            break

    return {
        "estimated_sleep_start": sleep_start.isoformat() if sleep_start else None,
        "estimated_wake_time": wake_time.isoformat() if wake_time else None,
        "estimated_duration_hours": (
            (wake_time - sleep_start).total_seconds() / 3600
            if sleep_start and wake_time else None
        )
    }
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| ngrok URL keeps changing | Use `ngrok http 8000 --domain your-name.ngrok-free.app` (free static domain) |
| Shortcut says "permission denied" | Go to iPhone Settings → Health → Apps → Shortcuts → allow Steps read |
| No data received | Check iPhone has step data: Health app → Browse → Activity → Steps |
| Token rejected | Re-generate Supabase JWT: sign in via Supabase Auth and copy the access_token |

---

## For Demo Day (Quick Setup)

1. Start API: `uvicorn main:app --port 8000`
2. Start ngrok: `ngrok http 8000`
3. Update ngrok URL in Shortcut on iPhone (⑰ POST URL도 같이 업데이트)
4. Run Shortcut manually (8× sync → 1× train, 총 17 액션 실행)
5. Check API response from ⑰: `{ "nights_processed": N, "latest_prediction": {...} }`
6. Check Supabase `sleep_predictions` table — prediction row only (raw samples 없음)
7. Call `GET /api/sleep/prediction/{user_id}` — sleep score 반환 확인
