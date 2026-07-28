"""
Root-level pytest configuration.

Deliberately has no database-touching imports: `tests/unit` must be able
to run without a live Postgres connection or even the ability to
construct a SQLAlchemy engine. Fixtures that need the database
(`db_session`, `client`, `organization`, `superuser`, ...) live in
`tests/_fixtures.py` and are pulled in only by the conftest.py of the
test packages that actually need them (`tests/api`, `tests/integration`).
"""

import asyncio
import sys

if sys.platform == "win32":
    # asyncpg's connection-cancellation path uses raw socket operations
    # ProactorEventLoop (asyncio's default on Windows) doesn't support,
    # surfacing as "Event loop is closed" / "NoneType has no attribute
    # 'send'" errors that cascade across every subsequent test in the
    # session. CI runs on Linux where this never applies; this only
    # changes local Windows test runs.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
