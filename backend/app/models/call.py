"""
app/models/call.py — Telephony Call Record & Analytics Model

CONCEPT: Call Telemetry in Voice AI
====================================
Every phone interaction is recorded with:
  - Direction: Inbound customer call vs outbound confirmation/reminder campaign
  - Operational metrics: Duration, audio recording URL, structured conversation transcript
  - Latency breakdown: STT transcription ms, LLM generation ms, TTS synthesis ms
  - AI Intelligence: Sentiment extraction (Positive/Neutral/Negative), primary caller intent
  - Cost accounting: Token usage and carrier telephony costs in cents
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class CallDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class CallStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BUSY = "BUSY"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"


class CallSentiment(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class Call(Base, TimestampMixin, SoftDeleteMixin):
    """Represents a telephony voice session and performance telemetry."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant isolation key",
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated business profile",
    )

    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Associated appointment if booked or discussed during call",
    )

    caller_phone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Caller or recipient phone number",
    )

    direction: Mapped[CallDirection] = mapped_column(
        Enum(CallDirection, name="calldirection"),
        nullable=False,
        default=CallDirection.INBOUND,
        server_default=CallDirection.INBOUND.value,
        comment="Call direction: INBOUND or OUTBOUND",
    )

    status: Mapped[CallStatus] = mapped_column(
        Enum(CallStatus, name="callstatus"),
        nullable=False,
        default=CallStatus.COMPLETED,
        server_default=CallStatus.COMPLETED.value,
        index=True,
        comment="Final call connection status",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Call connection timestamp",
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Call termination timestamp",
    )

    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Call talk time in seconds",
    )

    recording_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="S3 or cloud storage audio recording URL",
    )

    transcript: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
        comment="Chronological list of dialog turns [{'role': 'user', 'content': '...'}]",
    )

    sentiment: Mapped[CallSentiment] = mapped_column(
        Enum(CallSentiment, name="callsentiment"),
        nullable=False,
        default=CallSentiment.NEUTRAL,
        server_default=CallSentiment.NEUTRAL.value,
        index=True,
        comment="Sentiment analysis classification",
    )

    intent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Extracted primary purpose (e.g. 'Appointment Booking')",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI executive summary of call conversation",
    )

    # ── Latency Telemetry (milliseconds) ─────────────────────────────────────
    stt_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Speech-to-text average transcription latency",
    )

    llm_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="LLM time-to-first-token latency",
    )

    tts_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Text-to-speech first audio chunk latency",
    )

    cost_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Estimated cost in US cents",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    appointment: Mapped["Appointment | None"] = relationship(  # noqa: F821
        "Appointment",
    )

    __table_args__ = (
        Index("ix_calls_tenant_started", "tenant_id", "started_at"),
        Index("ix_calls_business_sentiment", "business_id", "sentiment"),
    )

    def __repr__(self) -> str:
        return f"<Call id={self.id} phone={self.caller_phone} duration={self.duration_seconds}s>"

