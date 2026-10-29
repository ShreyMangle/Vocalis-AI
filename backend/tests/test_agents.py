"""
tests/test_agents.py — Unit Tests for AI Voice Agent Configuration

Testing:
  - Agent config retrieval and not-found handling
  - RBAC checks (STAFF forbidden from editing, ADMIN/OWNER allowed)
  - Upsert and patch mutations
  - System prompt compiler integration with business profile, working hours, and services
  - Voice engine catalog listings
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.agent import AgentConfig
from app.models.business import Business, DayOfWeek, WorkingHours
from app.models.service import Service


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.fixture
def tokens(tenant_id):
    return {
        "owner": create_access_token(uuid.uuid4(), tenant_id, "OWNER"),
        "admin": create_access_token(uuid.uuid4(), tenant_id, "ADMIN"),
        "staff": create_access_token(uuid.uuid4(), tenant_id, "STAFF"),
    }


@pytest.fixture
def mock_agent(tenant_id):
    a = MagicMock(spec=AgentConfig)
    a.id = uuid.uuid4()
    a.tenant_id = tenant_id
    a.business_id = uuid.uuid4()
    a.name = "Sarah"
    a.role_description = "Clinic receptionist"
    a.system_prompt = "Be friendly and polite."
    a.greeting_message = "Hello! Thanks for calling Sunrise Clinic."
    a.fallback_message = "Sorry, could you repeat that?"
    a.voice_provider = "cartesia"
    a.voice_id = "a0e99841-438c-4a64-b679-ae501e7d6091"
    a.speech_speed = 1.0
    a.llm_provider = "openai"
    a.llm_model = "gpt-4o-mini"
    a.temperature = 0.3
    a.vad_sensitivity = "normal"
    a.primary_language = "en"
    a.supported_languages = ["en", "hi"]
    a.transfer_phone_number = "+919876543210"
    a.webhook_url = "https://example.com/webhook"
    a.sms_enabled = True
    a.is_active = True
    a.is_deleted = False
    a.created_at = datetime.now(timezone.utc)
    a.updated_at = datetime.now(timezone.utc)
    return a


class TestAgentConfigAPI:
    def test_get_agent_unauthorized(self, client):
        response = client.get("/api/v1/agents")
        assert response.status_code == 401

    def test_get_agent_not_found(self, client, tokens):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/agents",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "AGENT_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_get_agent_success(self, client, tokens, mock_agent):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.get(
                "/api/v1/agents",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Sarah"
            assert data["voice_provider"] == "cartesia"
            assert data["llm_model"] == "gpt-4o-mini"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_upsert_agent_forbidden_for_staff(self, client, tokens):
        payload = {"name": "Alex", "voice_id": "custom-voice"}
        response = client.put(
            "/api/v1/agents",
            json=payload,
            headers={"Authorization": f"Bearer {tokens['staff']}"},
        )
        assert response.status_code == 403

    def test_upsert_agent_creates_new(self, client, tokens):
        mock_session = AsyncMock()
        
        # 1. Business lookup
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = None

        # 2. Agent lookup
        mock_a_res = MagicMock()
        mock_a_res.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_b_res, mock_a_res]
        mock_session.add = MagicMock()

        async def mock_refresh(instance):
            instance.id = uuid.uuid4()
            instance.created_at = datetime.now(timezone.utc)
            instance.updated_at = datetime.now(timezone.utc)

        mock_session.refresh = mock_refresh

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            payload = {
                "name": "Priya",
                "role_description": "Friendly hospital receptionist",
                "voice_provider": "cartesia",
                "voice_id": "b7d50908-b17c-442d-ad8d-810c63997ed9",
                "llm_provider": "groq",
                "llm_model": "llama-3.3-70b-versatile",
                "primary_language": "en",
                "supported_languages": ["en", "hi"],
            }
            response = client.put(
                "/api/v1/agents",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['admin']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Priya"
            assert data["llm_provider"] == "groq"
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_patch_agent_updates_fields(self, client, tokens, mock_agent):
        mock_session = AsyncMock()
        mock_res = MagicMock()
        mock_res.scalar_one_or_none.return_value = mock_agent
        mock_session.execute.return_value = mock_res

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            payload = {"temperature": 0.5, "speech_speed": 1.1}
            response = client.patch(
                "/api/v1/agents",
                json=payload,
                headers={"Authorization": f"Bearer {tokens['owner']}"},
            )
            assert response.status_code == 200
            assert mock_agent.temperature == 0.5
            assert mock_agent.speech_speed == 1.1
            mock_session.commit.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_preview_prompt_compiles_context(self, client, tokens, mock_agent):
        mock_session = AsyncMock()

        # 1. Agent
        mock_a_res = MagicMock()
        mock_a_res.scalar_one_or_none.return_value = mock_agent

        # 2. Business
        mock_b = MagicMock(spec=Business)
        mock_b.id = uuid.uuid4()
        mock_b.name = "Apex Health"
        mock_b.industry = "Pediatric Clinic"
        mock_b.timezone = "Asia/Kolkata"
        mock_b.phone_number = "+919999988888"
        mock_b.address = "12 Bangalore Road"
        mock_b_res = MagicMock()
        mock_b_res.scalar_one_or_none.return_value = mock_b

        # 3. Working Hours
        wh = MagicMock(spec=WorkingHours)
        wh.day_of_week = DayOfWeek.MONDAY
        wh.is_closed = False
        wh.open_time = datetime.strptime("09:00", "%H:%M").time()
        wh.close_time = datetime.strptime("17:00", "%H:%M").time()
        mock_wh_res = MagicMock()
        mock_wh_res.scalars.return_value.all.return_value = [wh]

        # 4. Services
        s = MagicMock(spec=Service)
        s.name = "Pediatric Checkup"
        s.duration_minutes = 30
        s.price = 60000
        s.currency = "INR"
        s.is_active = True
        mock_s_res = MagicMock()
        mock_s_res.scalars.return_value.all.return_value = [s]

        mock_session.execute.side_effect = [mock_a_res, mock_b_res, mock_wh_res, mock_s_res]

        async def override():
            yield mock_session

        app.dependency_overrides[get_session] = override
        try:
            response = client.post(
                "/api/v1/agents/preview-prompt",
                headers={"Authorization": f"Bearer {tokens['staff']}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["agent_name"] == "Sarah"
            assert data["business_name"] == "Apex Health"
            assert "Apex Health" in data["compiled_prompt"]
            assert "Pediatric Checkup" in data["compiled_prompt"]
            assert data["services_count"] == 1
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_list_voice_catalog(self, client, tokens):
        response = client.get(
            "/api/v1/agents/voices",
            headers={"Authorization": f"Bearer {tokens['staff']}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3
        names = [v["name"] for v in data]
        assert "Sarah" in names
        assert "Priya" in names

