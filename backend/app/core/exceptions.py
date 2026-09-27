"""
app/core/exceptions.py — Custom Exception Classes

CONCEPT: Why Custom Exceptions?
================================
Python has built-in exceptions like ValueError, KeyError, etc.
But in a web app we need richer exceptions that carry:
  - An HTTP status code (404, 400, 401, 403, 500...)
  - A machine-readable error code ("TENANT_NOT_FOUND")
  - A human-readable message ("The tenant you requested does not exist")

Example without custom exceptions (BAD):
    raise ValueError("Tenant not found")
    # FastAPI doesn't know what HTTP code to return → returns 500

Example with custom exceptions (GOOD):
    raise NotFoundError("Tenant not found", code="TENANT_NOT_FOUND")
    # Our error handler catches it → returns proper 404 JSON response

We have ONE global exception handler in main.py that catches these and
converts them to the correct HTTP responses.
"""

from typing import Any


class VoxAIError(Exception):
    """
    Base exception for all VoxAI errors.
    Every custom exception inherits from this.
    
    This lets you catch ALL application errors with a single except clause:
        except VoxAIError as e:
            log and return error response
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code              # Machine-readable: "TENANT_NOT_FOUND"
        self.status_code = status_code  # HTTP status code: 404
        self.details = details or {}  # Extra context for debugging


class NotFoundError(VoxAIError):
    """Resource does not exist. HTTP 404."""

    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=404, details=details)


class ValidationError(VoxAIError):
    """Input data is invalid. HTTP 422."""

    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=422, details=details)


class AuthenticationError(VoxAIError):
    """User is not authenticated (not logged in). HTTP 401."""

    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHENTICATED", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=401, details=details)


class AuthorizationError(VoxAIError):
    """User is authenticated but does not have permission. HTTP 403."""

    def __init__(self, message: str = "You do not have permission to perform this action", code: str = "FORBIDDEN", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=403, details=details)


class ConflictError(VoxAIError):
    """Resource already exists or state conflict. HTTP 409."""

    def __init__(self, message: str = "Resource conflict", code: str = "CONFLICT", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=409, details=details)


class ExternalServiceError(VoxAIError):
    """An external API (LLM, STT, TTS, Telephony) failed. HTTP 502."""

    def __init__(self, message: str = "External service error", code: str = "EXTERNAL_ERROR", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=502, details=details)


class RateLimitError(VoxAIError):
    """Too many requests. HTTP 429."""

    def __init__(self, message: str = "Too many requests, please slow down", code: str = "RATE_LIMITED", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=429, details=details)


class TenantIsolationError(VoxAIError):
    """
    A request tried to access another tenant's data.
    This should NEVER happen in normal use — if it does, it's a security bug.
    HTTP 403.
    """

    def __init__(self, message: str = "Cross-tenant access denied", code: str = "TENANT_ISOLATION_VIOLATION") -> None:
        super().__init__(message, code=code, status_code=403)
