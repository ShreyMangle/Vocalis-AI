"""
app/schemas/service.py — Business Service Schemas

Pydantic schemas for:
  - Creating, updating, and returning business services
  - Validating durations (5 to 480 minutes) and price (non-negative)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreateRequest(BaseModel):
    """Payload to create a new service offered by the business."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Display name of the service",
        examples=["General Health Consultation"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Details of what is covered in this service (used in AI agent voice prompt)",
        examples=["30-minute doctor consultation with physical exam and prescription review."],
    )
    duration_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        description="Service duration in minutes for calendar slot generation",
        examples=[30],
    )
    price: int = Field(
        default=0,
        ge=0,
        description="Price in smallest currency unit (e.g. 50000 paise = 500 INR)",
        examples=[50000],
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=10,
        description="ISO 4217 currency code",
        examples=["INR", "USD"],
    )
    category: str | None = Field(
        default=None,
        max_length=100,
        description="Optional categorization (e.g. Dental, Pediatrics)",
        examples=["General Medicine"],
    )
    is_active: bool = Field(
        default=True,
        description="Whether this service is currently available for customer booking",
    )


class ServiceUpdateRequest(BaseModel):
    """Payload to partially update an existing service."""
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    duration_minutes: int | None = Field(
        default=None,
        ge=5,
        le=480,
    )
    price: int | None = Field(
        default=None,
        ge=0,
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=10,
    )
    category: str | None = Field(
        default=None,
        max_length=100,
    )
    is_active: bool | None = None


class ServiceResponse(BaseModel):
    """Public representation of an offered service."""
    id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID
    name: str
    description: str | None
    duration_minutes: int
    price: int
    currency: str
    category: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceListResponse(BaseModel):
    """List response wrapping services."""
    items: list[ServiceResponse]
    total: int

