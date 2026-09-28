"""
alembic/env.py — Alembic Migration Environment

This file is the "brain" of Alembic — it tells Alembic:
  1. HOW to connect to the database.
  2. WHAT models to look at when auto-generating migrations.
  3. HOW to run migrations (online vs offline).

CONCEPT: Online vs Offline migrations
=======================================
Online:  Alembic connects to the real database and applies changes directly.
         Used for: normal deployments.

Offline: Alembic generates SQL scripts without connecting.
         Used for: DBAs who want to review SQL before applying it,
                   or environments where the app can't directly access the DB.
         We support both, but primarily use online.

CONCEPT: run_migrations_online() with async engine
====================================================
SQLAlchemy 2.x uses async connections. Alembic was originally designed for sync.
We bridge them using `run_sync` — which runs synchronous Alembic code inside
the async connection context.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ──────────────────────────────────────────────────────────────────────────────
# Import our application settings and ALL models.
# Models MUST be imported so SQLAlchemy's metadata knows what tables exist.
# If a model isn't imported here → Alembic won't generate a migration for it.
# ──────────────────────────────────────────────────────────────────────────────
from app.core.config import settings

# This import loads all models via app/models/__init__.py
# As we add models (Week 2, 3...), we add them to models/__init__.py
import app.models  # noqa: F401 — imported for side effect (registers models with Base)
from app.models.base import Base

# Alembic Config object — gives access to values in alembic.ini
config = context.config

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# `target_metadata` tells Alembic what tables SHOULD exist (from our models).
# Alembic compares this to what's ACTUALLY in the DB and generates the diff.
target_metadata = Base.metadata

# Set the database URL from our settings (not from alembic.ini)
# This is how we avoid hardcoding credentials in alembic.ini
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # render_as_batch=True would be needed for SQLite
        # For PostgreSQL we don't need it
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    """
    Synchronous migration runner — called inside the async connection.
    Alembic itself is synchronous, so we run it inside run_sync().
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # compare_type=True: detect column type changes (e.g., VARCHAR(100) → VARCHAR(255))
        compare_type=True,
        # compare_server_default=True: detect server-side default changes
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.
    This is the main path used for all real migrations.
    """
    # Create an async engine just for migrations
    # We use NullPool to avoid keeping connections open after migration
    # (migrations are one-shot operations, not long-running servers)
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Don't pool connections for migrations
    )

    async with connectable.connect() as connection:
        # run_sync bridges async connection → sync Alembic context
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — runs the async function."""
    asyncio.run(run_async_migrations())


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point: Alembic calls this file and checks the mode
# ──────────────────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
