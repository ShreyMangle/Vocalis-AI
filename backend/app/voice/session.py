"""
app/voice/session.py — In-Memory Voice Session State

Manages real-time state for active phone calls & browser sandbox sessions.
Tracks hydrated AgentConfig runtime settings, VAD audio buffers, turn concurrency
locks, barge-in cancellation flags, and per-stage latency telemetry.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.models.agent import AgentConfig
from app.models.call import CallDirection, CallSentiment
from app.voice.audio_utils import MulawVADDetector

VAD_ENERGY_THRESHOLDS: dict[str, float] = {
    "low": 900.0,
    "normal": 600.0,
    "high": 350.0,
}


@dataclass
class CallSession:
    """Live state of an ongoing telephony or sandbox voice session."""

    call_id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID
    customer_phone: str
    customer_name: str
    business_name: str
    appointment_id: uuid.UUID | None = None
    direction: CallDirection = CallDirection.INBOUND

    # Telephony stream identifiers
    stream_sid: str | None = None
    is_sandbox: bool = False

    # Hydrated AgentConfig runtime settings
    agent_config: AgentConfig | None = None
    agent_name: str = "Sarah"
    role_description: str = "Front desk receptionist and appointment scheduling coordinator"
    custom_system_prompt: str | None = None
    greeting_message: str = "Hello! Thank you for calling. How can I assist you today?"
    fallback_message: str = "I apologize, I am experiencing a brief connection glitch. Could you please repeat that?"
    voice_id: str = field(default_factory=lambda: settings.DEFAULT_TTS_VOICE)
    voice_provider: str = field(default_factory=lambda: settings.DEFAULT_TTS_PROVIDER)
    speech_speed: float = 1.0
    llm_provider: str = field(default_factory=lambda: settings.DEFAULT_LLM_PROVIDER)
    llm_model: str = field(default_factory=lambda: settings.DEFAULT_LLM_MODEL)
    temperature: float = 0.3
    vad_sensitivity: str = "normal"
    barge_in_enabled: bool = True
    primary_language: str = "en-IN"
    supported_languages: list[str] = field(default_factory=lambda: ["en-IN", "hi-IN"])
    transfer_phone: str | None = None
    webhook_url: str | None = None
    sms_enabled: bool = True

    # Conversational state
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    call_action: str | None = None  # None | "transfer" | "hangup"
    sentiment: CallSentiment = CallSentiment.NEUTRAL
    intent: str | None = None
    call_summary: str | None = None
    is_ended: bool = False

    # Concurrency & barge-in interruption state
    is_speaking: bool = False
    stream_ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    current_playback_task: asyncio.Task | None = None
    current_turn_task: asyncio.Task | None = None
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_turn_id: int = 0
    in_db_io: bool = False

    # VAD audio buffer
    vad: MulawVADDetector = field(default_factory=lambda: MulawVADDetector(energy_threshold=600.0))

    # Latency meters (milliseconds per turn)
    stt_latencies: list[int] = field(default_factory=list)
    llm_latencies: list[int] = field(default_factory=list)
    tts_latencies: list[int] = field(default_factory=list)

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.agent_config is not None:
            self.apply_agent_config(self.agent_config)

    def apply_agent_config(self, config: AgentConfig | None) -> None:
        """Copy all AgentConfig fields safely so disconnected ORM sessions never raise."""
        if config is None:
            return
        self.agent_config = config
        self.agent_name = config.name or self.agent_name
        self.role_description = config.role_description or self.role_description
        self.custom_system_prompt = config.system_prompt
        if config.greeting_message:
            self.greeting_message = config.greeting_message
        if config.fallback_message:
            self.fallback_message = config.fallback_message
        self.voice_provider = config.voice_provider or self.voice_provider
        self.voice_id = config.voice_id or self.voice_id
        self.speech_speed = config.speech_speed if config.speech_speed is not None else self.speech_speed
        self.llm_provider = config.llm_provider or self.llm_provider
        self.llm_model = config.llm_model or self.llm_model
        self.temperature = config.temperature if config.temperature is not None else self.temperature
        self.vad_sensitivity = (config.vad_sensitivity or "normal").lower()
        self.primary_language = config.primary_language or self.primary_language
        self.supported_languages = list(config.supported_languages or ["en-IN", "hi-IN"])
        self.transfer_phone = config.transfer_phone_number
        self.webhook_url = config.webhook_url
        self.sms_enabled = config.sms_enabled
        self.vad.energy_threshold = VAD_ENERGY_THRESHOLDS.get(self.vad_sensitivity, 600.0)

    def begin_turn(self) -> int:
        """Advance turn generation counter and return the new turn ID."""
        self.active_turn_id += 1
        return self.active_turn_id

    def interrupt_playback(self) -> None:
        """Immediate barge-in: abort currently playing audio chunks."""
        self.is_speaking = False
        if self.current_playback_task and not self.current_playback_task.done():
            self.current_playback_task.cancel()
            self.current_playback_task = None

    def cancel_active_turn(self) -> None:
        """Invalidate pending turns, cancel active LLM reasoning when safe, and silence TTS playback."""
        self.active_turn_id += 1
        self.interrupt_playback()
        if self.current_turn_task and not self.current_turn_task.done() and not self.in_db_io:
            current = asyncio.current_task()
            if self.current_turn_task is not current:
                self.current_turn_task.cancel()
            self.current_turn_task = None
