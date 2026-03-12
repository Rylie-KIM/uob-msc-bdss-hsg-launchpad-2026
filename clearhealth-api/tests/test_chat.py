"""Tests for the chat service safety guardrails."""
import pytest
from api.services.llm_agent import is_safety_flagged, SAFETY_RESPONSE


def test_safety_flag_detects_self_harm():
    assert is_safety_flagged("I want to kill myself") is True
    assert is_safety_flagged("I've been thinking about self harm") is True
    assert is_safety_flagged("I don't want to live anymore") is True


def test_safety_flag_case_insensitive():
    assert is_safety_flagged("I WANT TO DIE") is True


def test_safety_flag_not_triggered_on_normal_message():
    assert is_safety_flagged("I can't sleep lately") is False
    assert is_safety_flagged("What's a good bedtime routine?") is False
    assert is_safety_flagged("I feel really tired") is False


def test_safety_response_contains_crisis_line():
    assert "116 123" in SAFETY_RESPONSE
    assert "Samaritans" in SAFETY_RESPONSE
    assert "85258" in SAFETY_RESPONSE
