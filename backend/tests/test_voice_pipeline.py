"""
tests/test_voice_pipeline.py — Unit Tests for Voice Pipeline, STT/TTS & WebSocket Streams
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, LLMStreamChunk
from app.models.agent import AgentConfig
from app.models.call import CallStatus
from app.voice.pipeline import VoicePipeline, extract_speakable_clauses, split_into_sentences
from app.voice.session import CallSession
from app.voice.stt import pcm_to_wav_bytes, transcribe_audio_pcm
from app.voice.tts import synthesize_speech


def test_split_into_sentences():
    text = "Hello there! Welcome to our clinic. How can I help you today?"
    sentences = split_into_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "Hello there!"
    assert sentences[1] == "Welcome to our clinic."
    assert sentences[2] == "How can I help you today?"

    single = "Just one sentence."
    assert split_into_sentences(single) == ["Just one sentence."]


def test_extract_speakable_clauses_preserves_abbreviations_and_splits_long_clauses():
    buf = "Dr. Sharma has a consultation at 10.5 AM tomorrow. Shall I book it for you? Yes"
    clauses, remaining = extract_speakable_clauses(buf, flush=False)
    assert clauses == [
        "Dr. Sharma has a consultation at 10.5 AM tomorrow.",
        "Shall I book it for you?",
    ]
    assert remaining == "Yes"

    long_buf = "We offer dental cleanings, root canal therapy, orthodontics, and pediatric care, "
    clauses2, rem2 = extract_speakable_clauses(long_buf, flush=False)
    assert len(clauses2) == 1
    assert clauses2[0].endswith(",")
    assert rem2 == ""


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

    async def dummy():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy())
    session.current_playback_task = task

    session.interrupt_playback()
    assert session.is_speaking is False
    assert session.current_playback_task is None
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert task.cancelled()


def test_call_session_hydrates_agent_config():
    config = AgentConfig(
        tenant_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        name="Priya",
        role_description="Medical Concierge",
        system_prompt="Always confirm patient age.",
        greeting_message="Namaste! Welcome to Sunrise Clinic.",
        fallback_message="Sorry, could you repeat that?",
        voice_provider="edge",
        voice_id="en-IN-NeerjaNeural",
        speech_speed=1.1,
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
        temperature=0.2,
        vad_sensitivity="high",
        primary_language="hi-IN",
        supported_languages=["hi-IN", "en-IN"],
        transfer_phone_number="+919999988888",
        sms_enabled=False,
    )
    session = CallSession(
        call_id=uuid.uuid4(),
        tenant_id=config.tenant_id,
        business_id=config.business_id,
        customer_phone="+919876543210",
        customer_name="Caller",
        business_name="Sunrise Clinic",
        agent_config=config,
    )
    assert session.agent_name == "Priya"
    assert session.llm_provider == "gemini"
    assert session.llm_model == "gemini-2.0-flash"
    assert session.temperature == 0.2
    assert session.voice_provider == "edge"
    assert session.voice_id == "en-IN-NeerjaNeural"
    assert session.vad_sensitivity == "high"
    assert session.vad.energy_threshold == 350.0
    assert session.transfer_phone == "+919999988888"
    assert session.custom_system_prompt == "Always confirm patient age."


@pytest.mark.asyncio
async def test_pipeline_streaming_react_tool_loop():
    class ScriptedReActProvider(BaseLLMProvider):
        def __init__(self):
            super().__init__(model="gemini-2.0-flash", temperature=0.2)
            self.calls: list[list[LLMMessage]] = []

        async def complete(self, messages, tools=None, **kwargs):
            raise NotImplementedError

        async def stream(self, messages, tools=None, **kwargs):
            yield ""

        async def stream_events(self, messages, tools=None, **kwargs):
            self.calls.append(list(messages))
            if len(self.calls) == 1:
                yield LLMStreamChunk(
                    done=True,
                    tool_calls=[
                        {
                            "id": "call_avail_1",
                            "type": "function",
                            "function": {
                                "name": "check_availability",
                                "arguments": '{"target_date": "2026-11-28"}',
                            },
                        }
                    ],
                    provider="gemini",
                    model=self.model,
                    latency_ms=45,
                )
            else:
                yield LLMStreamChunk(text_delta="We have openings tomorrow. ", provider="gemini", model=self.model)
                yield LLMStreamChunk(text_delta="Would 10 AM work?", provider="gemini", model=self.model)
                yield LLMStreamChunk(done=True, provider="gemini", model=self.model, latency_ms=55)

    mock_db = AsyncMock()
    mock_empty_res = MagicMock()
    mock_empty_res.scalar_one_or_none.return_value = None
    mock_empty_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_empty_res

    class MockCM:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session = CallSession(
        call_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_phone="+919876543210",
        customer_name="Riya",
        business_name="Sunrise Clinic",
        is_sandbox=True,
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )
    mock_ws = AsyncMock()
    pipeline = VoicePipeline(websocket=mock_ws, session=session, session_factory=MockCM)
    fake_llm = ScriptedReActProvider()

    mock_tool_res = MagicMock()
    mock_tool_res.action = None
    mock_tool_res.success = True
    mock_tool_res.message = "Slots at 10:00 AM and 2:00 PM."
    mock_tool_res.data = {"slots": ["10:00", "14:00"]}
    mock_tool_res.to_dict.return_value = {
        "tool_name": "check_availability",
        "success": True,
        "message": "Slots at 10:00 AM and 2:00 PM.",
        "data": {"slots": ["10:00", "14:00"]},
        "action": None,
    }

    with (
        patch("app.voice.pipeline.get_llm_provider", return_value=fake_llm),
        patch("app.voice.pipeline.ToolExecutor.execute", new=AsyncMock(return_value=mock_tool_res)) as mock_exec,
    ):
        await pipeline.process_utterance("What slots are open on 2026-11-28?")

    assert len(fake_llm.calls) == 2
    second_call_msgs = fake_llm.calls[1]
    assert any(m.role == "assistant" and m.tool_calls for m in second_call_msgs)
    tool_msgs = [m for m in second_call_msgs if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "10:00" in (tool_msgs[0].content or "")
    mock_exec.assert_awaited_once_with("check_availability", {"target_date": "2026-11-28"})

    sent_events = [call.args[0] for call in mock_ws.send_json.call_args_list]
    assert any(ev.get("event") == "tool_call" and ev.get("tool") == "check_availability" for ev in sent_events)
    audio_texts = [ev.get("text") for ev in sent_events if ev.get("event") == "sandbox_audio"]
    assert audio_texts == ["We have openings tomorrow.", "Would 10 AM work?"]
    assert session.conversation_history[-1] == {
        "role": "assistant",
        "content": "We have openings tomorrow. Would 10 AM work?",
    }


@pytest.mark.asyncio
async def test_pipeline_turn_concurrency_cancels_stale_turn():
    turn_started = asyncio.Event()

    class SlowThenFastProvider(BaseLLMProvider):
        def __init__(self):
            super().__init__(model="groq", temperature=0.3)

        async def complete(self, messages, tools=None, **kwargs):
            return LLMResponse(content="OK", provider="groq", model=self.model)

        async def stream(self, messages, tools=None, **kwargs):
            yield "OK"

        async def stream_events(self, messages, tools=None, **kwargs):
            last_user = [m for m in messages if m.role == "user"][-1].content
            if last_user == "First slow utterance":
                turn_started.set()
                await asyncio.sleep(5)
                yield LLMStreamChunk(text_delta="Stale reply.", provider="groq", model=self.model)
            else:
                yield LLMStreamChunk(text_delta="Fresh priority reply.", provider="groq", model=self.model)
            yield LLMStreamChunk(done=True, provider="groq", model=self.model)

    mock_db = AsyncMock()
    mock_empty_res = MagicMock()
    mock_empty_res.scalar_one_or_none.return_value = None
    mock_empty_res.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_empty_res

    class MockCM:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session = CallSession(
        call_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        customer_phone="+919876543210",
        customer_name="Riya",
        business_name="Sunrise Clinic",
        is_sandbox=True,
    )
    mock_ws = AsyncMock()
    pipeline = VoicePipeline(websocket=mock_ws, session=session, session_factory=MockCM)

    with patch("app.voice.pipeline.get_llm_provider", return_value=SlowThenFastProvider()):
        first_task = pipeline.schedule_utterance("First slow utterance")
        await turn_started.wait()
        second_task = pipeline.schedule_utterance("Second urgent utterance")
        await second_task
        try:
            await first_task
        except asyncio.CancelledError:
            pass

    assistant_turns = [m["content"] for m in session.conversation_history if m["role"] == "assistant"]
    assert assistant_turns == ["Fresh priority reply."]


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
        start_payload = {
            "event": "start",
            "start": {"streamSid": "MZ1234567890"},
        }
        websocket.send_text(json.dumps(start_payload))

        stop_payload = {"event": "stop"}
        websocket.send_text(json.dumps(stop_payload))


def test_sandbox_websocket_stream_dialog(client):
    """Test connecting to sandbox simulator and sending text."""
    with client.websocket_connect("/api/v1/telephony/sandbox") as websocket:
        greeting_data = websocket.receive_json()
        assert greeting_data.get("event") == "sandbox_audio"

        text_payload = {
            "event": "sandbox_text",
            "text": "Hello, is this clinic open?",
        }
        websocket.send_text(json.dumps(text_payload))

        stop_payload = {"event": "stop"}
        websocket.send_text(json.dumps(stop_payload))
