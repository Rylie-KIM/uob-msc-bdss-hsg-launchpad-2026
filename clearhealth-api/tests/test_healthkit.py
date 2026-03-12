"""Tests for HealthKit data processing."""
import pytest
from fastapi.testclient import TestClient


def test_healthkit_payload_valid():
    """Validate that a well-formed HealthKit payload is accepted by the Pydantic model."""
    from api.routers.healthkit import HealthKitPayload, HealthSample
    payload = HealthKitPayload(
        data_type="step_count",
        samples=[
            HealthSample(startDate="2026-03-12T22:00:00", endDate="2026-03-12T22:15:00", value=5.0),
            HealthSample(startDate="2026-03-12T22:15:00", endDate="2026-03-12T22:30:00", value=2.0),
        ],
    )
    assert payload.data_type == "step_count"
    assert len(payload.samples) == 2


def test_healthkit_empty_samples():
    from api.routers.healthkit import HealthKitPayload
    payload = HealthKitPayload(data_type="step_count", samples=[])
    assert len(payload.samples) == 0
