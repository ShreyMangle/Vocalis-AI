"""
tests/test_telephony.py — Unit Tests for Telephony Inbound & Outbound Dispatch
"""

import uuid

import pytest

from app.core.security import create_access_token


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def tokens(tenant_id):
    return {
        "staff": create_access_token(uuid.uuid4(), tenant_id, "STAFF"),
        "admin": create_access_token(uuid.uuid4(), tenant_id, "ADMIN"),
    }


def test_twilio_voice_webhook_returns_twiml_xml(client):
    response = client.get("/api/v1/telephony/voice?appointmentId=test-123")
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    body = response.text
    assert "<Response>" in body
    assert "<Connect>" in body
    assert "<Stream" in body
    assert 'name="appointmentId" value="test-123"' in body


def test_get_telephony_status_unauthorized(client):
    response = client.get("/api/v1/telephony/status")
    assert response.status_code == 401


def test_get_telephony_status_authorized(client, tokens):
    response = client.get(
        "/api/v1/telephony/status",
        headers={"Authorization": f"Bearer {tokens['staff']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "provider" in data
    assert "is_configured" in data


def test_trigger_outbound_call_forbidden_for_staff(client, tokens):
    payload = {"to_phone": "+919876543210"}
    response = client.post(
        "/api/v1/telephony/outbound-call",
        json=payload,
        headers={"Authorization": f"Bearer {tokens['staff']}"},
    )
    assert response.status_code == 403


def test_trigger_outbound_call_simulation_for_admin(client, tokens):
    payload = {"to_phone": "+919876543210"}
    response = client.post(
        "/api/v1/telephony/outbound-call",
        json=payload,
        headers={"Authorization": f"Bearer {tokens['admin']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("simulation_initiated", "queued")
    assert data["to_phone"] == "+919876543210"
    assert data["call_sid"] != ""

