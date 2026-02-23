"""Async database engine and session factory.

Call init_engine() once at app startup (from the FastAPI lifespan handler).
Use get_session() or get_session_or_none() to get database sessions.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

# Module-level singletons — created once at startup, reused for the
# lifetime of the process.
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    """Create the async engine and session factory.

    Called once during app startup from the FastAPI lifespan handler.

    pool_size=5      → keep 5 connections open and ready
    max_overflow=10  → allow up to 10 more if all 5 are busy
    pool_pre_ping    → test connections before using them (handles DB restarts)
    """
    global _engine, _session_factory
    if _engine is not None:
        logger.warning("init_engine called more than once; ignoring")
        return
    kwargs: dict = {"echo": False}
    if not database_url.startswith("sqlite"):
        kwargs.update(pool_size=5, max_overflow=10, pool_pre_ping=True)
    _engine = create_async_engine(database_url, **kwargs)
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
    )
    logger.info("Database engine initialized")


async def dispose_engine() -> None:
    """Close all database connections. Called during app shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine disposed")
    _engine = None
    _session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session. Raises if engine not initialized."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized. Call init_engine() first.")
    async with _session_factory() as session:
        yield session


async def get_session_or_none() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield a database session if available, otherwise None.

    This is the graceful degradation path: if the DB is down or not
    configured, callers get None and should skip database operations.
    """
    if _session_factory is None:
        yield None
        return
    try:
        async with _session_factory() as session:
            yield session
    except Exception:
        logger.warning("Database unavailable, proceeding without persistence", exc_info=True)
        yield None
