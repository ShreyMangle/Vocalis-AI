"""
app/schemas/telephony.py — Telephony Dispatch & TwiML Schemas

Pydantic schemas for:
  - Outbound phone call dispatch
  - Telephony status and health reports
"""

import uuid

from pydantic import BaseModel, Field


class OutboundCallRequest(BaseModel):
    """Payload to trigger an automated outbound voice call."""
    to_phone: str = Field(
        ...,
        min_length=7,
        max_length=50,
        description="Recipient E.164 phone number",
        examples=["+919876543210"],
    )
    customer_name: str | None = Field(
        default=None,
        max_length=255,
        description="Optional customer display name for outbound call personalization",
    )
    appointment_id: uuid.UUID | None = Field(
        default=None,
        description="Optional appointment ID to discuss or confirm",
    )
    custom_greeting: str | None = Field(
        default=None,
        max_length=500,
        description="Optional opening phrase override for this call",
    )


class OutboundCallResponse(BaseModel):
    """Response returned upon dispatching an outbound call."""
    status: str
    call_sid: str
    to_phone: str
    from_phone: str | None
    message: str


class TelephonyStatusResponse(BaseModel):
    """Current carrier telephony configuration status."""
    provider: str
    is_configured: bool
    phone_number_configured: bool
    account_configured: bool
    vobiz_configured: bool = False
    twilio_configured: bool = False
    active_number: str | None = None

