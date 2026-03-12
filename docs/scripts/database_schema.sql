-- ============================================================
-- ClearHealth — Supabase Database Schema
-- Paste this entire file into Supabase SQL Editor and run it
-- ============================================================


-- ============================================================
-- 1. USER PROFILES
-- Extended info beyond Supabase Auth (auth.users)
-- ============================================================
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    university_name TEXT,
    year_of_study INTEGER,
    is_international_student BOOLEAN DEFAULT FALSE,
    usual_sleep_hours NUMERIC(4,1),
    has_sleep_issues BOOLEAN DEFAULT FALSE,
    usual_bedtime TIME,
    usual_wake_time TIME,
    healthkit_consent BOOLEAN DEFAULT FALSE,
    role TEXT DEFAULT 'student' CHECK (role IN ('student', 'staff')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Users can only read/update their own profile
CREATE POLICY "Users can view own profile"
    ON public.user_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.user_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own profile"
    ON public.user_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

-- Staff can view all student profiles
CREATE POLICY "Staff can view all profiles"
    ON public.user_profiles FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND role = 'staff'
        )
    );


-- ============================================================
-- 2. SLEEP DIARY
-- Manual sleep log entries submitted by students
-- ============================================================
CREATE TABLE public.sleep_diary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    entry_date DATE NOT NULL,
    bed_time TIMESTAMPTZ,            -- when they got into bed
    sleep_time TIMESTAMPTZ,          -- when they actually fell asleep
    wake_time TIMESTAMPTZ,           -- when they woke up
    out_of_bed_time TIMESTAMPTZ,     -- when they got out of bed
    sleep_quality INTEGER CHECK (sleep_quality BETWEEN 1 AND 5),  -- 1=very poor, 5=excellent
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.sleep_diary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own sleep diary"
    ON public.sleep_diary FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Staff can view all sleep diary"
    ON public.sleep_diary FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND role = 'staff'
        )
    );

-- Index for quick lookup by user and date
CREATE INDEX idx_sleep_diary_user_date ON public.sleep_diary(user_id, entry_date DESC);


-- ============================================================
-- 3. TRAINING SAMPLES
-- One processed row per user per night — extracted from HealthKit data.
-- Raw HealthKit data is NOT stored (processed on arrival and discarded).
-- Labels: diary entries take priority over HealthKit-estimated values.
-- ============================================================
CREATE TABLE public.training_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sample_date DATE NOT NULL,                   -- the wake-up date (morning side of the night)

    -- Sleep time labels
    sleep_start TIMESTAMPTZ,                     -- when sleep began (diary or HealthKit-estimated)
    wake_time TIMESTAMPTZ,                       -- when they woke up (diary or HealthKit-estimated)
    estimated_duration_hours NUMERIC(4,1),
    data_source TEXT CHECK (data_source IN ('diary', 'healthkit')),

    -- Features (extracted from HealthKit data)
    steps_daytime NUMERIC DEFAULT 0,
    walking_distance_metres NUMERIC DEFAULT 0,
    avg_step_length_cm NUMERIC DEFAULT 0,
    active_energy_kcal NUMERIC DEFAULT 0,
    basal_energy_kcal NUMERIC DEFAULT 0,
    flights_climbed NUMERIC DEFAULT 0,
    headphone_audio_evening_db NUMERIC DEFAULT 0,
    environmental_audio_night_db NUMERIC DEFAULT 0,
    day_of_week INTEGER,                         -- 0=Mon … 6=Sun

    -- Target label (0–100)
    -- diary: sleep_quality (1–5) × 20
    -- healthkit only: heuristic from duration
    quality_label NUMERIC(5,2),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, sample_date)
);

ALTER TABLE public.training_samples ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own training samples"
    ON public.training_samples FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert training samples"
    ON public.training_samples FOR INSERT
    WITH CHECK (TRUE);

CREATE INDEX idx_training_samples_user_date ON public.training_samples(user_id, sample_date DESC);


-- ============================================================
-- 4. SLEEP PREDICTIONS
-- ML model output stored per user per day
-- ============================================================
CREATE TABLE public.sleep_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    prediction_date DATE NOT NULL,
    sleep_score NUMERIC(5,2),            -- 0–100 quality score
    estimated_sleep_start TIMESTAMPTZ,   -- derived from HealthKit walk stop
    estimated_wake_time TIMESTAMPTZ,     -- derived from HealthKit walk start
    estimated_duration_hours NUMERIC(4,1),
    data_source TEXT DEFAULT 'healthkit' CHECK (data_source IN ('healthkit', 'diary', 'combined')),
    llm_advice TEXT,                     -- AI-generated personalised advice
    risk_level TEXT DEFAULT 'low' CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, prediction_date)
);

ALTER TABLE public.sleep_predictions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own predictions"
    ON public.sleep_predictions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service role can insert predictions"
    ON public.sleep_predictions FOR INSERT
    WITH CHECK (TRUE);  -- Python backend uses service key

CREATE POLICY "Staff can view all predictions"
    ON public.sleep_predictions FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND role = 'staff'
        )
    );


-- ============================================================
-- 5. CHAT SESSIONS
-- LLM chatbot conversation history
-- ============================================================
CREATE TABLE public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0
);

ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own chat sessions"
    ON public.chat_sessions FOR ALL
    USING (auth.uid() = user_id);


-- ============================================================
-- 6. CHAT MESSAGES
-- Individual messages within a chat session
-- ============================================================
CREATE TABLE public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    safety_flagged BOOLEAN DEFAULT FALSE,  -- true if safety guardrail triggered
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own messages"
    ON public.chat_messages FOR ALL
    USING (auth.uid() = user_id);

CREATE INDEX idx_chat_messages_session ON public.chat_messages(session_id, created_at ASC);


-- ============================================================
-- 7. SOCIAL POSTS
-- Community forum posts (judgement-free zone)
-- ============================================================
CREATE TABLE public.social_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_anonymous BOOLEAN DEFAULT FALSE,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.social_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone authenticated can view posts"
    ON public.social_posts FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Users can create posts"
    ON public.social_posts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own posts"
    ON public.social_posts FOR UPDATE
    USING (auth.uid() = user_id);

CREATE INDEX idx_social_posts_created ON public.social_posts(created_at DESC);


-- ============================================================
-- 8. SOCIAL COMMENTS
-- Comments on forum posts
-- ============================================================
CREATE TABLE public.social_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES public.social_posts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_anonymous BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.social_comments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Authenticated users can view comments"
    ON public.social_comments FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Users can create comments"
    ON public.social_comments FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE INDEX idx_social_comments_post ON public.social_comments(post_id, created_at ASC);


-- ============================================================
-- 9. STAFF ALERTS
-- Log of alerts sent to university staff
-- ============================================================
CREATE TABLE public.staff_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES auth.users(id),
    triggered_by TEXT NOT NULL,          -- e.g. 'sleep_prediction', 'chat_safety_flag'
    risk_level TEXT NOT NULL CHECK (risk_level IN ('medium', 'high', 'critical')),
    message TEXT,
    email_sent BOOLEAN DEFAULT FALSE,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.staff_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Staff can view all alerts"
    ON public.staff_alerts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles
            WHERE id = auth.uid() AND role = 'staff'
        )
    );

CREATE POLICY "Service role can insert alerts"
    ON public.staff_alerts FOR INSERT
    WITH CHECK (TRUE);


-- ============================================================
-- HELPER: Auto-update updated_at timestamp
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON public.user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_social_posts_updated_at
    BEFORE UPDATE ON public.social_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
