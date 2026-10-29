"""
app/api/v1/telephony.py — Carrier Telephony Webhooks & Outbound Dispatch

Routes:
  GET|POST /api/v1/telephony/voice         → Twilio/VoBiz incoming call webhook (returns TwiML)
  POST     /api/v1/telephony/outbound-call → Dispatch automated outbound customer call
  GET      /api/v1/telephony/status        → Check telephony carrier readiness
"""

import uuid
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.core.config import settings
from app.core.dependencies import (
    CurrentUser,
    require_authenticated,
    require_role,
)
from app.models.tenant_user import UserRole
from app.schemas.telephony import (
    OutboundCallRequest,
    OutboundCallResponse,
    TelephonyStatusResponse,
)

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
    """Returns whether Twilio / VoBiz credentials and numbers are configured."""
    has_account = bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)
    has_phone = bool(settings.TWILIO_PHONE_NUMBER)

    return TelephonyStatusResponse(
        provider=settings.DEFAULT_TELEPHONY_PROVIDER,
        is_configured=has_account and has_phone,
        phone_number_configured=has_phone,
        account_configured=has_account,
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
    Initiates an outbound phone call to a customer using Twilio REST API.
    If credentials are not yet set in environment, runs in safe simulation mode.
    """
    has_twilio = bool(
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_PHONE_NUMBER
    )

    if not has_twilio:
        # Development / Simulation mode
        simulated_sid = f"SIM_{uuid.uuid4().hex[:16]}"
        logger.info(
            "Outbound call simulated (no Twilio credentials configured)",
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

    # Real Twilio API Call
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

