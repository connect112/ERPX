"""
The Placements job feed: jobs found on outside job sites, shown on the admin and student Placements pages.

Admins choose which sources to read and which kinds of job to keep; the feed refreshes on a schedule (and on request).
Students open the original job page to apply. Nothing is applied for inside ERPX, and nothing is copied from sites
that don't offer a feed or API (LinkedIn, Naukri and Indeed don't, so those are only offered as search links).
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from modules.placements.connectors.sources import (
    FETCHERS,
    MIN_INTERVAL_HOURS,
    SOURCES,
    JobItem,
    SourceError,
    is_configured,
    new_client,
)
from modules.placements.models import ExternalJob, JobFeedSettings

logger = get_logger(__name__)

DEFAULT_KEYWORDS = [
    "cyber",
    "cybersecurity",
    "information security",
    "infosec",
    "security analyst",
    "security engineer",
    "soc analyst",
    "devsecops",
    "devops",
    "cloud",
    "penetration",
    "pentest",
    "vulnerability",
    "appsec",
    "application security",
    "network security",
    "incident response",
    "threat",
    "site reliability",
    "sre",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
]
MAX_KEYWORDS = 60
STALE_AFTER = timedelta(days=21)

_FRESHER = re.compile(
    r"\b(fresher|freshers|entry[- ]level|graduates?|junior|jr\.?|intern|interns|internship|trainee|apprentice|"
    r"0\s*[-–to]+\s*[12]\s*years?|no experience|campus|early career)\b",
    re.I,
)
_SENIOR = re.compile(r"\b(senior|sr\.?|lead|principal|staff|manager|director|head|architect|vp|chief)\b", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clean_keywords(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        word = " ".join(str(value).lower().split())[:40]
        if word and word not in seen:
            seen.append(word)
    if not seen:
        raise ValidationError("Enter at least one keyword for the kind of job you want.")
    return seen[:MAX_KEYWORDS]


def keyword_pattern(keywords: list[str]) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in keywords) + r")(?![a-z0-9])", re.I)


def is_fresher_friendly(item: JobItem) -> bool:
    kind = (item.job_type or "").lower()
    if "intern" in kind:
        return True
    if _SENIOR.search(item.title):
        return False
    return bool(_FRESHER.search(item.title) or _FRESHER.search(item.summary or "") or _FRESHER.search(" ".join(item.tags)))


def wanted(item: JobItem, pattern: re.Pattern, fresher_only: bool) -> tuple[bool, bool]:
    """(keep it, is it fresher-friendly): the job's title must name one of the wanted roles (tags are too loose: a
    React developer is often tagged "aws")."""
    if not pattern.search(item.title):
        return False, False
    fresher = is_fresher_friendly(item)
    return (fresher or not fresher_only), fresher


class JobFeedService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- settings ----------------

    async def get_settings(self, organization_id: uuid.UUID) -> JobFeedSettings:
        row = (
            await self.db.execute(select(JobFeedSettings).where(JobFeedSettings.organization_id == organization_id))
        ).scalar_one_or_none()
        if row is None:
            row = JobFeedSettings(
                organization_id=organization_id,
                keywords=list(DEFAULT_KEYWORDS),
                fresher_only=True,
                sources={name: name in ("remotive", "arbeitnow") or is_configured(name) for name in SOURCES},
                source_state={},
            )
            self.db.add(row)
            await self.db.flush()
        return row

    async def update_settings(
        self,
        organization_id: uuid.UUID,
        keywords: list[str] | None,
        fresher_only: bool | None,
        sources: dict[str, bool] | None,
    ) -> JobFeedSettings:
        row = await self.get_settings(organization_id)
        if keywords is not None:
            row.keywords = clean_keywords(keywords)
        if fresher_only is not None:
            row.fresher_only = fresher_only
        if sources is not None:
            unknown = set(sources) - set(SOURCES)
            if unknown:
                raise ValidationError(f"Unknown job source: {sorted(unknown)[0]}.")
            row.sources = {**row.sources, **sources}
        await self.db.flush()
        return row

    # ---------------- reading the sources ----------------

    async def refresh(self, organization_id: uuid.UUID, force: bool = False) -> dict[str, dict]:
        """Read every enabled source that is due, keep the jobs that fit the organisation's wishes, and retire jobs
        that have gone. A source read recently is left alone (the sources limit how often they may be asked), unless
        `force`. Returns what happened per source."""
        row = await self.get_settings(organization_id)
        pattern = keyword_pattern(row.keywords)
        now = _now()
        state = dict(row.source_state or {})
        summary: dict[str, dict] = {}

        async with new_client() as client:
            for name in SOURCES:
                if not row.sources.get(name):
                    continue
                if not is_configured(name):
                    summary[name] = {"skipped": "needs an API key"}
                    continue
                last = (state.get(name) or {}).get("last_fetch_at")
                due = last is None or now - datetime.fromisoformat(last) >= timedelta(hours=MIN_INTERVAL_HOURS[name])
                if not due and not force:
                    summary[name] = {"skipped": "read recently"}
                    continue
                try:
                    items = await FETCHERS[name](client)
                except SourceError as exc:
                    summary[name] = {"error": str(exc)}
                    state[name] = {**(state.get(name) or {}), "error": str(exc)}
                    continue
                except Exception:  # noqa: BLE001 - one broken source must not stop the others
                    logger.warning("job_feed_source_failed", source=name, exc_info=True)
                    summary[name] = {"error": "something went wrong reading it"}
                    state[name] = {**(state.get(name) or {}), "error": "something went wrong reading it"}
                    continue
                result = await self._store(organization_id, name, items, pattern, row.fresher_only, now)
                summary[name] = result
                state[name] = {"last_fetch_at": now.isoformat(), "error": None, **result}

        row.source_state = state
        await self.db.flush()
        return summary

    async def _store(
        self,
        organization_id: uuid.UUID,
        source: str,
        items: list[JobItem],
        pattern: re.Pattern,
        fresher_only: bool,
        now: datetime,
    ) -> dict:
        existing = {
            job.external_id: job
            for job in (
                await self.db.execute(
                    select(ExternalJob).where(ExternalJob.organization_id == organization_id, ExternalJob.source == source)
                )
            ).scalars()
        }
        matched = new = 0
        seen: set[str] = set()
        for item in items:
            keep, fresher = wanted(item, pattern, fresher_only)
            if not keep or item.external_id in seen:
                continue
            seen.add(item.external_id)
            matched += 1
            job = existing.get(item.external_id)
            if job is None:
                job = ExternalJob(organization_id=organization_id, source=source, external_id=item.external_id)
                self.db.add(job)
                new += 1
            job.title, job.company_name, job.url = item.title, item.company, item.url
            job.location, job.remote, job.job_type = item.location, item.remote, item.job_type
            job.summary, job.tags, job.posted_at, job.salary_text = item.summary, item.tags, item.posted_at, item.salary_text
            job.fresher_friendly, job.is_active, job.last_seen_at = fresher, True, now
        # Gone from the feed (or no longer a match): stop showing it, keep the row.
        for external_id, job in existing.items():
            if external_id not in seen and job.is_active:
                job.is_active = False
        await self.db.flush()
        return {"fetched": len(items), "matched": matched, "new": new}

    async def clear_stale(self, organization_id: uuid.UUID) -> int:
        """Forget jobs that left their feed weeks ago."""
        result = await self.db.execute(
            ExternalJob.__table__.delete().where(
                ExternalJob.organization_id == organization_id,
                ExternalJob.is_active.is_(False),
                ExternalJob.last_seen_at < _now() - STALE_AFTER,
            )
        )
        return result.rowcount or 0

    # ---------------- listing ----------------

    async def list_jobs(
        self,
        organization_id: uuid.UUID,
        *,
        include_hidden: bool,
        q: str | None,
        source: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[ExternalJob], int]:
        conditions = [ExternalJob.organization_id == organization_id, ExternalJob.is_active.is_(True)]
        if not include_hidden:
            conditions.append(ExternalJob.hidden.is_(False))
        if source:
            conditions.append(ExternalJob.source == source)
        if q and q.strip():
            like = f"%{q.strip()}%"
            conditions.append(
                or_(ExternalJob.title.ilike(like), ExternalJob.company_name.ilike(like), ExternalJob.location.ilike(like))
            )
        total = (await self.db.execute(select(func.count()).select_from(ExternalJob).where(*conditions))).scalar_one()
        rows = (
            await self.db.execute(
                select(ExternalJob)
                .where(*conditions)
                .order_by(ExternalJob.posted_at.desc().nulls_last(), ExternalJob.last_seen_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars()
        return list(rows), total

    async def set_hidden(self, organization_id: uuid.UUID, job_id: uuid.UUID, hidden: bool) -> ExternalJob:
        job = (
            await self.db.execute(
                select(ExternalJob).where(ExternalJob.id == job_id, ExternalJob.organization_id == organization_id)
            )
        ).scalar_one_or_none()
        if job is None:
            raise NotFoundError("Job", job_id)
        job.hidden = hidden
        await self.db.flush()
        return job

    async def organizations_with_feed(self) -> list[uuid.UUID]:
        return list((await self.db.execute(select(JobFeedSettings.organization_id))).scalars())

