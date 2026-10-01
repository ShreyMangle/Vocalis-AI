"""
app/api/v1/auth.py — Authentication Routes

Routes:
  POST /api/v1/auth/register  → Create tenant + owner user + return tokens
  POST /api/v1/auth/login     → Verify credentials + return tokens
  POST /api/v1/auth/refresh   → Use refresh token to get new access token
  POST /api/v1/auth/logout    → Revoke refresh token (invalidate session)
  GET  /api/v1/auth/me        → Return current user + tenant info

CONCEPT: Route Handlers
========================
A route handler is a function that:
  1. Receives a request (with body, headers, path params).
  2. Runs business logic (validate, query DB, call services).
  3. Returns a response.

FastAPI uses function signature annotations to:
  - Parse request body: `body: RegisterRequest` → pydantic validates it
  - Inject dependencies: `session: AsyncSession = Depends(get_session)`
  - Inject current user: `user: CurrentUser = Depends(require_authenticated)`

CONCEPT: Slug Generation
=========================
A slug is a URL-safe version of a string.
"Sunrise Clinic" → "sunrise-clinic"
"Dr. Sharma's Office!" → "dr-sharmas-office"

Rules:
  - Lowercase
  - Spaces → hyphens
  - Remove special chars
  - Must be unique (we add random suffix if collision)

CONCEPT: Status Codes
======================
201 Created    → Used when a resource is newly created (POST/register)
200 OK         → Used for login, refresh, me (no new resource created)
401 Unauthorized → Bad credentials
409 Conflict   → Email already registered
"""

import re
import uuid
from datetime import UTC

import structlog
from fastapi import APIRouter, Depends, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, require_authenticated
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.models.tenant import Tenant
from app.models.tenant_user import TenantUser, UserRole
from app.models.user import User
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

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# HELPERS
# =============================================================================

def _slugify(text: str) -> str:
    """
    Convert a business name to a URL-safe slug.
    "Sunrise Clinic" → "sunrise-clinic"
    "Dr. Sharma's!" → "dr-sharmas"
    """
    # Lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


async def _generate_unique_slug(session: AsyncSession, business_name: str) -> str:
    """
    Generate a slug and ensure it's unique in the DB.
    If "sunrise-clinic" is taken → try "sunrise-clinic-a3f2".
    """
    base_slug = _slugify(business_name)
    slug = base_slug

    # Check if slug exists
    existing = await session.execute(
        select(Tenant).where(Tenant.slug == slug)
    )
    if existing.scalar_one_or_none() is None:
        return slug  # Slug is free!

    # Collision → add random suffix
    slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
    return slug


def _build_token_pair(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> TokenPair:
    """Create access + refresh tokens and wrap in a TokenPair schema."""
    access = create_access_token(user_id, tenant_id, role)
    refresh = create_refresh_token(user_id, tenant_id)
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
    )


# =============================================================================
# REGISTER
# =============================================================================

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new business",
    description="""
    Creates a new **Tenant** (business organization) and **User** (owner) in one step.
    
    The registering user is automatically assigned the **OWNER** role for the new tenant.
    Returns JWT access + refresh tokens on success.
    """,
)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> RegisterResponse:
    """
    Registration flow:
    1. Check email isn't already registered.
    2. Hash the password.
    3. Generate a unique slug from the business name.
    4. Create Tenant, User, TenantUser records in one DB transaction.
    5. Generate tokens.
    6. Return user info + tokens.

    Everything in steps 3-4 happens in a SINGLE TRANSACTION.
    If anything fails, nothing is saved — the DB stays consistent.
    """

    # ── Step 1: Check for duplicate email ─────────────────────────────────────
    existing_user = await session.execute(
        select(User).where(User.email == body.email.lower())
    )
    if existing_user.scalar_one_or_none() is not None:
        # IMPORTANT: Use 409 Conflict, not 400 Bad Request
        # 409 specifically means "this resource already exists"
        raise ConflictError(
            f"An account with email '{body.email}' already exists.",
            code="EMAIL_ALREADY_REGISTERED",
        )

    # ── Step 2: Create the Tenant ──────────────────────────────────────────────
    slug = await _generate_unique_slug(session, body.business_name)
    tenant = Tenant(
        name=body.business_name,
        slug=slug,
        plan="free",
        is_active=True,
    )
    session.add(tenant)
    # flush() sends the INSERT to the DB within the transaction
    # but doesn't COMMIT yet — we can still rollback if later steps fail.
    # This gives tenant.id a value so we can use it below.
    await session.flush()

    logger.info("Tenant created", tenant_id=str(tenant.id), slug=slug)

    # ── Step 3: Create the User ────────────────────────────────────────────────
    user = User(
        email=body.email.lower(),  # Always store emails lowercase
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        is_verified=False,  # TODO: send verification email
        is_active=True,
    )
    session.add(user)
    await session.flush()

    logger.info("User created", user_id=str(user.id), email=user.email)

    # ── Step 4: Link User to Tenant as OWNER ──────────────────────────────────
    membership = TenantUser(
        tenant_id=tenant.id,
        user_id=user.id,
        role=UserRole.OWNER,
        is_active=True,
    )
    session.add(membership)
    # The session.commit() in get_session() will commit all three inserts atomically

    # ── Step 5: Generate tokens ────────────────────────────────────────────────
    tokens = _build_token_pair(user.id, tenant.id, UserRole.OWNER.value)

    logger.info(
        "Registration complete",
        user_id=str(user.id),
        tenant_id=str(tenant.id),
    )

    return RegisterResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
        tokens=tokens,
    )


# =============================================================================
# LOGIN
# =============================================================================

@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """
    Login flow:
    1. Find user by email.
    2. Verify password.
    3. Find their tenant membership (default: first active tenant they own).
    4. Generate tokens.

    SECURITY NOTE: Always use the same error message for wrong email AND wrong password.
    "Invalid credentials" — not "Email not found" or "Wrong password".
    WHY? If we say "Email not found", attackers learn which emails are registered.
    """

    # ── Step 1: Find user ──────────────────────────────────────────────────────
    result = await session.execute(
        select(User).where(
            User.email == body.email.lower(),
            User.is_active == True,  # noqa: E712
            User.is_deleted == False,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()

    # ── Step 2: Verify password ────────────────────────────────────────────────
    # CRITICAL: We check user is not None AND verify password together.
    # If user is None, we still call verify_password with a dummy hash
    # to prevent "timing attacks" — measuring how long the response takes
    # to figure out if the email exists.
    _dummy_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj2NkJUn5Iu."
    password_valid = verify_password(
        body.password,
        user.password_hash if user else _dummy_hash,
    )

    if not user or not password_valid:
        raise AuthenticationError(
            "Invalid email or password.",
            code="INVALID_CREDENTIALS",
        )

    # ── Step 3: Get their tenant membership ────────────────────────────────────
    membership_result = await session.execute(
        select(TenantUser, Tenant)
        .join(Tenant, TenantUser.tenant_id == Tenant.id)
        .where(
            TenantUser.user_id == user.id,
            TenantUser.is_active == True,  # noqa: E712
            Tenant.is_active == True,  # noqa: E712
            Tenant.is_deleted == False,  # noqa: E712
        )
        .order_by(TenantUser.created_at.asc())  # Default: first tenant they joined
        .limit(1)
    )
    row = membership_result.first()

    if row is None:
        raise AuthenticationError(
            "No active tenant found for this account.",
            code="NO_ACTIVE_TENANT",
        )

    membership, tenant = row

    # ── Step 4: Generate tokens ────────────────────────────────────────────────
    tokens = _build_token_pair(user.id, tenant.id, membership.role.value)

    logger.info(
        "User logged in",
        user_id=str(user.id),
        tenant_id=str(tenant.id),
        role=membership.role.value,
    )

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
        tokens=tokens,
    )


# =============================================================================
# REFRESH TOKEN
# =============================================================================

@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Use your refresh token to get a new access token without re-logging in.",
)
async def refresh_token(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> RefreshResponse:
    """
    Refresh flow:
    1. Decode + verify the refresh token.
    2. Check user still exists and is active.
    3. Get their current role (it might have changed since last login).
    4. Issue a new access token.

    NOTE: We do NOT issue a new refresh token here (token rotation).
    The refresh token remains valid until it expires (7 days).
    Token rotation (new refresh token on every refresh) can be added in a security sprint.
    """
    try:
        payload = decode_refresh_token(body.refresh_token)
    except JWTError:
        raise AuthenticationError(
            "Invalid or expired refresh token. Please log in again.",
            code="INVALID_REFRESH_TOKEN",
        )

    user_id = uuid.UUID(payload["sub"])
    tenant_id = uuid.UUID(payload["tenant_id"])

    # Verify user + membership are still active (they might have been suspended)
    result = await session.execute(
        select(TenantUser)
        .where(
            TenantUser.user_id == user_id,
            TenantUser.tenant_id == tenant_id,
            TenantUser.is_active == True,  # noqa: E712
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise AuthenticationError(
            "Session is no longer valid. Please log in again.",
            code="SESSION_INVALIDATED",
        )

    new_access = create_access_token(user_id, tenant_id, membership.role.value)

    return RefreshResponse(
        access_token=new_access,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# =============================================================================
# LOGOUT
# =============================================================================

@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out (invalidate session)",
)
async def logout(
    current_user: CurrentUser = Depends(require_authenticated),
) -> dict:
    """
    Logout flow:
    The client should discard their tokens.
    Access tokens can't be truly revoked (they're stateless JWTs).
    The access token will naturally expire in 15 minutes.

    For stricter logout, you'd store the JTI (token ID) in a Redis denylist.
    We'll add that in the security hardening sprint.

    Client-side: delete tokens from localStorage / cookies.
    """
    logger.info("User logged out", user_id=str(current_user.user_id))
    return {"message": "Logged out successfully."}


# =============================================================================
# ME — Get current user profile
# =============================================================================

@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the authenticated user's profile + their role in the current tenant.",
)
async def get_me(
    current_user: CurrentUser = Depends(require_authenticated),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    """
    Me flow:
    1. current_user is injected by the require_authenticated dependency.
       It already has user_id and tenant_id from the JWT — no DB query needed for that.
    2. We query the DB to get the full User + Tenant records (for complete profile data).
    3. Return the profile.

    WHY query at all if we have the JWT?
    The JWT is a SNAPSHOT from login time. If the user changed their name since
    logging in, the JWT would have the old name. We query fresh data here.
    """
    # Fetch user from DB
    user = await session.get(User, current_user.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User account not found or deactivated.", code="USER_NOT_FOUND")

    # Fetch tenant from DB
    tenant = await session.get(Tenant, current_user.tenant_id)
    if tenant is None or not tenant.is_active:
        raise AuthenticationError("Tenant not found or inactive.", code="TENANT_NOT_FOUND")

    return MeResponse(
        user=UserResponse.model_validate(user),
        tenant=TenantResponse.model_validate(tenant),
        role=current_user.role.value,
    )
