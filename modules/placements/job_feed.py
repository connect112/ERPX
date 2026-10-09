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
    DEFAULT_BOARDS,
    FETCHERS,
    MIN_INTERVAL_HOURS,
    SOURCES,
    JobItem,
    SourceError,
    is_configured,
    new_client,
)
from modules.placements.experience import BUCKETS, OPEN_ENDED, extract_experience
from modules.placements.models import ExternalJob, JobFeedSettings

logger = get_logger(__name__)

DEFAULT_KEYWORDS = [
    "security",
    "ethical",
    "vapt",
    "forensic",
    "malware",
    "grc",
    "iam",
    "firewall",
    "siem",
    "soc",
    "platform engineer",
    "infrastructure engineer",
    "systems engineer",
    "sysadmin",
    "system administrator",
    "network engineer",
    "linux",
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
REFRESH_STALE_AFTER = timedelta(minutes=15)  # a refresh marker older than this is from a run that died
SEARCH_STYLE_SOURCES = {"adzuna", "jooble"}  # their searches are already limited to India
# "security" also names guards and officers; those are not wanted.
_NOT_IT = re.compile(r"\b(security (guard|officer|supervisor|manager - (retail|facility))|guard|watchman|bouncer)\b", re.I)
_INDIA_PLACES = (
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "navi mumbai", "delhi", "gurgaon", "gurugram",
    "noida", "chennai", "kolkata", "ahmedabad", "kochi", "cochin", "coimbatore", "jaipur", "indore", "chandigarh",
    "thiruvananthapuram", "trivandrum", "visakhapatnam", "vizag", "mysuru", "mysore", "nagpur", "bhubaneswar", "lucknow",
)
_OPEN_TO_INDIA = ("worldwide", "anywhere", "global", "apac", "asia", "remote - india", "remote, india")

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


_BOARD_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,59}$")


def clean_boards(boards: dict[str, list[str]]) -> dict[str, list[str]]:
    """Company board names, per hiring system, lower-cased and de-duplicated."""
    unknown = set(boards) - {"greenhouse", "lever"}
    if unknown:
        raise ValidationError(f"Company career pages can only be read from Greenhouse and Lever, not {sorted(unknown)[0]}.")
    cleaned: dict[str, list[str]] = {}
    for system, names in boards.items():
        seen: list[str] = []
        for name in names:
            token = str(name).strip().lower()
            if not _BOARD_NAME.match(token):
                raise ValidationError(f'"{name}" is not a valid company board name (letters, digits, - and _ only).')
            if token not in seen:
                seen.append(token)
        if len(seen) > 120:
            raise ValidationError("Add at most 120 company pages per hiring system.")
        cleaned[system] = seen
    return cleaned


def keyword_pattern(keywords: list[str]) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in keywords) + r")(?![a-z0-9])", re.I)


def is_fresher_friendly(item: JobItem) -> bool:
    kind = (item.job_type or "").lower()
    if "intern" in kind:
        return True
    if _SENIOR.search(item.title):
        return False
    return bool(_FRESHER.search(item.title) or _FRESHER.search(item.summary or "") or _FRESHER.search(" ".join(item.tags)))


def tidy_location(text: str | None) -> str | None:
    """Fit a place into its column. Some employers list hundreds of places in one string: show the Indian ones."""
    if not text:
        return None
    text = " ".join(text.split())
    if len(text) > 255:
        parts = [p.strip() for p in re.split(r"[;|]", text) if p.strip()]
        indian = [p for p in parts if any(word in p.lower() for word in _INDIA_PLACES)]
        text = "; ".join(indian or parts)
        if len(text) > 255:
            text = text[:252].rstrip(" ;,") + "..."
    return text


def _fit(value: str | None, size: int) -> str | None:
    return value[:size] if value else value


def in_india_or_open(item: JobItem) -> bool:
    """Located in India, or remote and open to people in India. Jobs with no place given at all are kept (a remote
    posting with an empty location is worldwide on the sources that do that)."""
    if item.source in SEARCH_STYLE_SOURCES:
        return True
    place = (item.location or "").lower()
    if any(word in place for word in _INDIA_PLACES):
        return True
    if item.remote and (not place or any(word in place for word in _OPEN_TO_INDIA)):
        return True
    return False


def wanted(item: JobItem, pattern: re.Pattern) -> tuple[bool, bool]:
    """(keep it, is it fresher-friendly): the job's title must name one of the wanted roles (tags are too loose: a
    React developer is often tagged "aws")."""
    if not pattern.search(item.title) or _NOT_IT.search(item.title):
        return False, False
    fresher = is_fresher_friendly(item)
    return True, fresher


class JobFeedService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- settings ----------------

    async def get_settings(self, organization_id: uuid.UUID) -> JobFeedSettings:
        row = (
            await self.db.execute(select(JobFeedSettings).where(JobFeedSettings.organization_id == organization_id))
        ).scalar_one_or_none()
        if row is not None and row.keywords == ["__reset__"]:
            row.keywords = list(DEFAULT_KEYWORDS)  # the wider default replaces the first version's list
        if row is None:
            row = JobFeedSettings(
                organization_id=organization_id,
                keywords=list(DEFAULT_KEYWORDS),
                india_only=True,
                boards={name: list(tokens) for name, tokens in DEFAULT_BOARDS.items()},
                sources={
                    name: name in ("remotive", "greenhouse", "lever") or (name in ("adzuna", "jooble") and is_configured(name))
                    for name in SOURCES
                },
                source_state={},
            )
            self.db.add(row)
            await self.db.flush()
        return row

    async def update_settings(
        self,
        organization_id: uuid.UUID,
        keywords: list[str] | None,
        sources: dict[str, bool] | None,
        india_only: bool | None = None,
        boards: dict[str, list[str]] | None = None,
    ) -> JobFeedSettings:
        row = await self.get_settings(organization_id)
        if keywords is not None:
            row.keywords = clean_keywords(keywords)
        if india_only is not None:
            row.india_only = india_only
        if boards is not None:
            row.boards = clean_boards(boards)
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
        options = dict(row.boards or {})
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
                    items = await FETCHERS[name](client, options)
                except SourceError as exc:
                    summary[name] = {"error": str(exc)}
                    state[name] = {**(state.get(name) or {}), "error": str(exc)}
                    continue
                except Exception:  # noqa: BLE001 - one broken source must not stop the others
                    logger.warning("job_feed_source_failed", source=name, exc_info=True)
                    summary[name] = {"error": "something went wrong reading it"}
                    state[name] = {**(state.get(name) or {}), "error": "something went wrong reading it"}
                    continue
                try:
                    async with self.db.begin_nested():  # a savepoint: a database problem undoes only this source
                        result = await self._store(organization_id, name, items, pattern, row.india_only, now)
                except Exception:  # noqa: BLE001
                    logger.warning("job_feed_store_failed", source=name, exc_info=True)
                    summary[name] = {"error": "its jobs could not be saved"}
                    state[name] = {**(state.get(name) or {}), "error": "its jobs could not be saved"}
                    continue
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
        india_only: bool,
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
            keep, fresher = wanted(item, pattern)
            if india_only and not in_india_or_open(item):
                keep = False
            if not keep or item.external_id in seen:
                continue
            seen.add(item.external_id)
            matched += 1
            job = existing.get(item.external_id)
            if job is None:
                job = ExternalJob(organization_id=organization_id, source=source, external_id=item.external_id[:255])
                self.db.add(job)
                new += 1
            job.title, job.company_name, job.url = item.title[:255], item.company[:255], item.url
            job.location, job.remote, job.job_type = tidy_location(item.location), item.remote, _fit(item.job_type, 30)
            job.summary, job.tags, job.posted_at = item.summary, item.tags[:20], item.posted_at
            job.salary_text = _fit(item.salary_text, 120)
            job.fresher_friendly, job.is_active, job.last_seen_at = fresher, True, now
            job.experience_min, job.experience_max, job.experience_estimated = extract_experience(
                item.title, item.summary, item.job_type
            )
            job.experience_parsed = True
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
        experience: str | None = None,
    ) -> tuple[list[ExternalJob], int]:
        conditions = [ExternalJob.organization_id == organization_id, ExternalJob.is_active.is_(True)]
        if not include_hidden:
            conditions.append(ExternalJob.hidden.is_(False))
        if source:
            conditions.append(ExternalJob.source == source)
        if experience == "unknown":
            conditions.append(ExternalJob.experience_min.is_(None))
        elif experience:
            if experience not in BUCKETS:
                raise ValidationError("Unknown experience range.")
            low, high = BUCKETS[experience]
            # The job's own range (open-ended when it says "and more") must overlap the chosen one.
            conditions.append(ExternalJob.experience_min.is_not(None))
            conditions.append(ExternalJob.experience_min <= high)
            conditions.append(func.coalesce(ExternalJob.experience_max, OPEN_ENDED) >= low)
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
                # Newest posting first; jobs whose source gives no date go last.
                .order_by(ExternalJob.posted_at.desc().nulls_last(), ExternalJob.last_seen_at.desc(), ExternalJob.id)
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

    # ---------------- background refresh ----------------

    async def start_refresh(self, organization_id: uuid.UUID) -> bool:
        """Mark a refresh as running; False when one already is (so a double click doesn't read the sources twice)."""
        row = await self.get_settings(organization_id)
        if row.refresh_started_at and _now() - row.refresh_started_at < REFRESH_STALE_AFTER:
            return False
        row.refresh_started_at = _now()
        await self.db.flush()
        return True

    @staticmethod
    def is_refreshing(row: JobFeedSettings) -> bool:
        return bool(row.refresh_started_at and _now() - row.refresh_started_at < REFRESH_STALE_AFTER)

    async def backfill_experience(self, organization_id: uuid.UUID) -> int:
        """Read the experience of jobs saved before it was tracked (no job sites involved)."""
        rows = (
            await self.db.execute(
                select(ExternalJob)
                .where(ExternalJob.organization_id == organization_id, ExternalJob.experience_parsed.is_(False))
                .limit(5000)
            )
        ).scalars().all()
        for job in rows:
            job.experience_min, job.experience_max, job.experience_estimated = extract_experience(
                job.title, job.summary, job.job_type
            )
            job.experience_parsed = True
        await self.db.flush()
        return len(rows)

    async def run_refresh(self, organization_id: uuid.UUID, force: bool = False) -> dict[str, dict]:
        """Read the sources and tidy up, then clear the running marker (also when something goes wrong)."""
        try:
            await self.backfill_experience(organization_id)
            summary = await self.refresh(organization_id, force=force)
            await self.clear_stale(organization_id)
            return summary
        finally:
            try:
                row = await self.get_settings(organization_id)
            except Exception:  # noqa: BLE001 - the session is unusable after a database error
                await self.db.rollback()
                row = await self.get_settings(organization_id)
            row.refresh_started_at = None
            await self.db.flush()

    async def organizations_with_feed(self) -> list[uuid.UUID]:
        return list((await self.db.execute(select(JobFeedSettings.organization_id))).scalars())

