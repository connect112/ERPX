"""
Audit module — automatic capture via SQLAlchemy session events.

This is what makes "every module must include audit logging" actually
true without every module's service layer needing to remember to call
anything: `register_audit_hooks()` is called once at app startup
(`app/main.py`) and attaches `before_flush`/`after_flush` listeners to
`sqlalchemy.orm.Session`. Since our `AsyncSession` delegates its real
flush work to an underlying sync `Session`, these class-level listeners
fire for every flush in the application — every module, every request,
automatically, including modules built after this one.

Two-phase capture is required because a newly-inserted row's primary key
isn't populated until the flush actually executes the INSERT:

  * `before_flush` walks `session.new` / `session.dirty` / `session.deleted`
    (the only point at which these collections are valid) and records a
    lightweight *description* of each change — for updates/deletes the ID
    is already known; for creates it isn't yet, so we keep a reference to
    the object itself and read `.id` off it later.
  * `after_flush` runs once the INSERT/UPDATE/DELETE statements have
    executed (so every object's `.id` is now populated) and turns those
    descriptions into real `AuditLog` rows via `session.add()`. Adding new
    objects inside `after_flush` is specifically supported by SQLAlchemy —
    they're folded into the same flush/transaction as the change being
    audited, so an audit entry can never exist without (or disagree with)
    the change it describes.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.audit_context import get_audit_context
from app.core.logging_config import get_logger
from modules.audit.models import AuditAction, AuditLog

logger = get_logger(__name__)

_PENDING_KEY = "_audit_pending"


def _serialize(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, PyEnum):
        return value.value
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _should_skip(obj) -> bool:
    cls = type(obj)
    if cls is AuditLog:
        return True
    return bool(getattr(cls, "__audit_skip__", False))


def _excluded_fields(obj) -> set[str]:
    return getattr(type(obj), "__audit_exclude_fields__", set())


def _column_keys(obj) -> list[str]:
    return [attr.key for attr in inspect(obj).mapper.column_attrs]


def _snapshot(obj) -> dict:
    excluded = _excluded_fields(obj)
    return {
        key: _serialize(getattr(obj, key))
        for key in _column_keys(obj)
        if key not in excluded
    }


def _diff(obj) -> dict:
    excluded = _excluded_fields(obj)
    state = inspect(obj)
    changes = {}
    for key in _column_keys(obj):
        if key in excluded:
            continue
        history = state.attrs[key].history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else getattr(obj, key)
        changes[key] = {"old": _serialize(old), "new": _serialize(new)}
    return changes


@event.listens_for(Session, "before_flush")
def _capture_pending_changes(session: Session, flush_context, instances) -> None:
    pending = session.info.setdefault(_PENDING_KEY, [])

    for obj in list(session.new):
        if _should_skip(obj):
            continue
        pending.append({"action": AuditAction.CREATE, "obj": obj})

    for obj in list(session.dirty):
        if _should_skip(obj) or not session.is_modified(obj, include_collections=False):
            continue
        changes = _diff(obj)
        if not changes:
            continue
        pending.append({
            "action": AuditAction.UPDATE,
            "entity_type": obj.__tablename__,
            "entity_id": obj.id,
            "organization_id": getattr(obj, "organization_id", None),
            "changes": changes,
        })

    for obj in list(session.deleted):
        if _should_skip(obj):
            continue
        pending.append({
            "action": AuditAction.DELETE,
            "entity_type": obj.__tablename__,
            "entity_id": obj.id,
            "organization_id": getattr(obj, "organization_id", None),
            "changes": _snapshot(obj),
        })


@event.listens_for(Session, "after_flush")
def _write_audit_rows(session: Session, flush_context) -> None:
    pending = session.info.pop(_PENDING_KEY, [])
    if not pending:
        return

    ctx = get_audit_context()

    for entry in pending:
        if entry["action"] == AuditAction.CREATE:
            obj = entry["obj"]
            entity_type = obj.__tablename__
            entity_id = getattr(obj, "id", None)
            organization_id = getattr(obj, "organization_id", None)
            if entity_type == "organizations":
                organization_id = entity_id
            changes = _snapshot(obj)
        else:
            entity_type = entry["entity_type"]
            entity_id = entry["entity_id"]
            organization_id = entry["organization_id"]
            if entity_type == "organizations" and organization_id is None:
                organization_id = entity_id
            changes = entry["changes"]

        session.add(
            AuditLog(
                organization_id=organization_id or ctx["organization_id"],
                user_id=ctx["user_id"],
                action=entry["action"],
                entity_type=entity_type,
                entity_id=entity_id,
                changes=changes,
                ip_address=ctx["ip_address"],
                user_agent=ctx["user_agent"],
                request_id=ctx["request_id"],
            )
        )


def register_audit_hooks() -> None:
    """
    No-op at call time — the `@event.listens_for` decorators above already
    registered the listeners at import time. This function exists so
    `app/main.py` has an explicit, greppable place that establishes
    "audit logging is active", and to guarantee this module (and therefore
    the listeners) has actually been imported before the app starts
    serving requests.
    """
    logger.info("audit_hooks_registered")
