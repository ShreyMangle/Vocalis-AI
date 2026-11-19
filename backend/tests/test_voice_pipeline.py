"""
tests/test_voice_pipeline.py — Unit Tests for Voice Pipeline, STT/TTS & WebSocket Streams
"""

import asyncio
import base64
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token
from app.db.base import SessionFactory
from app.main import app
from app.models.agent import AgentConfig
from app.models.business import Business
from app.models.call import Call, CallStatus
from app.voice.audio_utils import pcm16_to_mulaw_bytes
from app.voice.pipeline import VoicePipeline, split_into_sentences
from app.voice.session import CallSession
from app.voice.stt import pcm_to_wav_bytes, transcribe_audio_pcm
from app.voice.tts import generate_mock_mulaw_tone, synthesize_speech


def test_split_into_sentences():
    text = "Hello there! Welcome to our clinic. How can I help you today?"
    sentences = split_into_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Hello there!"
    assert sentences[1] == "Welcome to our clinic."
    assert sentences[2] == "How can I help you today?"

    single = "Just one sentence."
    assert split_into_sentences(single) == ["Just one sentence."]


def test_pcm_to_wav_bytes():
    pcm = b"\x00\x00" * 160  # 160 samples (20ms at 8kHz)
    wav = pcm_to_wav_bytes(pcm, sample_rate=8000)
    assert wav.startswith(b"RIFF")
    assert b"WAVE" in wav
    assert len(wav) == 44 + len(pcm)


@pytest.mark.asyncio
async def test_transcribe_audio_pcm_discards_short_noise():
    # Only 10 bytes (under minimum threshold)
    transcript, latency = await transcribe_audio_pcm(b"\x00" * 10, sample_rate=8000)
    assert transcript == ""
    assert latency == 0


@pytest.mark.asyncio
async def test_synthesize_speech_fallback_tone():
    # Without external API keys, fallback returns valid 8kHz mu-law audio
    mulaw, latency_ms = await synthesize_speech("Hello, your booking is confirmed.")
    assert len(mulaw) > 0
    assert latency_ms >= 0


@pytest.mark.asyncio
async def test_call_session_barge_in_interruption():
    session = CallSession(
        call_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_phone="+919876543210",
        customer_name="Test User",
        business_name="Test Clinic",
    )
    session.is_speaking = True

    # Simulate active playback task
    async def dummy():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy())
    session.current_playback_task = task

    # Trigger interrupt
    session.interrupt_playback()
    assert session.is_speaking is False
    assert session.current_playback_task is None
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.cancelled()


@pytest.mark.asyncio
async def test_pipeline_finalize_call():
    mock_db = AsyncMock()
    mock_call_res = MagicMock()
    mock_call_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_call_res
    mock_db.add = MagicMock()

    class MockContextManager:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session = CallSession(
        call_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_phone="+919876543210",
        customer_name="Aman",
        business_name="Aman Clinic",
    )
    session.stt_latencies = [150, 180]
    session.llm_latencies = [220, 240]
    session.tts_latencies = [40, 50]
    session.conversation_history = [
        {"role": "user", "content": "I want an appointment."},
        {"role": "assistant", "content": "Certainly, let me check slots."},
    ]

    mock_ws = AsyncMock()
    pipeline = VoicePipeline(
        websocket=mock_ws,
        session=session,
        session_factory=MockContextManager,
    )

    await pipeline.finalize_call()

    assert session.is_ended is True
    mock_db.commit.assert_awaited_once()
    mock_db.add.assert_called_once()
    saved_call = mock_db.add.call_args[0][0]
    assert saved_call.id == session.call_id
    assert saved_call.status == CallStatus.COMPLETED
    assert saved_call.stt_latency_ms == 165
    assert saved_call.llm_latency_ms == 230
    assert saved_call.tts_latency_ms == 45


def test_carrier_websocket_stream_connect(client):
    """Test connecting to carrier stream and sending start + stop events."""
    with client.websocket_connect("/api/v1/telephony/stream") as websocket:
        # Send start event
        start_payload = {
            "event": "start",
            "start": {"streamSid": "MZ1234567890"},
        }
        websocket.send_text(json.dumps(start_payload))

        # Send stop event
        stop_payload = {"event": "stop"}
        websocket.send_text(json.dumps(stop_payload))


def test_sandbox_websocket_stream_dialog(client):
    """Test connecting to sandbox simulator and sending text."""
    with client.websocket_connect("/api/v1/telephony/sandbox") as websocket:
        # First frame received is the greeting
        greeting_data = websocket.receive_json()
        assert greeting_data.get("event") == "sandbox_audio"

        # Send customer text turn
        text_payload = {
            "event": "sandbox_text",
            "text": "Hello, is this clinic open?",
        }
        websocket.send_text(json.dumps(text_payload))

        # Stop
        stop_payload = {"event": "stop"}
        websocket.send_text(json.dumps(stop_payload))
