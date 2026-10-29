"""
Writing a Pentrix record into its ERPX copy without two messages about the same record colliding.

Pentrix sends a message straight after each change, and two changes close together (a payment created, then confirmed) make two
messages that can arrive at the same moment. Both look for the row, find none, and both try to insert it; the unique key on Pentrix's
id refuses the second. That refusal is the right outcome for the data, but it must not surface as an error: the second message should
simply update the row the first one made.
"""
from typing import Any, Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.audit.hooks import _PENDING_KEY

T = TypeVar("T")


async def insert_or_existing(db: AsyncSession, model: type[T], key_column: Any, key: Any, make: Callable[[], T]) -> T:
    """Insert a new row made by `make`, or return the row that is already there if someone else inserted it first."""
    info = db.sync_session.info
    mark = len(info.get(_PENDING_KEY, []))
    try:
        async with db.begin_nested():
            row = make()
            db.add(row)
            await db.flush()
        return row
    except IntegrityError:
        pending = info.get(_PENDING_KEY)
        if pending is not None:
            del pending[mark:]  # the audit note for the insert that did not happen
        return (await db.execute(select(model).where(key_column == key))).scalar_one()
