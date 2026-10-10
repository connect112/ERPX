"""
Is the machinery behind the page actually running?

Every scheduled job leaves a heartbeat when it finishes (`record`). `report` compares each heartbeat with how often that job
should run, and a job that failed or has gone quiet is shown on the overview and emailed once a day to the people set in
Settings (`due_alerts`). A job that has never run is shown as "not run yet", not as a fault, so a fresh deployment is not alarming.

Only the job's name, time, outcome, a short error class/message and a count are kept: nothing from comments or messages.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media.models import JobRun, SocialAccount


@dataclass(frozen=True)
class Job:
    key: str
    label: str
    every: timedelta  # how often it is scheduled
    grace: timedelta  # how late it may be before it counts as stalled
    needs_account: bool = False


JOBS = (
    Job("publish_due", "Publishing scheduled posts", timedelta(minutes=1), timedelta(minutes=5)),
    Job("recover_publishing", "Settling interrupted publishing", timedelta(minutes=5), timedelta(minutes=20)),
    Job("sync_inbox", "Reading comments and messages", timedelta(minutes=30), timedelta(minutes=90), needs_account=True),
    Job("sync_insights", "Reading insights", timedelta(days=1), timedelta(hours=6), needs_account=True),
    Job("make_reports", "Writing weekly and monthly reports", timedelta(days=1), timedelta(hours=6)),
    Job("refresh_tokens", "Keeping the Instagram access alive", timedelta(days=1), timedelta(hours=6), needs_account=True),
    Job("apply_retention", "Removing data past the retention period", timedelta(days=1), timedelta(hours=6)),
)
BY_KEY = {j.key: j for j in JOBS}
ALERT_EVERY = timedelta(hours=24)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def record(db: AsyncSession, job: str, ok: bool, error: str | None = None, count: int | None = None, detail: dict | None = None, now: datetime | None = None) -> None:
    """Leave a heartbeat. A later success clears the failure streak."""
    now = now or utcnow()
    message = (error or "")[:300] or None
    stmt = pg_insert(JobRun).values(
        id=uuid.uuid4(), job=job, last_finished_at=now, last_ok=ok, last_error=None if ok else message, last_count=count, detail=detail or {}, failures=0 if ok else 1, created_at=now, updated_at=now,
    )
    await db.execute(
        stmt.on_conflict_do_update(
            constraint="uq_social_job_runs_job",
            set_={
                "last_finished_at": now, "last_ok": ok, "last_error": None if ok else message, "last_count": count, "detail": detail or {},
                "failures": 0 if ok else JobRun.failures + 1, "updated_at": now,
            },
        )
    )


def _state(job: Job, row: JobRun | None, now: datetime) -> str:
    if row is None:
        return "never"
    if row.last_ok is False:
        return "failed"
    if now - row.last_finished_at > job.every + job.grace:
        return "late"
    return "ok"


async def report(db: AsyncSession, organization_id: uuid.UUID | None = None, now: datetime | None = None) -> list[dict]:
    now = now or utcnow()
    rows = {r.job: r for r in (await db.execute(select(JobRun))).scalars()}
    has_account = True
    if organization_id is not None:
        has_account = (await db.execute(select(SocialAccount.id).where(SocialAccount.organization_id == organization_id, SocialAccount.token_encrypted.is_not(None)))).first() is not None
    out = []
    for job in JOBS:
        row = rows.get(job.key)
        state = _state(job, row, now)
        applies = has_account or not job.needs_account
        out.append(
            {
                "key": job.key, "label": job.label, "state": state if applies else "idle", "applies": applies,
                "runs_every_minutes": int(job.every.total_seconds() // 60),
                "last_finished_at": row.last_finished_at if row else None, "last_ok": row.last_ok if row else None,
                "last_error": row.last_error if row else None, "consecutive_failures": row.failures if row else 0, "last_count": row.last_count if row else None,
            }
        )
    return out


async def due_alerts(db: AsyncSession, now: datetime | None = None) -> list[dict]:
    """Jobs that are failed or late and haven't been alerted about in the last 24 hours; marks them alerted."""
    now = now or utcnow()
    problems = []
    accounts_exist = (await db.execute(select(SocialAccount.id).where(SocialAccount.token_encrypted.is_not(None)))).first() is not None
    for job in JOBS:
        if job.needs_account and not accounts_exist:
            continue
        row = (await db.execute(select(JobRun).where(JobRun.job == job.key))).scalar_one_or_none()
        state = _state(job, row, now)
        if state not in ("failed", "late") or row is None:
            continue
        if row.alerted_at is not None and now - row.alerted_at < ALERT_EVERY:
            continue
        row.alerted_at = now
        detail = row.last_error if state == "failed" else f"It last finished {row.last_finished_at:%d %b %H:%M} UTC and should run every {int(job.every.total_seconds() // 60)} minute(s)."
        problems.append({"key": job.key, "label": job.label, "state": state, "detail": detail or "No detail was recorded."})
    await db.flush()
    return problems
