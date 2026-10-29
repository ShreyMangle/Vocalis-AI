"""
app/schemas/call.py — Telephony Call Analytics Schemas

Pydantic schemas for:
  - Reading call detail logs and transcripts
  - Filtering and pagination
  - Summary KPI telemetry dashboards
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.call import CallDirection, CallSentiment, CallStatus


class CallResponse(BaseModel):
    """Public representation of a telephony call record."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID
    appointment_id: uuid.UUID | None
    caller_phone: str
    direction: CallDirection
    status: CallStatus
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    recording_url: str | None
    transcript: list[dict[str, Any]]
    sentiment: CallSentiment
    intent: str | None
    notes: str | None
    stt_latency_ms: int
    llm_latency_ms: int
    tts_latency_ms: int
    cost_cents: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CallListResponse(BaseModel):
    """List response wrapping call logs."""
    items: list[CallResponse]
    total: int


class CallStatsResponse(BaseModel):
    """Aggregated operational metrics for dashboard KPI cards."""
    total_calls: int
    total_duration_minutes: int
    avg_duration_seconds: float
    total_cost_usd: float
    sentiment_breakdown: dict[str, int]
    avg_stt_latency_ms: int
    avg_llm_latency_ms: int
    avg_tts_latency_ms: int
    avg_e2e_latency_ms: int

