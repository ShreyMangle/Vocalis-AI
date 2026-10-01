"""
app/core/security.py — Password Hashing & JWT Token Management

CONCEPT: How Authentication Works in Our System
================================================
The authentication flow has two parts:

PART 1 — LOGIN (happens once):
  User sends email + password
  → We verify password against stored bcrypt hash
  → We create TWO tokens:
      Access Token  (short-lived: 15 minutes)
      Refresh Token (long-lived: 7 days)
  → Return both to the client (browser/app)

PART 2 — EVERY API REQUEST (happens on every call):
  Client sends access token in the Authorization header:
      Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  → Our middleware extracts and verifies the token
  → If valid, the request is processed with the user's identity
  → If expired, client uses refresh token to get a new access token

CONCEPT: JWT (JSON Web Token)
==============================
A JWT is a string with three base64-encoded parts separated by dots:
  HEADER.PAYLOAD.SIGNATURE

Example:
  eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyXzEiLCJleHAiOjE2...signature...

  HEADER:    {"alg": "HS256", "typ": "JWT"}  ← algorithm used
  PAYLOAD:   {"sub": "user_id", "role": "OWNER", "exp": 1234567890}
  SIGNATURE: HMAC_SHA256(header + "." + payload, SECRET_KEY)

The SIGNATURE is the key part:
  - Only our server knows the SECRET_KEY
  - Anyone can READ the payload (it's just base64, not encrypted)
  - Nobody can FORGE a valid signature without the secret
  - We verify: "did OUR server sign this?" → YES → trust the payload

IMPORTANT: JWTs are NOT encrypted — don't put sensitive data in them.
The payload is readable by anyone. Only the signature is secret.

CONCEPT: Access Token vs Refresh Token
========================================
Access Token:
  - Short expiry (15 min) — minimizes damage if stolen
  - Client sends with EVERY API request
  - If stolen, attacker has access for max 15 minutes

Refresh Token:
  - Long expiry (7 days) — so users don't re-login daily
  - Client stores safely (httpOnly cookie in browser)
  - ONLY sent to the /auth/refresh endpoint
  - We store its ID in Redis — can be revoked immediately

WHY TWO TOKENS?
  If access token is 7 days long and stolen → attacker has 7 days.
  If access token is 15 min → attacker has 15 minutes.
  Refresh token is ONLY sent to one endpoint → smaller attack surface.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = structlog.get_logger(__name__)

# =============================================================================
# PASSWORD HASHING
# =============================================================================
# CryptContext manages multiple hashing schemes.
# schemes=["bcrypt"] → use bcrypt algorithm
# deprecated="auto" → if we add a new scheme later, old hashes are auto-detected
#
# HOW BCRYPT WORKS:
# 1. Generates a random 22-char salt (different every time)
# 2. Combines salt + password
# 3. Runs the expensive Blowfish cipher 2^12 = 4096 times (slow by design)
# 4. Returns: "$2b$12$" + salt + hash
#
# The "12" is the "work factor" — higher = slower = harder to brute force.
# On modern hardware, factor=12 takes ~100ms → 10 guesses/second (not 1 billion).

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Call this on registration before storing in DB.
    Never store the plain password.

    Example:
        hashed = hash_password("mySecretPassword123")
        # → "$2b$12$LQv3c1yqBWVHxkd..."
        user.password_hash = hashed
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Call this on login:
        if not verify_password(request.password, user.password_hash):
            raise AuthenticationError("Invalid credentials")

    Returns True if password matches, False otherwise.
    NEVER raise an exception that reveals whether the email or password was wrong.
    Always say "Invalid credentials" (not "Wrong password" or "Email not found").
    WHY? Revealing which part is wrong helps attackers.
    """
    return _pwd_context.verify(plain_password, hashed_password)


# =============================================================================
# JWT TOKEN MANAGEMENT
# =============================================================================

def _create_token(
    payload: dict,
    expire_delta: timedelta,
    token_type: str,
) -> str:
    """
    Internal helper — creates a signed JWT token.

    payload: dict of claims to include (sub, tenant_id, role, etc.)
    expire_delta: how long until the token expires
    token_type: "access" or "refresh" (stored in payload for validation)
    """
    now = datetime.now(UTC)
    expire = now + expire_delta

    # Build the full payload (claims)
    # "sub" (subject) is the JWT standard claim for the principal identity
    # "exp" (expiry) is checked automatically by python-jose on decode
    # "jti" (JWT ID) is a unique ID for this token — allows revocation
    claims = {
        **payload,
        "type": token_type,
        "iat": now,        # issued at
        "exp": expire,     # expires at
        "jti": str(uuid.uuid4()),  # unique token ID
    }

    return jwt.encode(
        claims,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
) -> str:
    """
    Create a short-lived JWT access token.

    This token is sent with every API request in the Authorization header.
    It contains all the info needed to identify and authorize the user
    WITHOUT querying the database on every request.

    Args:
        user_id: The user's UUID (stored as "sub")
        tenant_id: Which tenant they're accessing (for isolation)
        role: Their role in this tenant (OWNER/ADMIN/STAFF)
    """
    return _create_token(
        payload={
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role,
        },
        expire_delta=timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        ),
        token_type="access",
    )


def create_refresh_token(user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """
    Create a long-lived JWT refresh token.

    This token is ONLY used to get new access tokens.
    It should be stored in an httpOnly cookie (browser can't read it via JS).
    We store its `jti` in Redis so we can revoke it.
    """
    return _create_token(
        payload={
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
        },
        expire_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def decode_access_token(token: str) -> dict:
    """
    Verify and decode an access token.

    Raises:
        JWTError: if token is invalid, expired, or tampered with

    Returns:
        dict with keys: sub, tenant_id, role, type, iat, exp, jti
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        # Extra safety: ensure this is actually an access token
        # (not a refresh token being used as access)
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")
        return payload
    except JWTError:
        raise  # Re-raise — caller decides how to handle


def decode_refresh_token(token: str) -> dict:
    """
    Verify and decode a refresh token.

    Raises:
        JWTError: if token is invalid, expired, or tampered with
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            raise JWTError("Invalid token type")
        return payload
    except JWTError:
        raise
