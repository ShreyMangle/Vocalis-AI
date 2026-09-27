"""
app/core/logging.py — Structured Logging Setup

CONCEPT: Structured Logging
============================
Regular print():        "User logged in at 10:30"
Structured logging:     {"event": "user_login", "user_id": "abc", "tenant_id": "xyz", 
                         "timestamp": "2026-09-27T10:30:00Z", "level": "info"}

WHY structured logs?
- Regular logs are strings. Strings are hard to search and filter.
- Structured logs are JSON. You can query them like a database.
  "Show me all LLM errors for tenant abc in the last hour" → one query.
- Tools like Grafana Loki, AWS CloudWatch, Datadog can parse JSON logs automatically.

We use `structlog` — the best structured logging library for Python.

HOW IT WORKS:
1. Every log entry is a Python dict.
2. structlog adds context automatically (request_id, tenant_id, etc.).
3. In development: pretty colorful output.
4. In production: clean JSON output.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import settings


def add_app_info(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Processor: Adds application metadata to every log entry.
    
    A "processor" in structlog is a function that transforms a log event dict.
    They run in a chain, each adding or modifying data.
    
    This processor adds:
    - app_name: "VoxAI"
    - environment: "development" or "production"
    """
    event_dict["app"] = settings.APP_NAME
    event_dict["env"] = settings.ENVIRONMENT
    return event_dict


def setup_logging() -> None:
    """
    Configure structlog for the application.
    
    Call this ONCE at startup in main.py.
    After this, every module just does:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.info("something happened", user_id=user.id, action="login")
    """
    # -------------------------------------------------------------------------
    # Shared processors — run on EVERY log entry regardless of output format
    # -------------------------------------------------------------------------
    shared_processors: list[Any] = [
        # Adds log level name: "info", "error", "debug", etc.
        structlog.stdlib.add_log_level,
        # Adds logger name: the __name__ passed to get_logger()
        structlog.stdlib.add_logger_name,
        # Adds ISO timestamp: "2026-09-27T10:30:00.123456Z"
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Our custom processor
        add_app_info,
        # Makes exception info JSON-serializable
        structlog.processors.format_exc_info,
        # Converts any non-JSON-serializable objects to strings
        structlog.processors.UnicodeDecoder(),
    ]

    # -------------------------------------------------------------------------
    # Output format: pretty in dev, JSON in production
    # -------------------------------------------------------------------------
    if settings.is_development and not settings.DEBUG:
        # ConsoleRenderer makes colored, human-readable output:
        # 2026-09-27T10:30:00Z [info     ] User logged in   user_id=abc
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # JSONRenderer makes machine-readable output:
        # {"timestamp": "...", "level": "info", "event": "User logged in", "user_id": "abc"}
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            # Bridge to Python's standard logging library
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Use stdlib's Logger as the underlying logger
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # Cache the logger — don't recreate it every call
        cache_logger_on_first_use=True,
    )

    # Configure the stdlib formatter to use our processors + renderer
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Attach to root handler — this captures ALL Python logging (including libraries)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Module-level logger for this file
logger = structlog.get_logger(__name__)
