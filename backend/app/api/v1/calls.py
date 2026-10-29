"""
app/api/v1/calls.py — Call Logs, Telemetry, and Analytics Endpoints

Routes:
  GET /api/v1/calls                → Paginated call logs (filters: sentiment, phone)
  GET /api/v1/calls/analytics/stats→ Executive KPI metrics for dashboard
  GET /api/v1/calls/export/csv     → Export call records to CSV
  GET /api/v1/calls/{call_id}      → Full call details and dialog transcript
"""

import csv
import io
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
)
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.business import Business
from app.models.call import Call, CallSentiment
from app.schemas.call import (
    CallListResponse,
    CallResponse,
    CallStatsResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/calls", tags=["Call Telemetry & Analytics"])


async def _get_tenant_business(session: AsyncSession, tenant_id: uuid.UUID) -> Business:
    result = await session.execute(
        select(Business).where(
            Business.tenant_id == tenant_id,
            Business.is_deleted == False,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()
    if business is None:
        raise NotFoundError("Business profile not configured.", code="BUSINESS_NOT_FOUND")
    return business


@router.get(
    "",
    response_model=CallListResponse,
    status_code=status.HTTP_200_OK,
    summary="List call logs",
)
async def list_calls(
    sentiment: CallSentiment | None = Query(default=None, description="Filter by sentiment"),
    caller_phone: str | None = Query(default=None, description="Search by phone number"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> CallListResponse:
    """Fetch paginated call records."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    query = select(Call).where(
        Call.tenant_id == current_user.tenant_id,
        Call.business_id == business.id,
        Call.is_deleted == False,  # noqa: E712
    )

    if sentiment:
        query = query.where(Call.sentiment == sentiment)

    if caller_phone:
        query = query.where(Call.caller_phone.ilike(f"%{caller_phone}%"))

    query = query.order_by(Call.started_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    calls = result.scalars().all()

    return CallListResponse(
        items=[CallResponse.model_validate(c) for c in calls],
        total=len(calls),
    )


@router.get(
    "/analytics/stats",
    response_model=CallStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated dashboard KPI statistics",
)
async def get_call_stats(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> CallStatsResponse:
    """Calculate operational KPIs across calls."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    result = await session.execute(
        select(Call).where(
            Call.tenant_id == current_user.tenant_id,
            Call.business_id == business.id,
            Call.is_deleted == False,  # noqa: E712
        )
    )
    calls = list(result.scalars().all())

    total_calls = len(calls)
    if total_calls == 0:
        return CallStatsResponse(
            total_calls=0,
            total_duration_minutes=0,
            avg_duration_seconds=0.0,
            total_cost_usd=0.0,
            sentiment_breakdown={"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
            avg_stt_latency_ms=0,
            avg_llm_latency_ms=0,
            avg_tts_latency_ms=0,
            avg_e2e_latency_ms=0,
        )

    total_dur_sec = sum(c.duration_seconds for c in calls)
    total_cost_cents = sum(c.cost_cents for c in calls)
    avg_stt = int(sum(c.stt_latency_ms for c in calls) / total_calls)
    avg_llm = int(sum(c.llm_latency_ms for c in calls) / total_calls)
    avg_tts = int(sum(c.tts_latency_ms for c in calls) / total_calls)

    sentiment_counts = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
    for c in calls:
        sentiment_counts[c.sentiment.value] = sentiment_counts.get(c.sentiment.value, 0) + 1

    return CallStatsResponse(
        total_calls=total_calls,
        total_duration_minutes=total_dur_sec // 60,
        avg_duration_seconds=round(total_dur_sec / total_calls, 1),
        total_cost_usd=round(total_cost_cents / 100.0, 2),
        sentiment_breakdown=sentiment_counts,
        avg_stt_latency_ms=avg_stt,
        avg_llm_latency_ms=avg_llm,
        avg_tts_latency_ms=avg_tts,
        avg_e2e_latency_ms=avg_stt + avg_llm + avg_tts,
    )


@router.get(
    "/export/csv",
    status_code=status.HTTP_200_OK,
    summary="Export call logs to CSV",
)
async def export_calls_csv(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Download call records as CSV."""
    business = await _get_tenant_business(session, current_user.tenant_id)

    result = await session.execute(
        select(Call)
        .where(
            Call.tenant_id == current_user.tenant_id,
            Call.business_id == business.id,
            Call.is_deleted == False,  # noqa: E712
        )
        .order_by(Call.started_at.desc())
    )
    calls = list(result.scalars().all())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Call ID",
            "Caller Phone",
            "Direction",
            "Status",
            "Started At",
            "Duration (s)",
            "Sentiment",
            "Intent",
            "Cost ($)",
            "STT Latency (ms)",
            "LLM Latency (ms)",
            "TTS Latency (ms)",
            "Notes",
        ]
    )

    for c in calls:
        writer.writerow(
            [
                str(c.id),
                c.caller_phone,
                c.direction.value,
                c.status.value,
                c.started_at.isoformat(),
                c.duration_seconds,
                c.sentiment.value,
                c.intent or "",
                f"{c.cost_cents / 100.0:.2f}",
                c.stt_latency_ms,
                c.llm_latency_ms,
                c.tts_latency_ms,
                c.notes or "",
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="call_report.csv"'},
    )


@router.get(
    "/{call_id}",
    response_model=CallResponse,
    status_code=status.HTTP_200_OK,
    summary="Get call by ID",
)
async def get_call_by_id(
    call_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> CallResponse:
    """Fetch single call log with transcript."""
    result = await session.execute(
        select(Call).where(
            Call.id == call_id,
            Call.tenant_id == current_user.tenant_id,
            Call.is_deleted == False,  # noqa: E712
        )
    )
    call = result.scalar_one_or_none()
    if call is None:
        raise NotFoundError("Call record not found.", code="CALL_NOT_FOUND")

    return CallResponse.model_validate(call)

