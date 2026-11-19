"""
app/voice/session.py — In-Memory Voice Session State

Manages real-time state for active phone calls & browser sandbox sessions.
Tracks VAD audio buffers, conversation turns, barge-in flags, and latency telemetry.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.models.agent import AgentConfig
from app.models.call import CallDirection, CallSentiment, CallStatus
from app.voice.audio_utils import MulawVADDetector


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

    # Agent configuration
    agent_name: str = "Sarah"
    voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091"
    voice_provider: str = "cartesia"
    speech_speed: float = 1.0
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

    # Audio playback & barge-in interruption state
    is_speaking: bool = False
    stream_ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    current_playback_task: asyncio.Task | None = None

    # VAD audio buffer
    vad: MulawVADDetector = field(default_factory=lambda: MulawVADDetector(energy_threshold=600.0))

    # Latency meters (milliseconds per turn)
    stt_latencies: list[int] = field(default_factory=list)
    llm_latencies: list[int] = field(default_factory=list)
    tts_latencies: list[int] = field(default_factory=list)

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def interrupt_playback(self) -> None:
        """Immediate barge-in: abort currently playing audio chunks."""
        self.is_speaking = False
        if self.current_playback_task and not self.current_playback_task.done():
            self.current_playback_task.cancel()
            self.current_playback_task = None
