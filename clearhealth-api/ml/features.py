"""Feature engineering for the sleep quality ML model."""


def build_features(
    estimated_duration_hours: float | None,
    steps_daytime: float,
    is_international: bool,
    day_of_week: int,
    sleep_quality: int | None,
    active_energy_kcal: float = 0,
    avg_step_length_cm: float = 0,
    flights_climbed: float = 0,
    headphone_audio_evening_db: float = 0,
    environmental_audio_night_db: float = 0,
    walking_distance_metres: float = 0,
    basal_energy_kcal: float = 0,
) -> list[float]:
    """
    Returns a feature vector for sleep quality prediction.

    Feature meanings:
    - duration_hours: estimated sleep duration (0 if unknown)
    - steps_daytime: total daytime steps (activity proxy)
    - is_international: jet lag risk flag
    - day_of_week: 0=Mon..6=Sun (weekend effect)
    - sleep_quality: diary self-report 1–5 (3 if unknown)
    - active_energy_kcal: calories burned through activity (more = better sleep)
    - avg_step_length_cm: avg stride length (shorter = more fatigued)
    - flights_climbed: flights of stairs (activity intensity)
    - headphone_audio_evening_db: avg audio exposure 8pm–midnight (stimulation before bed)
    - environmental_audio_night_db: avg ambient noise midnight–6am (sleep disturbance)
    - walking_distance_metres: total distance walked
    - basal_energy_kcal: resting metabolic rate (sleep recovery proxy)
    """
    return [
        float(estimated_duration_hours or 0),
        float(steps_daytime or 0),
        float(int(is_international)),
        float(day_of_week),
        float(sleep_quality or 3),
        float(active_energy_kcal or 0),
        float(avg_step_length_cm or 0),
        float(flights_climbed or 0),
        float(headphone_audio_evening_db or 0),
        float(environmental_audio_night_db or 0),
        float(walking_distance_metres or 0),
        float(basal_energy_kcal or 0),
    ]


FEATURE_NAMES = [
    "duration_hours",
    "steps_daytime",
    "is_international",
    "day_of_week",
    "sleep_quality",
    "active_energy_kcal",
    "avg_step_length_cm",
    "flights_climbed",
    "headphone_audio_evening_db",
    "environmental_audio_night_db",
    "walking_distance_metres",
    "basal_energy_kcal",
]

# Data types we pull from Supabase for feature building
HEALTHKIT_DATA_TYPES = [
    "step_count",
    "walking_distance",
    "walking_step_length",
    "active_energy_burned",
    "basal_energy_burned",
    "flights_climbed",
    "headphone_audio_exposure",
    "environmental_audio_exposure",
]
