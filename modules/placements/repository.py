import uuid
from datetime import datetime

from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.placements.models import (
    AggregationRun,
    AggregationRunSource,
    AggregationRunStatus,
    Application,
    ApplicationStatus,
    Company,
    JobPosting,
    JobPostingMatch,
    JobPostingStatus,
)


class CompanyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Company:
        company = Company(**fields)
        self.db.add(company)
        await self.db.flush()
        await self.db.refresh(company)
        return company

    async def get_by_id(self, company_id: uuid.UUID, organization_id: uuid.UUID) -> Company | None:
        result = await self.db.execute(
            select(Company).where(
                Company.id == company_id,
                Company.organization_id == organization_id,
                Company.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self, organization_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[Company], int]:
        conditions = [Company.organization_id == organization_id, Company.deleted_at.is_(None)]
        count_result = await self.db.execute(select(func.count()).select_from(Company).where(*conditions))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Company).where(*conditions).order_by(Company.name.asc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, company: Company, **fields) -> Company:
        for key, value in fields.items():
            if value is not None:
                setattr(company, key, value)
        await self.db.flush()
        await self.db.refresh(company)
        return company

    async def soft_delete(self, company: Company) -> None:
        from datetime import datetime, timezone

        company.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def get_by_name(self, organization_id: uuid.UUID, name: str) -> Company | None:
        """Used by the aggregation pipeline's get-or-create step
        (aggregation_service.py) — external postings arrive with a company
        *name*, not an id, so a source-of-truth company lookup has to go by
        name rather than the id-based `get_by_id` above."""
        result = await self.db.execute(
            select(Company).where(
                Company.organization_id == organization_id,
                Company.name == name,
                Company.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


class JobPostingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> JobPosting:
        posting = JobPosting(**fields)
        self.db.add(posting)
        await self.db.flush()
        await self.db.refresh(posting)
        return posting

    async def get_by_id(self, posting_id: uuid.UUID, organization_id: uuid.UUID) -> JobPosting | None:
        result = await self.db.execute(
            select(JobPosting).where(
                JobPosting.id == posting_id, JobPosting.organization_id == organization_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_organization(
        self,
        organization_id: uuid.UUID,
        status: JobPostingStatus | None = None,
        company_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[JobPosting], int]:
        conditions = [JobPosting.organization_id == organization_id]
        if status is not None:
            conditions.append(JobPosting.status == status)
        if company_id is not None:
            conditions.append(JobPosting.company_id == company_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(JobPosting).where(*conditions)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(JobPosting)
            .where(*conditions)
            .order_by(JobPosting.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, posting: JobPosting, **fields) -> JobPosting:
        for key, value in fields.items():
            if value is not None:
                setattr(posting, key, value)
        await self.db.flush()
        await self.db.refresh(posting)
        return posting

    async def delete(self, posting: JobPosting) -> None:
        await self.db.delete(posting)
        await self.db.flush()

    async def get_by_source_external_id(
        self, organization_id: uuid.UUID, source: str, external_id: str
    ) -> JobPosting | None:
        """The upsert key the aggregation pipeline dedupes against — see the
        `(organization_id, source, external_id)` partial-unique index this
        mirrors."""
        result = await self.db.execute(
            select(JobPosting).where(
                JobPosting.organization_id == organization_id,
                JobPosting.source == source,
                JobPosting.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def increment_absence_for_unseen(
        self,
        organization_id: uuid.UUID,
        source_in: list[str],
        seen_external_ids_by_source: dict[str, set[str]],
    ) -> int:
        """Bulk-increments `absence_streak` for every non-manual posting this
        run's connectors *should* have re-seen but didn't, and flips any
        posting that's now missed 3 consecutive pulls to `closed` — never
        deletes. Returns the count newly flipped to closed. Done per-source
        (rather than one query across all `source_in`) since each source's
        "seen" set is disjoint and a posting must only have its streak reset
        by its own source's sighting."""
        closed_count = 0
        for source in source_in:
            seen_ids = seen_external_ids_by_source.get(source, set())
            conditions = [
                JobPosting.organization_id == organization_id,
                JobPosting.source == source,
            ]
            if seen_ids:
                conditions.append(JobPosting.external_id.notin_(seen_ids))
            await self.db.execute(
                sa_update(JobPosting)
                .where(*conditions)
                .values(absence_streak=JobPosting.absence_streak + 1)
            )
            result = await self.db.execute(
                sa_update(JobPosting)
                .where(
                    JobPosting.organization_id == organization_id,
                    JobPosting.source == source,
                    JobPosting.absence_streak >= 3,
                    JobPosting.status != JobPostingStatus.CLOSED,
                )
                .values(status=JobPostingStatus.CLOSED)
                .returning(JobPosting.id)
            )
            closed_count += len(result.fetchall())
        await self.db.flush()
        return closed_count


class JobPostingMatchRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(
        self,
        canonical_posting_id: uuid.UUID,
        duplicate_posting_id: uuid.UUID,
        similarity_score: float,
        matched_fields: str | None = None,
    ) -> JobPostingMatch:
        result = await self.db.execute(
            select(JobPostingMatch).where(
                JobPostingMatch.canonical_posting_id == canonical_posting_id,
                JobPostingMatch.duplicate_posting_id == duplicate_posting_id,
            )
        )
        match = result.scalar_one_or_none()
        if match is not None:
            match.similarity_score = similarity_score
            match.matched_fields = matched_fields
            await self.db.flush()
            return match

        match = JobPostingMatch(
            canonical_posting_id=canonical_posting_id,
            duplicate_posting_id=duplicate_posting_id,
            similarity_score=similarity_score,
            matched_fields=matched_fields,
        )
        self.db.add(match)
        await self.db.flush()
        await self.db.refresh(match)
        return match

    async def list_for_canonical(self, canonical_posting_id: uuid.UUID) -> list[JobPostingMatch]:
        result = await self.db.execute(
            select(JobPostingMatch).where(
                JobPostingMatch.canonical_posting_id == canonical_posting_id
            )
        )
        return list(result.scalars().all())


class AggregationRunRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AggregationRun:
        run = AggregationRun(**fields)
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> AggregationRun | None:
        result = await self.db.execute(select(AggregationRun).where(AggregationRun.id == run_id))
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 20) -> list[AggregationRun]:
        result = await self.db.execute(
            select(AggregationRun).order_by(AggregationRun.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, run: AggregationRun, **fields) -> AggregationRun:
        for key, value in fields.items():
            if value is not None:
                setattr(run, key, value)
        await self.db.flush()
        await self.db.refresh(run)
        return run


class AggregationRunSourceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> AggregationRunSource:
        row = AggregationRunSource(**fields)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def list_for_run(self, aggregation_run_id: uuid.UUID) -> list[AggregationRunSource]:
        result = await self.db.execute(
            select(AggregationRunSource).where(
                AggregationRunSource.aggregation_run_id == aggregation_run_id
            )
        )
        return list(result.scalars().all())

    async def sum_request_count(self, source: str, since: datetime | None = None) -> int:
        """Used by the Adzuna daily-budget and Jooble lifetime-budget checks
        (connectors/adzuna.py, connectors/jooble.py) before making another
        request. `since=None` sums the whole table — Jooble's lifetime cap
        needs exactly that; Adzuna's daily cap passes `since=<start of
        today, UTC>`."""
        conditions = [AggregationRunSource.source == source]
        if since is not None:
            conditions.append(AggregationRunSource.created_at >= since)
        result = await self.db.execute(
            select(func.coalesce(func.sum(AggregationRunSource.request_count), 0)).where(*conditions)
        )
        return int(result.scalar_one())


class ApplicationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **fields) -> Application:
        application = Application(**fields)
        self.db.add(application)
        await self.db.flush()
        await self.db.refresh(application)
        return application

    async def get_by_id(self, application_id: uuid.UUID) -> Application | None:
        result = await self.db.execute(select(Application).where(Application.id == application_id))
        return result.scalar_one_or_none()

    async def get_by_posting_and_student(
        self, job_posting_id: uuid.UUID, student_id: uuid.UUID
    ) -> Application | None:
        result = await self.db.execute(
            select(Application).where(
                Application.job_posting_id == job_posting_id, Application.student_id == student_id
            )
        )
        return result.scalar_one_or_none()

    async def list_for_posting(self, job_posting_id: uuid.UUID) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.job_posting_id == job_posting_id)
            .order_by(Application.applied_at.asc())
        )
        return list(result.scalars().all())

    async def list_for_student(self, student_id: uuid.UUID) -> list[Application]:
        result = await self.db.execute(
            select(Application)
            .where(Application.student_id == student_id)
            .order_by(Application.applied_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, application: Application, **fields) -> Application:
        for key, value in fields.items():
            if value is not None:
                setattr(application, key, value)
        await self.db.flush()
        await self.db.refresh(application)
        return application
