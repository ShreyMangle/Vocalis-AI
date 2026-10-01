"""
app/schemas/auth.py — Authentication Request & Response Schemas

These Pydantic models define EXACTLY what the API accepts and returns.

CONCEPT: Field Validation
==========================
Pydantic runs validation before your code runs.
If the request doesn't match the schema → 422 error automatically.

Field(min_length=8)        → password must be at least 8 chars
Field(max_length=72)       → bcrypt max is 72 chars (longer is truncated)
EmailStr                   → validates real email format: "a@b.com" not "notanemail"
Field(pattern=r"^[a-z...]")→ regex pattern validation

CONCEPT: model_config = ConfigDict(from_attributes=True)
=========================================================
This lets Pydantic create a schema from a SQLAlchemy ORM object directly.
Without it: you'd have to manually map fields.
With it:    UserResponse.model_validate(user_orm_object) just works.

Example:
    user_orm = await session.get(User, user_id)   # SQLAlchemy User object
    response = UserResponse.model_validate(user_orm)  # Pydantic conversion
    return response  # FastAPI serializes it to JSON
"""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =============================================================================
# REGISTRATION
# =============================================================================

class RegisterRequest(BaseModel):
    """
    POST /auth/register — create a new tenant + owner user.

    Registration in VoxAI creates TWO things simultaneously:
    1. A Tenant (the business organization)
    2. A User (the person registering — automatically becomes OWNER)

    This is the "happy path" for new customers.
    """

    email: EmailStr = Field(
        description="Business email address — used to log in",
        examples=["owner@sunriseclinic.com"],
    )
    password: str = Field(
        min_length=8,
        max_length=72,  # bcrypt silently truncates at 72 chars
        description="At least 8 characters",
        examples=["MyStr0ngP@ssword"],
    )
    full_name: str = Field(
        min_length=2,
        max_length=255,
        description="Your full name",
        examples=["Dr. Anita Sharma"],
    )
    business_name: str = Field(
        min_length=2,
        max_length=255,
        description="Your business/clinic/hotel name",
        examples=["Sunrise Clinic"],
    )

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Enforce basic password complexity.
        Production rule: at least 1 uppercase, 1 lowercase, 1 digit.
        """
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class RegisterResponse(BaseModel):
    """What the API returns after successful registration."""

    user: "UserResponse"
    tenant: "TenantResponse"
    tokens: "TokenPair"
    message: str = "Registration successful! Welcome to VoxAI."


# =============================================================================
# LOGIN
# =============================================================================

class LoginRequest(BaseModel):
    """POST /auth/login — authenticate and get tokens."""

    email: EmailStr
    password: str = Field(min_length=1)  # min_length=1 just to prevent empty string


class LoginResponse(BaseModel):
    """What the API returns after successful login."""

    user: "UserResponse"
    tenant: "TenantResponse"
    tokens: "TokenPair"


# =============================================================================
# TOKENS
# =============================================================================

class TokenPair(BaseModel):
    """A pair of access + refresh tokens returned after auth."""

    access_token: str = Field(description="Short-lived JWT — send with every API request")
    refresh_token: str = Field(description="Long-lived JWT — only send to /auth/refresh")
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    """POST /auth/refresh — get a new access token."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """New access token after refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


# =============================================================================
# USER RESPONSE
# =============================================================================

class UserResponse(BaseModel):
    """
    Safe user representation for API responses.

    NOTICE: password_hash is NOT here.
    We never send password data in responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_verified: bool
    is_active: bool
    created_at: datetime


# =============================================================================
# TENANT RESPONSE
# =============================================================================

class TenantResponse(BaseModel):
    """Safe tenant representation for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime


# =============================================================================
# ME ENDPOINT
# =============================================================================

class MeResponse(BaseModel):
    """
    GET /auth/me — returns the currently authenticated user's profile.
    Also includes their memberships (which tenants they belong to).
    """

    user: UserResponse
    tenant: TenantResponse
    role: str  # OWNER / ADMIN / STAFF in the current tenant
