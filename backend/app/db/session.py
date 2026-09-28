"""
app/db/session.py — FastAPI Database Session Dependency

CONCEPT: Dependency Injection in FastAPI
=========================================
Instead of every route handler creating its own DB session manually,
FastAPI provides "dependency injection" — you declare what a route NEEDS,
and FastAPI provides it automatically.

ANALOGY: A restaurant kitchen.
  Without DI: Every chef (route) walks to the supply room, grabs ingredients,
              cooks, cleans up — lots of repetitive work.
  With DI:    A prep cook (dependency) handles all prep. Chefs just get what
              they need, ready to go.

HOW IT WORKS:
    from fastapi import Depends
    from app.db.session import get_session

    @router.get("/users")
    async def list_users(session: AsyncSession = Depends(get_session)):
        # session is ready to use — no setup needed
        users = await session.execute(select(User))
        return users.scalars().all()
        # Session is automatically closed after the response is sent

CONCEPT: Context Manager (`async with`)
========================================
`async with session_factory() as session:` creates a session and GUARANTEES
it will be closed when the block ends — even if an exception occurs.

Like a "try/finally" but cleaner:
    session = session_factory()
    try:
        yield session          # Route uses the session here
        await session.commit() # Success → commit all changes
    except Exception:
        await session.rollback() # Error → undo all changes
    finally:
        await session.close()  # Always clean up

CONCEPT: Generator Dependencies (yield)
=========================================
When a FastAPI dependency uses `yield`, it splits into two parts:
  1. Code BEFORE yield: runs before the route handler (setup)
  2. Code AFTER yield: runs after the response is sent (cleanup)

This is perfect for DB sessions:
  - Before yield: open session
  - Route runs and uses session
  - After yield: commit or rollback, then close
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.base import SessionFactory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.

    Usage in any route:
        @router.get("/something")
        async def my_route(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(SomeModel))
            return result.scalars().all()

    The session is:
    - Opened before the route handler runs.
    - Committed automatically on success.
    - Rolled back automatically on exception.
    - Closed after the response is sent.
    """
    async with SessionFactory() as session:
        try:
            yield session
            # If we get here, the route ran without exceptions — commit the work.
            await session.commit()
        except Exception:
            # Something went wrong — undo EVERYTHING in this session.
            # This ensures the database is never left in a partial/corrupt state.
            await session.rollback()
            raise  # Re-raise the exception so FastAPI's error handlers catch it
        # Note: session.close() is called automatically by the `async with` block
