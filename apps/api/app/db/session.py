"""
Async SQLAlchemy 2.0 engine and session management.

Every module's repository layer imports `get_db` as a FastAPI dependency
to obtain a transactional AsyncSession. Sessions are always closed and
rolled back on error via the context-managed generator below.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Coroutine, TypeVar

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_T = TypeVar("_T")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base. Every ORM model in every module extends this."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("db_session_error")
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager version for use outside request scope (Celery tasks, scripts)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def run_async(coro: Coroutine[object, object, _T]) -> _T:
    """Run an async coroutine to completion from a synchronous Celery task.

    The module-level ``engine`` is created once at import; its asyncpg pool
    binds each pooled connection to the event loop that first opened it. Celery
    tasks call async code from a sync context via ``asyncio.run``, which creates
    then *closes* a fresh loop on every call. A connection pooled during one
    task is therefore bound to a now-dead loop by the time the next task runs in
    the same (long-lived, prefork) worker child, raising
    ``RuntimeError: Event loop is closed`` / ``... got Future ... attached to a
    different loop``.

    Disposing the pool at the start of each run guarantees every task opens its
    connections on the loop it actually runs on. Under the prefork pool each
    child executes one task at a time (``worker_prefetch_multiplier=1``), so no
    concurrent task in the same process is using the pool when it is disposed.
    Mirrors the per-test disposal in ``tests/_fixtures.py::db_session``.
    """

    async def _runner() -> _T:
        # close=False: abandon any pooled connection left over from a previous
        # task's (now-closed) loop WITHOUT trying to close it — closing would
        # await the dead loop and raise "Event loop is closed" / "Future
        # attached to a different loop". The abandoned asyncpg connection is
        # terminated on garbage collection; the fresh pool binds to this loop.
        await engine.dispose(close=False)
        return await coro

    return asyncio.run(_runner())


async def check_db_connection() -> bool:
    """Used by the /health endpoint to verify DB connectivity."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("db_health_check_failed")
        return False
