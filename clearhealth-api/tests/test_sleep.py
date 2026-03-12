"""Tests for sleep prediction logic."""
import pytest
from api.services.sleep_predictor import estimate_sleep_times, compute_sleep_score, get_risk_level


def _make_samples(times_and_steps: list[tuple[str, float]]) -> list[dict]:
    return [{"startDate": t, "endDate": t, "value": v} for t, v in times_and_steps]


def test_estimate_sleep_times_detects_night_sleep():
    """Standard case: falls asleep ~11pm, wakes ~7am — within 18:00-06:00 window."""
    samples = _make_samples([
        ("2026-03-11T22:00:00", 50),  # still walking
        ("2026-03-11T22:20:00", 5),   # going inactive
        ("2026-03-11T22:40:00", 2),   # 20+ min inactive → sleep start
        ("2026-03-11T23:00:00", 3),
        ("2026-03-12T05:30:00", 80),  # woke up (within 06:00 cutoff)
        ("2026-03-12T05:45:00", 200),
    ])
    result = estimate_sleep_times(samples)
    assert result["estimated_sleep_start"] is not None
    assert result["estimated_wake_time"] is not None
    assert result["estimated_duration_hours"] is not None
    assert result["estimated_duration_hours"] > 0


def test_estimate_sleep_times_ignores_daytime_nap():
    """Daytime inactivity (12:00–17:00) should NOT be detected as sleep."""
    samples = _make_samples([
        ("2026-03-12T12:00:00", 2),   # 12pm — inactive (nap)
        ("2026-03-12T12:20:00", 1),   # still inactive
        ("2026-03-12T12:40:00", 3),   # 20+ min inactive — but NOT in night window
        ("2026-03-12T13:00:00", 150), # walking again
    ])
    result = estimate_sleep_times(samples)
    assert result["estimated_sleep_start"] is None  # daytime nap ignored


def test_estimate_sleep_times_empty():
    result = estimate_sleep_times([])
    assert result["estimated_sleep_start"] is None
    assert result["estimated_wake_time"] is None


def test_sleep_score_good_sleep():
    score = compute_sleep_score({
        "estimated_duration_hours": 7.5,
        "sleep_quality": 4,
        "steps_daytime": 8000,
        "is_international": False,
        "day_of_week": 1,
    })
    assert score >= 60


def test_sleep_score_poor_sleep():
    score = compute_sleep_score({
        "estimated_duration_hours": 4.0,
        "sleep_quality": 1,
        "steps_daytime": 1000,
        "is_international": True,
        "day_of_week": 6,
    })
    assert score < 50


def test_risk_levels():
    assert get_risk_level(80) == "low"
    assert get_risk_level(60) == "medium"
    assert get_risk_level(40) == "high"
    assert get_risk_level(20) == "critical"
