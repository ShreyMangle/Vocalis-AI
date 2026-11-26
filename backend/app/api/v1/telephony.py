"""
app/api/v1/telephony.py — Carrier Telephony Webhooks & Outbound Dispatch

Routes:
  GET|POST /api/v1/telephony/voice         → Twilio/VoBiz incoming call webhook (returns TwiML)
  POST     /api/v1/telephony/outbound-call → Dispatch automated outbound customer call
  GET      /api/v1/telephony/status        → Check telephony carrier readiness
"""

import base64
import json
import uuid
from typing import Any

import httpx
import structlog
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.db.base import SessionFactory
from app.models.agent import AgentConfig
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.tenant_user import UserRole
from app.schemas.telephony import (
    OutboundCallRequest,
    OutboundCallResponse,
    TelephonyStatusResponse,
)
from app.voice.pipeline import VoicePipeline
from app.voice.session import CallSession

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/telephony", tags=["Telephony Integration"])


@router.api_route(
    "/voice",
    methods=["GET", "POST"],
    summary="Twilio / VoBiz inbound call webhook",
)
async def twilio_voice_webhook(
    request: Request,
    appointment_id: str | None = Query(default=None, alias="appointmentId"),
    call_sid: str | None = Query(default=None, alias="CallSid"),
) -> Response:
    """
    Twilio voice entrypoint.
    Returns TwiML instruction instructing Twilio to open a bidirectional
    media stream WebSocket with the VoxAI voice pipeline.
    """
    host = request.headers.get("host", "localhost:8000")
    protocol = "wss" if "https" in request.base_url.scheme or "ngrok" in host else "ws"
    stream_url = f"{protocol}://{host}/api/v1/telephony/stream"

    param_appointment = f'<Parameter name="appointmentId" value="{appointment_id}" />' if appointment_id else ""
    param_call_sid = f'<Parameter name="callSid" value="{call_sid}" />' if call_sid else ""

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            {param_appointment}
            {param_call_sid}
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml, media_type="application/xml")


@router.get(
    "/status",
    response_model=TelephonyStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get telephony configuration status",
)
async def get_telephony_status(
    current_user: CurrentUser = Depends(require_authenticated),
) -> TelephonyStatusResponse:
    """Returns whether VoBiz (primary for India) or Twilio credentials and numbers are configured."""
    provider = settings.DEFAULT_TELEPHONY_PROVIDER.lower()
    vobiz_ok = bool(settings.VOBIZ_API_KEY and settings.VOBIZ_ACCOUNT_ID and settings.VOBIZ_PHONE_NUMBER)
    twilio_ok = bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_PHONE_NUMBER)

    if provider == "vobiz":
        has_account = bool(settings.VOBIZ_API_KEY and settings.VOBIZ_ACCOUNT_ID)
        has_phone = bool(settings.VOBIZ_PHONE_NUMBER)
        active_number = settings.VOBIZ_PHONE_NUMBER
    else:
        has_account = bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)
        has_phone = bool(settings.TWILIO_PHONE_NUMBER)
        active_number = settings.TWILIO_PHONE_NUMBER

    return TelephonyStatusResponse(
        provider=settings.DEFAULT_TELEPHONY_PROVIDER,
        is_configured=has_account and has_phone,
        phone_number_configured=has_phone,
        account_configured=has_account,
        vobiz_configured=vobiz_ok,
        twilio_configured=twilio_ok,
        active_number=active_number,
    )


@router.post(
    "/outbound-call",
    response_model=OutboundCallResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger outbound telephone call",
)
async def trigger_outbound_call(
    payload: OutboundCallRequest,
    request: Request,
    current_user: CurrentUser = Depends(
        require_role(UserRole.OWNER, UserRole.ADMIN)
    ),
) -> OutboundCallResponse:
    """
    Initiates an outbound phone call to a customer using VoBiz (or Twilio fallback).
    If credentials are not yet set in environment, runs in safe simulation mode.
    """
    provider = settings.DEFAULT_TELEPHONY_PROVIDER.lower()

    # ── VoBiz Carrier Path (India TRAI-compliant primary) ────────────────────
    if provider == "vobiz":
        has_vobiz = bool(settings.VOBIZ_API_KEY and settings.VOBIZ_PHONE_NUMBER)
        if not has_vobiz:
            simulated_sid = f"VOBIZ_SIM_{uuid.uuid4().hex[:16]}"
            logger.info(
                "Outbound VoBiz call simulated (no VoBiz credentials configured)",
                to_phone=payload.to_phone,
                simulated_sid=simulated_sid,
                tenant_id=str(current_user.tenant_id),
            )
            return OutboundCallResponse(
                status="simulation_initiated",
                call_sid=simulated_sid,
                to_phone=payload.to_phone,
                from_phone=settings.VOBIZ_PHONE_NUMBER or "+918000012345",
                message="Call dispatched in simulation mode via VoBiz. Configure VOBIZ_API_KEY and VOBIZ_PHONE_NUMBER for live India PSTN routing.",
            )

        host = request.headers.get("host", "localhost:8000")
        protocol = "https" if "https" in request.base_url.scheme or "ngrok" in host else "http"
        answer_url = f"{protocol}://{host}/api/v1/telephony/voice"
        if payload.appointment_id:
            answer_url += f"?appointmentId={payload.appointment_id}"

        url = (
            f"{settings.VOBIZ_BASE_URL}/accounts/{settings.VOBIZ_ACCOUNT_ID}/calls"
            if settings.VOBIZ_ACCOUNT_ID
            else f"{settings.VOBIZ_BASE_URL}/calls"
        )
        headers = {
            "Authorization": f"Bearer {settings.VOBIZ_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "to": payload.to_phone,
            "from": settings.VOBIZ_PHONE_NUMBER,
            "answer_url": answer_url,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=body, headers=headers, timeout=10.0)

            if resp.status_code in (200, 201, 202):
                resp_data = resp.json()
                call_sid = resp_data.get("call_id") or resp_data.get("sid") or "vobiz_call"
                logger.info("Outbound call successfully queued with VoBiz", call_sid=call_sid)
                return OutboundCallResponse(
                    status="queued",
                    call_sid=call_sid,
                    to_phone=payload.to_phone,
                    from_phone=settings.VOBIZ_PHONE_NUMBER,
                    message="Call successfully queued with VoBiz carrier.",
                )
            else:
                logger.error("VoBiz API error", status_code=resp.status_code, response=resp.text)
                return OutboundCallResponse(
                    status="error",
                    call_sid="",
                    to_phone=payload.to_phone,
                    from_phone=settings.VOBIZ_PHONE_NUMBER,
                    message=f"VoBiz carrier error: {resp.text}",
                )
        except Exception as e:
            logger.error("Failed to connect to VoBiz REST API", error=str(e))
            return OutboundCallResponse(
                status="failed",
                call_sid="",
                to_phone=payload.to_phone,
                from_phone=settings.VOBIZ_PHONE_NUMBER,
                message=f"VoBiz connection exception: {str(e)}",
            )

    # ── Twilio Carrier Path (Global fallback) ────────────────────────────────
    has_twilio = bool(
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_PHONE_NUMBER
    )

    if not has_twilio:
        simulated_sid = f"TWILIO_SIM_{uuid.uuid4().hex[:16]}"
        logger.info(
            "Outbound Twilio call simulated (no Twilio credentials configured)",
            to_phone=payload.to_phone,
            simulated_sid=simulated_sid,
            tenant_id=str(current_user.tenant_id),
        )
        return OutboundCallResponse(
            status="simulation_initiated",
            call_sid=simulated_sid,
            to_phone=payload.to_phone,
            from_phone=settings.TWILIO_PHONE_NUMBER or "+15005550006",
            message="Call dispatched in simulation mode. Configure TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN for live carrier routing.",
        )

    host = request.headers.get("host", "localhost:8000")
    protocol = "https" if "https" in request.base_url.scheme or "ngrok" in host else "http"
    twiml_url = f"{protocol}://{host}/api/v1/telephony/voice"
    if payload.appointment_id:
        twiml_url += f"?appointmentId={payload.appointment_id}"

    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    from_phone = settings.TWILIO_PHONE_NUMBER

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    data = {
        "To": payload.to_phone,
        "From": from_phone,
        "Url": twiml_url,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data=data,
                auth=(account_sid, auth_token),
                timeout=10.0,
            )

        if resp.status_code in (200, 201):
            resp_data = resp.json()
            call_sid = resp_data.get("sid", "unknown")
            logger.info("Outbound call successfully queued with Twilio", call_sid=call_sid)
            return OutboundCallResponse(
                status="queued",
                call_sid=call_sid,
                to_phone=payload.to_phone,
                from_phone=from_phone,
                message="Call successfully queued with carrier.",
            )
        else:
            logger.error("Twilio API error", status_code=resp.status_code, response=resp.text)
            return OutboundCallResponse(
                status="error",
                call_sid="",
                to_phone=payload.to_phone,
                from_phone=from_phone,
                message=f"Carrier error: {resp.text}",
            )
    except Exception as e:
        logger.error("Failed to connect to Twilio REST API", error=str(e))
        return OutboundCallResponse(
            status="failed",
            call_sid="",
            to_phone=payload.to_phone,
            from_phone=from_phone,
            message=f"Network exception: {str(e)}",
        )


# =============================================================================
# REAL-TIME VOICE PIPELINE WEBSOCKETS
# =============================================================================

@router.websocket("/stream")
async def carrier_voice_stream(
    websocket: WebSocket,
    appointmentId: str | None = Query(default=None),
    callId: str | None = Query(default=None),
) -> None:
    """
    Bidirectional media stream WebSocket handler for VoBiz & Twilio telephony carriers.
    Streams 8kHz G.711 mu-law audio frames and handles real-time barge-in and tool calling.
    """
    await websocket.accept()
    logger.info("Carrier WebSocket media stream connected", appointment_id=appointmentId, call_id=callId)

    call_uuid = uuid.UUID(callId) if callId else uuid.uuid4()
    tenant_id = uuid.uuid4()
    business_id = uuid.uuid4()
    business_name = "Clinic Reception"
    customer_name = "Valued Customer"
    customer_phone = "+919876543210"
    appt_uuid = None
    greeting_override = None
    agent_config = None

    # Load operational entities from database (gracefully fallback if DB offline)
    try:
        async with SessionFactory() as db:
            if appointmentId:
                try:
                    appt_uuid = uuid.UUID(appointmentId)
                    res = await db.execute(
                        select(Appointment).where(Appointment.id == appt_uuid)
                    )
                    appt = res.scalar_one_or_none()
                    if appt:
                        tenant_id = appt.tenant_id
                        business_id = appt.business_id
                        customer_name = appt.customer_name
                        customer_phone = appt.customer_phone
                except Exception as e:
                    logger.warning("Could not parse appointmentId", error=str(e))

            # Query Business profile
            b_res = await db.execute(
                select(Business).where(Business.id == business_id)
            )
            business = b_res.scalar_one_or_none()
            if not business:
                b_first = await db.execute(select(Business).limit(1))
                business = b_first.scalar_one_or_none()
                if business:
                    business_id = business.id
                    tenant_id = business.tenant_id

            if business:
                business_name = business.name

            # Query Agent configuration
            a_res = await db.execute(
                select(AgentConfig).where(AgentConfig.tenant_id == tenant_id)
            )
            agent_config = a_res.scalar_one_or_none()
            if agent_config and agent_config.greeting_message:
                greeting_override = agent_config.greeting_message
    except Exception as dbe:
        logger.warning("Could not connect to database on stream startup, using in-memory defaults", error=str(dbe))

    call_session = CallSession(
        call_id=call_uuid,
        tenant_id=tenant_id,
        business_id=business_id,
        customer_phone=customer_phone,
        customer_name=customer_name,
        business_name=business_name,
        appointment_id=appt_uuid,
        is_sandbox=False,
        agent_config=agent_config,
    )

    pipeline = VoicePipeline(
        websocket=websocket,
        session=call_session,
        session_factory=SessionFactory,
    )

    # Deliver opening greeting
    await pipeline.send_greeting(greeting_override)

    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            event = data.get("event")

            if event == "start":
                call_session.stream_sid = data.get("start", {}).get("streamSid")
                call_session.stream_ready_event.set()
                logger.info("Carrier stream started", stream_sid=call_session.stream_sid)

            elif event == "media":
                payload = data.get("media", {}).get("payload")
                if payload:
                    chunk = base64.b64decode(payload)
                    await pipeline.handle_audio_chunk(chunk)

            elif event == "stop":
                logger.info("Carrier stream stop signal received")
                break

    except WebSocketDisconnect:
        logger.info("Carrier WebSocket disconnected", call_id=str(call_uuid))
    except Exception as e:
        logger.error("Carrier WebSocket stream exception", error=str(e))
    finally:
        await pipeline.finalize_call()


@router.websocket("/sandbox")
async def browser_sandbox_stream(
    websocket: WebSocket,
    businessId: str | None = Query(default=None),
) -> None:
    """
    Browser-based Sandbox Voice Simulator WebSocket.
    Allows real-time testing of text dialog, microphone streaming, and tool execution.
    """
    await websocket.accept()
    logger.info("Browser Sandbox WebSocket connected")

    call_uuid = uuid.uuid4()
    tenant_id = uuid.uuid4()
    business_id = uuid.uuid4()
    business_name = "Sandbox Medical Clinic"
    greeting_override = None
    agent_config = None

    try:
        async with SessionFactory() as db:
            if businessId:
                try:
                    b_uuid = uuid.UUID(businessId)
                    b_res = await db.execute(select(Business).where(Business.id == b_uuid))
                    b = b_res.scalar_one_or_none()
                    if b:
                        business_id = b.id
                        tenant_id = b.tenant_id
                        business_name = b.name
                except Exception:
                    pass
            else:
                b_first = await db.execute(select(Business).limit(1))
                b = b_first.scalar_one_or_none()
                if b:
                    business_id = b.id
                    tenant_id = b.tenant_id
                    business_name = b.name

            a_res = await db.execute(
                select(AgentConfig).where(AgentConfig.tenant_id == tenant_id)
            )
            agent_config = a_res.scalar_one_or_none()
            if agent_config and agent_config.greeting_message:
                greeting_override = agent_config.greeting_message
    except Exception as dbe:
        logger.warning("Could not connect to database on sandbox startup, using defaults", error=str(dbe))

    call_session = CallSession(
        call_id=call_uuid,
        tenant_id=tenant_id,
        business_id=business_id,
        customer_phone="+919876543210",
        customer_name="Simulator Test Caller",
        business_name=business_name,
        is_sandbox=True,
        agent_config=agent_config,
    )

    pipeline = VoicePipeline(
        websocket=websocket,
        session=call_session,
        session_factory=SessionFactory,
    )

    await pipeline.send_greeting(greeting_override)

    try:
        while True:
            raw_text = await websocket.receive_text()
            data = json.loads(raw_text)
            event = data.get("event")

            if event == "sandbox_text":
                text = data.get("text", "").strip()
                if text:
                    pipeline.schedule_utterance(text)

            elif event == "sandbox_audio":
                payload = data.get("payload")
                if payload:
                    chunk = base64.b64decode(payload)
                    await pipeline.handle_audio_chunk(chunk)

            elif event in ("barge_in", "sandbox_clear"):
                call_session.cancel_active_turn()
                await pipeline._clear_remote_audio_buffer()

            elif event == "stop":
                break

    except WebSocketDisconnect:
        logger.info("Sandbox WebSocket disconnected", call_id=str(call_uuid))
    except Exception as e:
        logger.error("Sandbox WebSocket exception", error=str(e))
    finally:
        await pipeline.finalize_call()


