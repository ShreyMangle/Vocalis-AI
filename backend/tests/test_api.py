import pytest
import os
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db import init_db, query_db

@pytest.fixture(scope="session", autouse=True)
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    await init_db()

@pytest.mark.asyncio
async def test_full_api_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        
        # 1. Register a test business
        unique_email = f"test_{os.urandom(4).hex()}@vocalis.ai"
        reg_payload = {
            "name": "Apex Dental Clinic",
            "email": unique_email,
            "password": "Password123!",
            "industry": "Healthcare",
            "phone_number": "+15550001111"
        }
        res = await ac.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 200
        reg_data = res.json()
        assert "token" in reg_data
        token = reg_data["token"]
        business_id = reg_data["business"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get Profile (/api/auth/me)
        me_res = await ac.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == unique_email

        # 3. Create an appointment
        appt_payload = {
            "customer_name": "Alice Smith",
            "customer_phone": "+15559876543",
            "scheduled_at": "2026-09-01T14:00:00Z"
        }
        appt_res = await ac.post("/api/appointments", json=appt_payload, headers=headers)
        assert appt_res.status_code == 200
        appt_id = appt_res.json()["id"]

        # 4. Upload CSV Bulk appointments
        csv_payload = {
            "csvText": "Charlie Brown, +15551112233, 2026-09-02 10:00\nLucy van Pelt, +15554445566, 2026-09-02 11:30"
        }
        csv_res = await ac.post("/api/appointments/upload", json=csv_payload, headers=headers)
        assert csv_res.status_code == 200
        assert csv_res.json()["count"] == 2

        # 5. List appointments
        list_res = await ac.get("/api/appointments", headers=headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 3

        # 6. Test iCalendar RFC 5545 feed (/api/calendar/{business_id}/feed.ics)
        cal_res = await ac.get(f"/api/calendar/{business_id}/feed.ics")
        assert cal_res.status_code == 200
        assert "text/calendar" in cal_res.headers.get("content-type", "")
        cal_text = cal_res.text
        assert "BEGIN:VCALENDAR" in cal_text
        assert "Alice Smith" in cal_text
        assert "END:VCALENDAR" in cal_text

        # 7. Test Campaign Batch Dispatch
        camp_res = await ac.post("/api/campaigns/dispatch-reminders", headers=headers)
        assert camp_res.status_code == 200
        assert camp_res.json()["success"] is True
        assert camp_res.json()["count"] >= 3

        # 8. Test Settings Get & Update
        settings_res = await ac.get("/api/settings", headers=headers)
        assert settings_res.status_code == 200
        
        update_payload = {
            "agent_name": "Jessica",
            "voice_id": "en-GB-SoniaNeural",
            "custom_greeting": "Hi {customer_name}, this is Jessica calling from {business_name}.",
            "business_faqs": "Open Mon-Fri 8am-6pm. Free parking.",
            "webhook_url": "https://example.com/webhook",
            "sms_enabled": 1,
            "speech_speed": "+10%",
            "vad_sensitivity": "high"
        }
        set_res = await ac.put("/api/settings", json=update_payload, headers=headers)
        assert set_res.status_code == 200
        
        verify_settings = await ac.get("/api/settings", headers=headers)
        assert verify_settings.json()["agent_name"] == "Jessica"
        assert verify_settings.json()["speech_speed"] == "+10%"
        assert verify_settings.json()["vad_sensitivity"] == "high"

        # 9. Test Stats calculation (/api/stats)
        stats_res = await ac.get("/api/stats", headers=headers)
        assert stats_res.status_code == 200
        stats_data = stats_res.json()
        assert "appointments" in stats_data
        assert "roi" in stats_data
        assert "performance" in stats_data

        # 10. Test Calls CSV Export (/api/calls/export.csv)
        export_res = await ac.get("/api/calls/export.csv", headers=headers)
        assert export_res.status_code == 200
        assert "text/csv" in export_res.headers.get("content-type", "")
        assert "Call ID" in export_res.text

        # 11. Delete appointment
        del_res = await ac.delete(f"/api/appointments/{appt_id}", headers=headers)
        assert del_res.status_code == 200
