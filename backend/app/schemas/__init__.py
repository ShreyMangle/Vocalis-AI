"""
app/schemas/__init__.py — Pydantic Schemas Package

CONCEPT: Schemas vs Models
===========================
Models (app/models/) = SQLAlchemy classes that map to database tables.
Schemas (app/schemas/) = Pydantic classes that define API request/response shapes.

They are SEPARATE for good reasons:
  - Models have internal fields (password_hash, is_deleted) we NEVER expose in API.
  - Schemas can have different shapes for different operations:
      UserCreateRequest (has password field)
      UserResponse (NO password, has created_at)
      UserUpdateRequest (only optional fields allowed to change)

EXAMPLE:
  User model in DB:
    { id, email, password_hash, full_name, is_verified, is_active, ... }

  UserResponse schema (what the API returns):
    { id, email, full_name, is_verified, created_at }
    ← password_hash is NEVER in the response!

PYDANTIC VALIDATION:
  class RegisterRequest(BaseModel):
      email: EmailStr    ← pydantic validates it's a real email format
      password: str = Field(min_length=8)  ← enforces minimum length
  
  Pydantic raises a 422 Unprocessable Entity if validation fails.
"""

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    TenantResponse,
    TokenPair,
    UserResponse,
)
from app.schemas.business import (
    BusinessCreateRequest,
    BusinessResponse,
    BusinessUpdateRequest,
    WorkingHoursItem,
    WorkingHoursResponse,
    WorkingHoursUpdateBatchRequest,
)
from app.schemas.tenant import (
    AddMemberRequest,
    TenantDetailResponse,
    TenantMemberResponse,
    TenantUpdateRequest,
    UpdateMemberRoleRequest,
)

__all__ = [
    # Auth
    "RegisterRequest",
    "RegisterResponse",
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "TokenPair",
    "UserResponse",
    "TenantResponse",
    "MeResponse",
    # Tenant & Members
    "TenantDetailResponse",
    "TenantUpdateRequest",
    "TenantMemberResponse",
    "AddMemberRequest",
    "UpdateMemberRoleRequest",
    # Business & Working Hours
    "BusinessCreateRequest",
    "BusinessUpdateRequest",
    "BusinessResponse",
    "WorkingHoursItem",
    "WorkingHoursUpdateBatchRequest",
    "WorkingHoursResponse",
]
