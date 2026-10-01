"""
app/core/dependencies.py — FastAPI Dependency Functions

CONCEPT: What is a Dependency?
================================
A "dependency" in FastAPI is a function that runs BEFORE your route handler.
It can:
  1. Extract data from the request (e.g., parse the Authorization header).
  2. Validate it (e.g., verify JWT signature).
  3. Inject context into the route (e.g., the current user).
  4. Raise an error if invalid (e.g., 401 Unauthorized).

Think of it as a security guard at a building's entrance:
  - Every visitor (request) goes through the guard (dependency).
  - Guard checks their pass (JWT token).
  - If valid, allows entry with their identity card (CurrentUser).
  - If invalid, blocks entry (raises 401).

USAGE IN ROUTES:
    @router.get("/something")
    async def protected_route(
        current_user: CurrentUser = Depends(require_authenticated),
    ):
        # current_user.user_id, current_user.tenant_id, current_user.role
        # are all available here — no need to parse the token yourself

CONCEPT: CurrentUser Dataclass
================================
We define a simple dataclass that carries the authenticated user's context.
This is what gets injected into every protected route.

We don't inject the full User ORM object because:
  1. It would require a DB query on every request (expensive).
  2. The JWT already contains all the info we need for authorization.
  3. If we need the full User record, we can query inside the route.
"""

import uuid
from dataclasses import dataclass

import structlog
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.models.tenant_user import UserRole

logger = structlog.get_logger(__name__)

# HTTPBearer extracts the Bearer token from the Authorization header.
# auto_error=False means: if the header is missing, return None instead of
# raising a generic 403. We raise our own 401 with a better message.
_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """
    The authenticated user's context — injected into protected routes.

    frozen=True means this object is immutable after creation (safer).

    Fields:
        user_id:   The authenticated user's UUID
        tenant_id: The tenant they're acting as (for DB isolation)
        role:      Their role in this tenant (for RBAC)
        jti:       JWT token ID (for potential revocation checks)
    """

    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: UserRole
    jti: str


async def require_authenticated(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """
    Dependency: Ensures the request has a valid JWT access token.

    Extracts the Bearer token → verifies signature → decodes payload → returns CurrentUser.

    Usage:
        @router.get("/protected")
        async def my_route(user: CurrentUser = Depends(require_authenticated)):
            print(user.tenant_id)  # available!

    Raises:
        AuthenticationError (401): if token is missing, expired, or invalid
    """
    if credentials is None:
        raise AuthenticationError(
            "Authentication required. Include 'Authorization: Bearer <token>' header.",
            code="MISSING_TOKEN",
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as e:
        logger.warning("JWT validation failed", error=str(e))
        raise AuthenticationError(
            "Invalid or expired token. Please log in again.",
            code="INVALID_TOKEN",
        )

    # Extract claims from payload
    user_id_str = payload.get("sub")
    tenant_id_str = payload.get("tenant_id")
    role_str = payload.get("role")
    jti = payload.get("jti", "")

    if not all([user_id_str, tenant_id_str, role_str]):
        raise AuthenticationError(
            "Malformed token payload.",
            code="MALFORMED_TOKEN",
        )

    try:
        return CurrentUser(
            user_id=uuid.UUID(user_id_str),
            tenant_id=uuid.UUID(tenant_id_str),
            role=UserRole(role_str),
            jti=jti,
        )
    except (ValueError, KeyError):
        raise AuthenticationError("Malformed token payload.", code="MALFORMED_TOKEN")


def require_role(*allowed_roles: UserRole):
    """
    Dependency FACTORY: Creates a dependency that enforces a minimum role.

    This is a "factory" — it returns a dependency, not a value.

    Usage:
        # Only OWNER or ADMIN can access this route
        @router.delete("/agents/{id}")
        async def delete_agent(
            user: CurrentUser = Depends(require_role(UserRole.OWNER, UserRole.ADMIN)),
        ):
            ...

        # Only OWNER can access billing
        @router.post("/billing/upgrade")
        async def upgrade_plan(
            user: CurrentUser = Depends(require_role(UserRole.OWNER)),
        ):
            ...
    """

    async def _check_role(
        current_user: CurrentUser = Depends(require_authenticated),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise AuthorizationError(
                f"This action requires one of: {[r.value for r in allowed_roles]}. "
                f"Your role is: {current_user.role.value}",
                code="INSUFFICIENT_ROLE",
            )
        return current_user

    return _check_role
