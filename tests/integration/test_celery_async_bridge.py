"""
Regression test for the Celery sync->async DB bridge (``app.db.session.run_async``).

Celery tasks call async DB code from a synchronous task body. The module-level
``engine``'s asyncpg pool binds each connection to the event loop that opened
it, and ``asyncio.run`` creates then *closes* a fresh loop per call. Before
``run_async`` disposed the pool at the start of each run, a connection pooled by
one task invocation was bound to a dead loop by the next invocation in the same
(long-lived, prefork) worker child, raising ``RuntimeError: Event loop is
closed`` / ``... got Future ... attached to a different loop`` — observed live in
erpx_celery_worker on the reports.run_due_scheduled_reports retry. (``pool_pre_
ping`` does not mask it: the failure is an asyncio RuntimeError, not a DBAPI
disconnect.)

These are deliberately *synchronous* tests: ``run_async`` calls ``asyncio.run``,
which cannot be invoked from within a running event loop.
"""

from sqlalchemy import text

from app.db.session import AsyncSessionLocal, run_async


async def _db_roundtrip() -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        return result.scalar_one()


def test_run_async_survives_repeated_task_invocations():
    # Each call is a separate synchronous "task" invocation with its own event
    # loop, reusing the shared module-level engine — exactly the worker's
    # steady state. Without the pool dispose in run_async, the second call
    # raised "Event loop is closed". All three must succeed.
    assert run_async(_db_roundtrip()) == 1
    assert run_async(_db_roundtrip()) == 1
    assert run_async(_db_roundtrip()) == 1


def test_run_async_returns_coroutine_result():
    async def _compute() -> str:
        return "ok"

    assert run_async(_compute()) == "ok"
