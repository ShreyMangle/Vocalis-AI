"""
app/schemas/tenant.py — Tenant & Team Member Schemas

These schemas define the request & response contracts for:
  - Viewing and updating the current tenant organization
  - Viewing, inviting, updating, and removing team members
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.tenant_user import UserRole


# =============================================================================
# TENANT SCHEMAS
# =============================================================================

class TenantDetailResponse(BaseModel):
    """Full tenant organization details."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantUpdateRequest(BaseModel):
    """Payload to update the tenant organization name."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Updated business/organization name",
        examples=["Sunrise Healthcare Group"],
    )


# =============================================================================
# TENANT MEMBER SCHEMAS
# =============================================================================

class TenantMemberResponse(BaseModel):
    """A member of a tenant with their user information and role."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Membership record ID")
    user_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime = Field(..., description="When the member joined")


class AddMemberRequest(BaseModel):
    """Payload to add or invite a team member to the organization."""
    email: EmailStr = Field(
        ...,
        description="Email address of the user to add",
        examples=["receptionist@sunrise.com"],
    )
    full_name: str = Field(
        default="Team Member",
        min_length=1,
        max_length=255,
        description="Full name of the user if newly created",
        examples=["Pooja Sharma"],
    )
    role: UserRole = Field(
        default=UserRole.STAFF,
        description="Role assigned to the member in this organization",
    )


class UpdateMemberRoleRequest(BaseModel):
    """Payload to update a member's role (e.g. promote STAFF to ADMIN)."""
    role: UserRole = Field(
        ...,
        description="New role to assign to the member",
    )
