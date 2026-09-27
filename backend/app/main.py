"""
app/main.py — FastAPI Application Entry Point

CONCEPT: What is main.py?
==========================
main.py is the heart of the backend. It:
1. Creates the FastAPI application object.
2. Registers all middleware (CORS, logging, etc.).
3. Registers all API routes.
4. Defines startup/shutdown lifecycle hooks.
5. Registers global error handlers.

Think of it like the front door of a building:
  - Visitor (HTTP request) arrives at the door.
  - Security check (middleware).
  - Directed to the right department (router).
  - Department handles the request and returns a response.

UVICORN runs this app. Uvicorn is the actual server process.
Command: uvicorn app.main:app --host 0.0.0.0 --port 8000
         ↑ module  ↑ variable  ↑ bind to all interfaces  ↑ port
"""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import VoxAIError
from app.core.logging import setup_logging

# Set up logging FIRST — before anything else logs anything.
setup_logging()
logger = structlog.get_logger(__name__)


# =============================================================================
# LIFESPAN: Startup & Shutdown
# =============================================================================
# CONCEPT: Lifespan
# -----------------
# Some resources need to be created when the app starts and cleaned up when it stops.
# Examples: database connection pool, Redis connection, background workers.
#
# @asynccontextmanager + lifespan is the modern FastAPI way to do this.
# Code before `yield` runs on startup. Code after `yield` runs on shutdown.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # ── STARTUP ──────────────────────────────────────────────────────────────
    logger.info(
        "VoxAI starting up",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )

    # TODO (Week 2): Initialize database connection pool here
    # TODO (Week 2): Initialize Redis connection here
    # TODO (Week 8): Start background workers here

    logger.info("VoxAI startup complete ✓")

    yield  # ← Application runs here. Everything below runs on shutdown.

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    logger.info("VoxAI shutting down...")
    # TODO (Week 2): Close database connection pool here
    # TODO (Week 2): Close Redis connection here
    logger.info("VoxAI shutdown complete ✓")


# =============================================================================
# FASTAPI APP INSTANCE
# =============================================================================
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Voice Operations Platform — Powers AI receptionists for businesses.",
    # Disable auto-generated docs in production (security best practice)
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)


# =============================================================================
# MIDDLEWARE
# =============================================================================
# CONCEPT: Middleware
# -------------------
# Middleware is code that runs on EVERY request, before and after route handlers.
# Think of it as a conveyor belt — every request passes through it.
#
# Order matters: middleware is applied in reverse order of registration.
# (Last registered = outermost layer = runs first on request, last on response)

# ── 1. CORS Middleware ───────────────────────────────────────────────────────
# CONCEPT: CORS (Cross-Origin Resource Sharing)
# ---------------------------------------------
# Browsers block JavaScript from calling APIs on different domains by default.
# This is a security feature to prevent malicious websites from making requests
# to your API using a logged-in user's cookies.
#
# Our React frontend (localhost:5173) calls our API (localhost:8000).
# These are different "origins" → browser blocks it.
# CORS middleware tells the browser: "It's okay, this origin is trusted."
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,   # Allow cookies and auth headers
    allow_methods=["*"],       # Allow GET, POST, PUT, PATCH, DELETE, OPTIONS
    allow_headers=["*"],       # Allow all headers including Authorization
)


# ── 2. Request ID Middleware ─────────────────────────────────────────────────
# CONCEPT: Request IDs
# --------------------
# Every HTTP request gets a unique ID (UUID). This ID is:
# - Logged with every log entry for that request.
# - Returned in the response header.
#
# Why? When you have thousands of requests per second in logs, you can filter
# by request_id to see ALL log lines for a single request.
# Like a tracking number for a package — you can trace its entire journey.

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a unique request ID to every request and response."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Bind the request_id to the structlog context.
    # Any logger.info() call within this request will include request_id automatically.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    # Process the request and measure how long it takes
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # Add the request_id and timing to the response headers
    # This lets frontend developers see these in browser DevTools → Network tab
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms}ms"

    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )

    return response


# =============================================================================
# GLOBAL ERROR HANDLERS
# =============================================================================
# CONCEPT: Error Handlers
# -----------------------
# When an exception is raised anywhere in the application, FastAPI catches it.
# We register handlers to convert our custom exceptions into proper JSON responses.
#
# Without handlers: FastAPI returns a generic 500 Internal Server Error.
# With handlers: FastAPI returns a structured JSON with our error details.

@app.exception_handler(VoxAIError)
async def voxai_exception_handler(request: Request, exc: VoxAIError) -> JSONResponse:
    """
    Handle all VoxAI custom exceptions.
    
    Returns a consistent JSON error format:
    {
        "error": {
            "code": "NOT_FOUND",
            "message": "Tenant not found",
            "details": {},
            "request_id": "abc-123"
        }
    }
    """
    request_id = request.headers.get("X-Request-ID", "unknown")

    # Log the error — but only as ERROR if it's a server fault (5xx),
    # not for client errors like 404 or 400.
    log_fn = logger.error if exc.status_code >= 500 else logger.warning
    log_fn(
        "Application error",
        error_code=exc.code,
        error_message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for any unhandled exception.
    
    In production, never expose the raw exception message — it might contain
    internal implementation details that attackers could exploit.
    """
    request_id = request.headers.get("X-Request-ID", "unknown")

    logger.error(
        "Unhandled exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again.",
                "request_id": request_id,
            }
        },
    )


# =============================================================================
# HEALTH ENDPOINTS
# =============================================================================
# CONCEPT: Health Checks
# ----------------------
# Production systems need health check endpoints so:
# - Docker knows whether the container is alive (liveness probe).
# - Load balancers know whether to send traffic here (readiness probe).
# - Monitoring systems know the app is up.
#
# /health  → "Is the app process alive?" (always returns 200 if app is running)
# /ready   → "Is the app ready to serve traffic?" (checks DB, Redis, etc.)
#
# Docker Compose healthcheck: GET /health → if 200, container is healthy.

@app.get("/health", tags=["System"])
async def health_check():
    """
    Liveness probe — confirms the application process is running.
    
    Returns 200 immediately. Does NOT check database or external services.
    Used by: Docker, AWS ECS, load balancers.
    """
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready", tags=["System"])
async def readiness_check():
    """
    Readiness probe — confirms the app can serve traffic.
    
    Checks all critical dependencies:
    - Database connection
    - Redis connection
    
    Returns 200 if ready, 503 if not ready.
    Used by: load balancers to decide whether to route traffic here.
    """
    checks = {
        "database": "unchecked",
        "redis": "unchecked",
    }
    all_ok = True

    # TODO (Week 2): Replace with real DB ping
    # try:
    #     await db.execute(text("SELECT 1"))
    #     checks["database"] = "ok"
    # except Exception:
    #     checks["database"] = "error"
    #     all_ok = False
    checks["database"] = "ok (not yet connected)"

    # TODO (Week 2): Replace with real Redis ping
    # try:
    #     await redis_client.ping()
    #     checks["redis"] = "ok"
    # except Exception:
    #     checks["redis"] = "error"
    #     all_ok = False
    checks["redis"] = "ok (not yet connected)"

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
    )


# =============================================================================
# API ROUTERS (added incrementally each week)
# =============================================================================
# TODO (Week 2): from app.api.v1 import auth; app.include_router(auth.router, prefix="/api/v1")
# TODO (Week 3): from app.api.v1 import business; app.include_router(business.router, ...)
# ... and so on
