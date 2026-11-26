"""
tests/test_auth.py — Day 3 Authentication Tests

These are UNIT tests — everything is mocked. No real DB or Redis needed.

Testing strategy:
  - Security functions (hash_password, verify_password, create_token, decode_token)
    → Pure functions, no mocking needed
  - Route logic → Mock the DB session
  - Schema validation → Pure Pydantic, no mocking needed
  - Dependencies → Mock token contents

CONCEPT: Mocking DB in Tests
==============================
Our routes use `session: AsyncSession = Depends(get_session)`.
In tests, we override this with a mock using:
    app.dependency_overrides[get_session] = lambda: mock_session

Now when the route calls `session.execute(...)`, it gets our mock.
We control what the mock returns → tests are fast and predictable.

CONCEPT: AsyncMock
===================
`AsyncMock` is like `MagicMock` but for async functions.
When you `await async_mock()`, it returns `async_mock.return_value`.

Example:
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=lambda: None  # Simulate "no user found"
    )
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings


# =============================================================================
# Tests: Password Hashing
# =============================================================================

class TestPasswordHashing:
    """Tests for bcrypt hash/verify functions."""

    def test_hash_is_not_plain_text(self):
        """
        GIVEN: A plain password
        WHEN:  hash_password() is called
        THEN:  The result should NOT equal the plain password
        """
        from app.core.security import hash_password
        hashed = hash_password("MyPassword123")
        assert hashed != "MyPassword123"

    def test_hash_starts_with_bcrypt_prefix(self):
        """
        GIVEN: A plain password
        WHEN:  hash_password() is called
        THEN:  Result starts with "$2b$" — the bcrypt identifier
        """
        from app.core.security import hash_password
        hashed = hash_password("MyPassword123")
        assert hashed.startswith("$2b$")

    def test_same_password_produces_different_hashes(self):
        """
        GIVEN: The same password hashed twice
        WHEN:  Results are compared
        THEN:  They should be DIFFERENT (bcrypt uses random salts)
        """
        from app.core.security import hash_password
        hash1 = hash_password("MyPassword123")
        hash2 = hash_password("MyPassword123")
        assert hash1 != hash2  # Different salts → different hashes

    def test_verify_correct_password_returns_true(self):
        """
        GIVEN: A hashed password
        WHEN:  verify_password() is called with the original plain text
        THEN:  Returns True
        """
        from app.core.security import hash_password, verify_password
        hashed = hash_password("MyPassword123")
        assert verify_password("MyPassword123", hashed) is True

    def test_verify_wrong_password_returns_false(self):
        """
        GIVEN: A hashed password
        WHEN:  verify_password() is called with the WRONG password
        THEN:  Returns False (not raises, not crashes)
        """
        from app.core.security import hash_password, verify_password
        hashed = hash_password("MyPassword123")
        assert verify_password("WrongPassword999", hashed) is False

    def test_verify_empty_string_returns_false(self):
        """Empty string should not match any real password."""
        from app.core.security import hash_password, verify_password
        hashed = hash_password("MyPassword123")
        assert verify_password("", hashed) is False


# =============================================================================
# Tests: JWT Tokens
# =============================================================================

class TestJWTTokens:
    """Tests for JWT creation and decoding."""

    def _sample_ids(self):
        return uuid.uuid4(), uuid.uuid4()

    def test_create_access_token_returns_string(self):
        """
        GIVEN: User ID, tenant ID, role
        WHEN:  create_access_token() is called
        THEN:  Returns a non-empty string (the JWT)
        """
        from app.core.security import create_access_token
        user_id, tenant_id = self._sample_ids()
        token = create_access_token(user_id, tenant_id, "OWNER")
        assert isinstance(token, str)
        assert len(token) > 50  # JWTs are always > 50 chars

    def test_access_token_has_three_parts(self):
        """JWT format is header.payload.signature (3 parts separated by dots)."""
        from app.core.security import create_access_token
        user_id, tenant_id = self._sample_ids()
        token = create_access_token(user_id, tenant_id, "OWNER")
        parts = token.split(".")
        assert len(parts) == 3

    def test_decode_access_token_returns_correct_claims(self):
        """
        GIVEN: A created access token
        WHEN:  decode_access_token() is called
        THEN:  Returns correct user_id, tenant_id, role, type
        """
        from app.core.security import create_access_token, decode_access_token
        user_id, tenant_id = self._sample_ids()
        token = create_access_token(user_id, tenant_id, "ADMIN")
        payload = decode_access_token(token)

        assert payload["sub"] == str(user_id)
        assert payload["tenant_id"] == str(tenant_id)
        assert payload["role"] == "ADMIN"
        assert payload["type"] == "access"

    def test_decode_access_token_fails_with_wrong_secret(self):
        """
        GIVEN: A token signed with a different secret
        WHEN:  decode_access_token() is called
        THEN:  Raises JWTError (token is tampered/forged)
        """
        from jose import JWTError, jwt
        from app.core.security import decode_access_token
        user_id, tenant_id = self._sample_ids()

        # Create token with WRONG secret
        forged_token = jwt.encode(
            {"sub": str(user_id), "tenant_id": str(tenant_id), "role": "OWNER", "type": "access"},
            "WRONG_SECRET_KEY_12345678901234567890",
            algorithm="HS256",
        )

        with pytest.raises(JWTError):
            decode_access_token(forged_token)

    def test_decode_access_token_fails_when_expired(self):
        """
        GIVEN: An already-expired access token
        WHEN:  decode_access_token() is called
        THEN:  Raises JWTError
        """
        from jose import JWTError, jwt
        from app.core.security import decode_access_token

        user_id, tenant_id = self._sample_ids()
        expired_token = jwt.encode(
            {
                "sub": str(user_id),
                "tenant_id": str(tenant_id),
                "role": "OWNER",
                "type": "access",
                "exp": datetime.now(UTC) - timedelta(minutes=1),  # Already expired!
                "jti": str(uuid.uuid4()),
            },
            settings.JWT_SECRET,
            algorithm="HS256",
        )

        with pytest.raises(JWTError):
            decode_access_token(expired_token)

    def test_refresh_token_type_is_refresh(self):
        """
        GIVEN: A created refresh token
        WHEN:  Decoded manually
        THEN:  Token type must be "refresh", not "access"
        """
        from jose import jwt
        from app.core.security import create_refresh_token
        user_id, tenant_id = self._sample_ids()
        token = create_refresh_token(user_id, tenant_id)
        # Decode without verification (just to inspect payload)
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        assert payload["type"] == "refresh"

    def test_cannot_use_refresh_token_as_access_token(self):
        """
        GIVEN: A refresh token
        WHEN:  decode_access_token() is called with it
        THEN:  Raises JWTError (wrong type)

        This prevents token confusion attacks.
        """
        from jose import JWTError
        from app.core.security import create_refresh_token, decode_access_token
        user_id, tenant_id = self._sample_ids()
        refresh = create_refresh_token(user_id, tenant_id)
        with pytest.raises(JWTError):
            decode_access_token(refresh)

    def test_access_token_has_unique_jti(self):
        """
        GIVEN: Two access tokens for the same user
        WHEN:  Both are decoded
        THEN:  Their JTIs (JWT IDs) are different (unique per token)
        """
        from app.core.security import create_access_token, decode_access_token
        user_id, tenant_id = self._sample_ids()
        token1 = create_access_token(user_id, tenant_id, "OWNER")
        token2 = create_access_token(user_id, tenant_id, "OWNER")
        payload1 = decode_access_token(token1)
        payload2 = decode_access_token(token2)
        assert payload1["jti"] != payload2["jti"]


# =============================================================================
# Tests: Schema Validation
# =============================================================================

class TestRegisterSchema:
    """Tests for RegisterRequest Pydantic schema validation."""

    def test_valid_registration_passes(self):
        """GIVEN valid data WHEN parsed THEN no error."""
        from app.schemas.auth import RegisterRequest
        req = RegisterRequest(
            email="owner@sunrise.com",
            password="MyStr0ngPass",
            full_name="Dr. Anita",
            business_name="Sunrise Clinic",
        )
        assert req.email == "owner@sunrise.com"

    def test_invalid_email_fails(self):
        """GIVEN invalid email WHEN parsed THEN ValidationError."""
        from pydantic import ValidationError
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="not-an-email",
                password="MyStr0ngPass",
                full_name="Test User",
                business_name="Test Co",
            )

    def test_short_password_fails(self):
        """GIVEN 7-char password WHEN parsed THEN ValidationError."""
        from pydantic import ValidationError
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="a@b.com",
                password="Ab1xxxx",  # 7 chars — min is 8
                full_name="Test",
                business_name="Test Co",
            )

    def test_password_without_uppercase_fails(self):
        """GIVEN password without uppercase WHEN parsed THEN ValidationError."""
        from pydantic import ValidationError
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="a@b.com",
                password="nouppercase1",  # No uppercase
                full_name="Test",
                business_name="Test Co",
            )

    def test_password_without_digit_fails(self):
        """GIVEN password without digit WHEN parsed THEN ValidationError."""
        from pydantic import ValidationError
        from app.schemas.auth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="a@b.com",
                password="NoDigitPassword",  # No digit
                full_name="Test",
                business_name="Test Co",
            )

    def test_tenant_name_alias_supported(self):
        """GIVEN tenant_name instead of business_name WHEN parsed THEN both populated."""
        from app.schemas.auth import RegisterRequest
        req = RegisterRequest(
            email="owner@sunrise.com",
            password="MyStr0ngPass1",
            full_name="Dr. Anita",
            tenant_name="Sunrise Clinic",
        )
        assert req.business_name == "Sunrise Clinic"
        assert req.tenant_name == "Sunrise Clinic"


# =============================================================================
# Tests: Slugify Helper
# =============================================================================

class TestSlugify:
    """Tests for the slug generation helper in auth routes."""

    def test_basic_slug(self):
        from app.api.v1.auth import _slugify
        assert _slugify("Sunrise Clinic") == "sunrise-clinic"

    def test_removes_special_chars(self):
        from app.api.v1.auth import _slugify
        assert _slugify("Dr. Sharma's Office!") == "dr-sharma-s-office"

    def test_handles_multiple_spaces(self):
        from app.api.v1.auth import _slugify
        result = _slugify("  City   Hospital  ")
        assert result == "city-hospital"

    def test_all_lowercase(self):
        from app.api.v1.auth import _slugify
        assert _slugify("UPPERCASE COMPANY") == "uppercase-company"


# =============================================================================
# Tests: CurrentUser Dependency
# =============================================================================

class TestCurrentUserDependency:
    """Tests for the require_authenticated dependency."""

    def test_missing_token_raises_auth_error(self, client):
        """
        GIVEN: No Authorization header
        WHEN:  GET /api/v1/auth/me is called
        THEN:  Returns 401
        """
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_invalid_token_raises_auth_error(self, client):
        """
        GIVEN: A garbage token string
        WHEN:  GET /api/v1/auth/me is called
        THEN:  Returns 401
        """
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
        )
        assert response.status_code == 401

    def test_valid_token_structure_passes_auth(self, client):
        """
        GIVEN: A valid JWT access token
        WHEN:  GET /api/v1/auth/me is called
        THEN:  Token passes the auth layer and returns 200 OK with user profile
        """
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, MagicMock
        from app.main import app
        from app.core.security import create_access_token
        from app.db.session import get_session

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = create_access_token(user_id, tenant_id, "OWNER")

        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.created_at = datetime.now(timezone.utc)

        mock_tenant = MagicMock()
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Tenant"
        mock_tenant.slug = "test-tenant"
        mock_tenant.plan = "free"
        mock_tenant.is_active = True
        mock_tenant.created_at = datetime.now(timezone.utc)

        mock_session = AsyncMock()
        async def mock_get(model, obj_id):
            if getattr(model, "__name__", "") == "User":
                return mock_user
            return mock_tenant
        mock_session.get.side_effect = mock_get

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["user"]["email"] == "test@example.com"
            assert data["tenant"]["name"] == "Test Tenant"
            assert data["role"] == "OWNER"
        finally:
            app.dependency_overrides.pop(get_session, None)

    def test_auth_routes_are_registered(self, client):
        """
        GIVEN: The app is running
        WHEN:  POST /api/v1/auth/register is called (empty body)
        THEN:  Returns 422 (Unprocessable) NOT 404 (route not found)
              → Confirms route is registered
        """
        response = client.post("/api/v1/auth/register", json={})
        # 422 = route exists but body validation failed (correct!)
        # 404 = route doesn't exist (wrong!)
        assert response.status_code == 422

    def test_login_route_is_registered(self, client):
        """Login route exists and requires a body."""
        response = client.post("/api/v1/auth/login", json={})
        assert response.status_code == 422  # Pydantic validation, not 404

    def test_register_creates_tenant_user_business_and_agent(self, client):
        """
        GIVEN: Registration payload with tenant_name
        WHEN:  POST /api/v1/auth/register is called
        THEN:  Creates Tenant, User, TenantUser, Business, AgentConfig and returns 201 Created
        """
        from app.main import app
        from app.db.session import get_session
        from app.models.tenant import Tenant
        from app.models.user import User
        from app.models.tenant_user import TenantUser
        from app.models.business import Business, WorkingHours
        from app.models.agent import AgentConfig

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        added_objects = []
        def capture_add(obj):
            if not getattr(obj, "id", None):
                obj.id = uuid.uuid4()
            if not getattr(obj, "created_at", None):
                from datetime import timezone
                obj.created_at = datetime.now(timezone.utc)
            added_objects.append(obj)
        mock_session.add = capture_add

        async def mock_flush():
            for obj in added_objects:
                if not getattr(obj, "id", None):
                    obj.id = uuid.uuid4()
                if not getattr(obj, "created_at", None):
                    from datetime import timezone
                    obj.created_at = datetime.now(timezone.utc)
        mock_session.flush = mock_flush

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            payload = {
                "tenant_name": "Sunrise Wellness Center",
                "full_name": "Dr. Anita Sharma",
                "email": "anita.unique@sunrisewellness.in",
                "password": "Password123",
            }
            response = client.post("/api/v1/auth/register", json=payload)
            assert response.status_code == 201
            data = response.json()
            assert data["user"]["email"] == "anita.unique@sunrisewellness.in"
            assert data["tenant"]["name"] == "Sunrise Wellness Center"
            assert "access_token" in data["tokens"]

            # Verify Tenant, User, TenantUser, Business, WorkingHours, and AgentConfig were all added
            types_added = [type(obj) for obj in added_objects]
            assert Tenant in types_added
            assert User in types_added
            assert TenantUser in types_added
            assert Business in types_added
            assert WorkingHours in types_added
            assert types_added.count(WorkingHours) == 7
            assert AgentConfig in types_added
        finally:
            app.dependency_overrides.pop(get_session, None)
