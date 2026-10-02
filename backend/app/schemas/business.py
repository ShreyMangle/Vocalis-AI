"""
app/schemas/business.py — Business Profile & Working Hours Schemas

Pydantic schemas for:
  - Business profile creation, updating, and responses
  - Weekly operating hours schedule item and batch update payloads
  - Strict validation of timezones (IANA zoneinfo) and time ranges (open_time < close_time)
"""

import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo, available_timezones

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.business import DayOfWeek

# Cache valid timezone names for fast validation
_VALID_TIMEZONES = set(available_timezones())


# =============================================================================
# BUSINESS PROFILE SCHEMAS
# =============================================================================

class BusinessCreateRequest(BaseModel):
    """Payload to create or initialize a business profile."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Public display name of the business",
        examples=["Sunrise Multi-Specialty Clinic"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Detailed description of services offered (injected into AI prompt)",
        examples=["Full service medical clinic offering general practice and pediatric care."],
    )
    industry: str = Field(
        default="healthcare",
        max_length=100,
        description="Business industry vertical",
        examples=["healthcare"],
    )
    timezone: str = Field(
        default="Asia/Kolkata",
        description="IANA standard timezone name",
        examples=["Asia/Kolkata", "America/New_York"],
    )
    phone_number: str | None = Field(
        default=None,
        max_length=30,
        description="Contact phone number",
        examples=["+919876543210"],
    )
    email: EmailStr | None = Field(
        default=None,
        description="Public contact email",
        examples=["contact@sunriseclinic.com"],
    )
    website: str | None = Field(
        default=None,
        max_length=255,
        description="Official website URL",
        examples=["https://sunriseclinic.com"],
    )
    address: str | None = Field(
        default=None,
        max_length=500,
        description="Physical office / clinic address",
        examples=["101 MG Road, Bangalore, India"],
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        if v not in _VALID_TIMEZONES:
            raise ValueError(
                f"Invalid IANA timezone '{v}'. Must be a valid timezone like 'Asia/Kolkata' or 'America/New_York'."
            )
        return v


class BusinessUpdateRequest(BaseModel):
    """Payload to update fields of an existing business profile."""
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    industry: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None)
    phone_number: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = Field(default=None)
    website: str | None = Field(default=None, max_length=255)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_TIMEZONES:
            raise ValueError(
                f"Invalid IANA timezone '{v}'. Must be a valid timezone like 'Asia/Kolkata' or 'America/New_York'."
            )
        return v


class BusinessResponse(BaseModel):
    """Complete business profile response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    industry: str
    timezone: str
    phone_number: str | None
    email: str | None
    website: str | None
    address: str | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# WORKING HOURS SCHEMAS
# =============================================================================

class WorkingHoursItem(BaseModel):
    """Operating hours specification for a single day of the week."""
    day_of_week: DayOfWeek = Field(
        ...,
        description="Day of the week",
        examples=[DayOfWeek.MONDAY],
    )
    open_time: time | None = Field(
        default=None,
        description="Opening time in HH:MM:SS format",
        examples=["09:00:00"],
    )
    close_time: time | None = Field(
        default=None,
        description="Closing time in HH:MM:SS format",
        examples=["18:00:00"],
    )
    is_closed: bool = Field(
        default=False,
        description="Set to true if business is closed on this day",
    )

    @model_validator(mode="after")
    def validate_times(self) -> "WorkingHoursItem":
        if self.is_closed:
            # When closed, open_time and close_time can be None
            return self

        if self.open_time is None or self.close_time is None:
            raise ValueError("open_time and close_time must be provided when is_closed is False.")

        if self.open_time >= self.close_time:
            raise ValueError(
                f"open_time ({self.open_time}) must be earlier than close_time ({self.close_time})."
            )

        return self


class WorkingHoursUpdateBatchRequest(BaseModel):
    """Batch schedule update containing 1 to 7 daily schedules."""
    schedule: list[WorkingHoursItem] = Field(
        ...,
        min_length=1,
        max_length=7,
        description="List of daily working hour items",
    )

    @field_validator("schedule")
    @classmethod
    def validate_unique_days(cls, v: list[WorkingHoursItem]) -> list[WorkingHoursItem]:
        days = [item.day_of_week for item in v]
        if len(days) != len(set(days)):
            raise ValueError("Each day_of_week can only appear once in a schedule batch.")
        return v


class WorkingHoursResponse(BaseModel):
    """Single working hours record response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    business_id: uuid.UUID
    day_of_week: DayOfWeek
    open_time: time | None
    close_time: time | None
    is_closed: bool
    created_at: datetime
    updated_at: datetime
