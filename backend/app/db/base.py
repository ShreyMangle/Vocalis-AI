"""
app/db/base.py — SQLAlchemy Async Engine & Session Factory

CONCEPT: What is an ORM?
=========================
ORM = Object-Relational Mapper.

Without ORM (raw SQL):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    user = {"id": row[0], "email": row[1]}  # manual mapping

With ORM (SQLAlchemy):
    user = await session.get(User, user_id)
    print(user.email)  # just Python objects!

SQLAlchemy lets us write Python classes that map to database tables.
When we say `User.email`, SQLAlchemy generates the SQL for us.

CONCEPT: What is async I/O?
============================
Your app handles hundreds of requests simultaneously.
Without async: each request "blocks" — while one request waits for the DB,
               no other requests can be served. Like one checkout lane.
With async:    while waiting for DB response, Python handles other requests.
               Like multiple self-checkout lanes.

asyncpg is the async PostgreSQL driver. create_async_engine uses it.

CONCEPT: Connection Pool
=========================
Opening a new DB connection is EXPENSIVE (~100ms).
A pool keeps N connections open and REUSES them.
When a request needs the DB, it "borrows" a connection from the pool.
When done, it "returns" it — the connection isn't closed, just reused.

Like a library book — you borrow, use, return. The book isn't destroyed.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.logging import logger

# =============================================================================
# ENGINE
# =============================================================================
# The engine is the core connection to the database.
# create_async_engine() returns an engine object — it doesn't actually
# open any connections yet. Connections are opened lazily when needed.
#
# Think of it like a factory: the factory is built here,
# but no products (connections) are made until a customer (request) arrives.

def create_engine() -> AsyncEngine:
    """
    Create the SQLAlchemy async engine from settings.
    
    Called once on application startup.
    The engine manages the connection pool automatically.
    """
    # str(settings.DATABASE_URL) converts the pydantic URL type to a plain string
    # "postgresql+asyncpg://..." tells SQLAlchemy to use the async driver
    engine = create_async_engine(
        str(settings.DATABASE_URL),

        # ── Pool settings ─────────────────────────────────────────────────
        # pool_size: how many connections to keep open permanently
        pool_size=settings.DB_POOL_SIZE,
        # max_overflow: extra connections allowed during traffic spikes
        # e.g., if pool_size=10 and max_overflow=20, we can have up to 30 total
        max_overflow=settings.DB_MAX_OVERFLOW,
        # pool_timeout: how long to wait for a free connection (seconds)
        # if no connection available after this → raises TimeoutError
        pool_timeout=settings.DB_POOL_TIMEOUT,
        # pool_pre_ping: before using a connection from the pool, check it's still alive
        # prevents "stale connection" errors (DB restarted, connection died)
        pool_pre_ping=True,

        # ── Logging ───────────────────────────────────────────────────────
        # echo=True prints every SQL query to the console (useful for debugging)
        # Only enable in DEBUG mode — it's very noisy in production
        echo=settings.DEBUG,
    )

    logger.info(
        "Database engine created",
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )

    return engine


# =============================================================================
# SESSION FACTORY
# =============================================================================
# async_sessionmaker creates a FACTORY for sessions.
# A "session" is like a shopping cart for your database operations:
# - You add items (SQL operations) to the cart.
# - At checkout (commit), they're all saved to the DB atomically.
# - If anything fails, you can rollback the entire cart — nothing is saved.
#
# expire_on_commit=False:
#   By default, after commit(), SQLAlchemy "expires" all objects —
#   meaning accessing them triggers another SQL query.
#   For async apps, this causes issues because you can't run queries
#   outside an async context. Setting to False prevents this.

def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory, bound to the given engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,   # We control commits manually (safer)
        autoflush=False,    # We control flushes manually (better performance)
    )


# =============================================================================
# MODULE-LEVEL SINGLETONS
# =============================================================================
# These are created once when the module loads.
# They're REUSED across all requests for the lifetime of the application.
# This is the "singleton" pattern — only one instance ever exists.
#
# In main.py, we call engine.dispose() on shutdown to close all connections cleanly.

engine: AsyncEngine = create_engine()
SessionFactory: async_sessionmaker[AsyncSession] = create_session_factory(engine)
