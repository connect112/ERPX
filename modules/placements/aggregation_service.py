"""
Orchestrates one end-to-end pull of the job-aggregation pipeline: fetch from
every connector -> relevance-filter via `packages/ai` -> dedup across
sources -> fan out an upsert to every active organization -> sweep absent
postings closed. Called by `modules/placements/tasks.py` (Celery) and by the
manual-trigger route in `modules/placements/routes.py`.

Fetching happens ONCE per run, not once per organization — external pulls
aren't naturally org-scoped, and Adzuna/Jooble's rate/lifetime budgets can't
absorb an N-organization multiplier. This follows the one existing
precedent for "a scheduled task that must produce per-organization rows" in
this codebase, `modules.accounting.invoices.tasks`, which loops
`OrganizationRepository.list_all(skip=0, limit=10_000)` filtering
`org.is_active`.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.core.logging_config import get_logger
from modules.organizations.repository import OrganizationRepository
from modules.placements.aggregation_config import get_aggregation_keywords
from modules.placements.connectors import ConnectorResult, RawPosting, fetch_all
from modules.placements.models import AggregationRun, AggregationRunStatus, JobPosting, JobPostingStatus, JobType
from modules.placements.repository import (
    AggregationRunRepository,
    AggregationRunSourceRepository,
    CompanyRepository,
    JobPostingMatchRepository,
    JobPostingRepository,
)
from packages.ai.client import AIMessage, get_ai_client
from packages.ai.prompts import job_relevance_classifier_prompt, job_same_posting_classifier_prompt

logger = get_logger(__name__)

_RELEVANCE_BATCH_SIZE = 15
_DEDUP_AI_BATCH_SIZE = 10
_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_ai_json(text: str) -> list | dict:
    """Small, self-contained copy of `modules.ai.service._parse_json_response`
    — deliberately not imported cross-module (that helper is private to the
    `modules.ai` service layer); the fence-stripping logic is tiny enough
    that duplicating it here is clearer than reaching into another module's
    internals."""
    cleaned = text.strip()
    match = _FENCE_RE.match(cleaned)
    if match:
        cleaned = match.group(1)
    return json.loads(cleaned)


class AggregationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.job_repo = JobPostingRepository(db)
        self.company_repo = CompanyRepository(db)
        self.match_repo = JobPostingMatchRepository(db)
        self.run_repo = AggregationRunRepository(db)
        self.run_source_repo = AggregationRunSourceRepository(db)
        self.org_repo = OrganizationRepository(db)
        self.ai_client = get_ai_client()

    async def queue_run(self, triggered_by: str) -> AggregationRun:
        """Fast, synchronous insert used by the manual-trigger route so a
        `202` response always has a real row to reference, before `.delay()`
        hands the actual work to a Celery worker. The row's id MUST be
        passed through to `run_aggregation` as `run_id` — Celery task args
        are JSON-serialized, so it has to travel as a plain string/UUID
        across that boundary, not as the live ORM object created here (a
        prior version of this method took an in-process `AggregationRun`
        object, which cannot actually cross a real Celery `.delay()` call;
        that gap meant the task always created a *second*, disconnected
        run row instead of updating this one — caught only by a real
        Celery worker actually processing a real `.delay()`, not by tests
        that monkeypatch `.delay` to a no-op)."""
        return await self.run_repo.create(triggered_by=triggered_by, status=AggregationRunStatus.QUEUED)

    async def run_aggregation(
        self,
        triggered_by: str,
        sources: list[str] | None = None,
        run_id: uuid.UUID | str | None = None,
    ) -> AggregationRun:
        now = datetime.now(timezone.utc)
        run: AggregationRun | None = None
        if run_id is not None:
            run = await self.run_repo.get_by_id(
                run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(str(run_id))
            )
            if run is None:
                logger.warning("aggregation_run_id_not_found_falling_back", run_id=str(run_id))

        if run is None:
            run = await self.run_repo.create(triggered_by=triggered_by, status=AggregationRunStatus.RUNNING, started_at=now)
        else:
            run = await self.run_repo.update(run, status=AggregationRunStatus.RUNNING, started_at=now)

        try:
            return await self._run(run, sources)
        except Exception as exc:
            logger.exception("aggregation_run_failed", run_id=str(run.id))
            return await self.run_repo.update(
                run,
                status=AggregationRunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc)[:2000],
            )

    async def _run(self, run: AggregationRun, sources: list[str] | None) -> AggregationRun:
        keywords = get_aggregation_keywords()
        connector_results = await fetch_all(keywords, self.db, sources=sources)

        successful_sources: list[str] = []
        all_raw: list[RawPosting] = []
        for source, result in connector_results.items():
            await self.run_source_repo.create(
                aggregation_run_id=run.id,
                source=source,
                status=result.status,
                postings_fetched=len(result.postings),
                request_count=result.request_count,
                error_message=result.error_message,
            )
            if result.status == "success":
                successful_sources.append(source)
            all_raw.extend(result.postings)

        relevant: list[RawPosting] = []
        if all_raw:
            try:
                relevant = await self._filter_relevant(all_raw)
            except ServiceUnavailableError as exc:
                logger.warning("aggregation_relevance_filter_unavailable", run_id=str(run.id))
                return await self.run_repo.update(
                    run,
                    status=AggregationRunStatus.SKIPPED_NO_AI,
                    completed_at=datetime.now(timezone.utc),
                    error_message=str(exc),
                )

        groups = await self._dedupe(relevant)

        seen_external_ids_by_source: dict[str, set[str]] = {}
        for canonical, duplicates in groups:
            seen_external_ids_by_source.setdefault(canonical.source, set()).add(canonical.external_id)
            for duplicate, _score in duplicates:
                seen_external_ids_by_source.setdefault(duplicate.source, set()).add(duplicate.external_id)

        created = updated = closed = matches_created = 0
        active_orgs = [org for org in await self.org_repo.list_all(skip=0, limit=10_000) if org.is_active]

        for org in active_orgs:
            for canonical, duplicates in groups:
                canonical_row, was_created = await self._upsert_posting(org.id, canonical)
                created += int(was_created)
                updated += int(not was_created)

                for duplicate, score in duplicates:
                    duplicate_row, dup_created = await self._upsert_posting(org.id, duplicate)
                    created += int(dup_created)
                    updated += int(not dup_created)
                    await self.match_repo.upsert(
                        canonical_posting_id=canonical_row.id,
                        duplicate_posting_id=duplicate_row.id,
                        similarity_score=score,
                        matched_fields="title,company,location",
                    )
                    matches_created += 1

            closed += await self.job_repo.increment_absence_for_unseen(
                org.id, successful_sources, seen_external_ids_by_source
            )

        return await self.run_repo.update(
            run,
            status=AggregationRunStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc),
            postings_created=created,
            postings_updated=updated,
            postings_closed=closed,
            matches_created=matches_created,
        )

    async def _upsert_posting(self, organization_id: uuid.UUID, raw: RawPosting) -> tuple[JobPosting, bool]:
        company = await self.company_repo.get_by_name(organization_id, raw.company)
        if company is None:
            company = await self.company_repo.create(organization_id=organization_id, name=raw.company)

        now = datetime.now(timezone.utc)
        existing = await self.job_repo.get_by_source_external_id(organization_id, raw.source, raw.external_id)
        if existing is not None:
            updated_row = await self.job_repo.update(
                existing,
                title=raw.title,
                description=raw.description or None,
                location=raw.location,
                salary_min=raw.salary_min,
                salary_max=raw.salary_max,
                source_url=raw.source_url,
                company_id=company.id,
                last_seen_at=now,
                absence_streak=0,
            )
            return updated_row, False

        created_row = await self.job_repo.create(
            organization_id=organization_id,
            company_id=company.id,
            title=raw.title,
            description=raw.description or None,
            # None of the four sources cleanly maps to this enum
            # (full_time/part_time/internship/contract) from their response
            # shape alone — defaulting to FULL_TIME is a deliberate
            # simplification, not a data-loss bug; staff can correct
            # individual postings via the existing PATCH route same as any
            # manual one.
            job_type=JobType.FULL_TIME,
            location=raw.location,
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            status=JobPostingStatus.OPEN,
            source=raw.source,
            external_id=raw.external_id,
            source_url=raw.source_url,
            last_seen_at=now,
            absence_streak=0,
        )
        return created_row, True

    async def _filter_relevant(self, postings: list[RawPosting]) -> list[RawPosting]:
        relevant: list[RawPosting] = []
        system_prompt = job_relevance_classifier_prompt()

        for batch_start in range(0, len(postings), _RELEVANCE_BATCH_SIZE):
            batch = postings[batch_start : batch_start + _RELEVANCE_BATCH_SIZE]
            listing = "\n".join(
                f"{i}. Title: {p.title}\n   Company: {p.company}\n   "
                f"Description excerpt: {p.description[:300]}"
                for i, p in enumerate(batch)
            )
            result = await self.ai_client.complete(
                system_prompt, [AIMessage(role="user", content=listing)]
            )
            try:
                parsed = _parse_ai_json(result.text)
            except json.JSONDecodeError:
                # A malformed AI response for one batch shouldn't sink the
                # whole run — log and skip the batch (fail closed per
                # posting, not per run, since the run-level fail-closed
                # behavior is reserved for "AI not configured at all").
                logger.warning("aggregation_relevance_batch_unparseable", batch_start=batch_start)
                continue
            if not isinstance(parsed, list):
                logger.warning("aggregation_relevance_batch_not_list", batch_start=batch_start)
                continue

            relevant_indexes = {
                entry.get("index")
                for entry in parsed
                if isinstance(entry, dict) and entry.get("relevant") is True
            }
            for i, posting in enumerate(batch):
                if i in relevant_indexes:
                    relevant.append(posting)

        return relevant

    @staticmethod
    def _normalize_key(posting: RawPosting) -> str:
        return "|".join(
            [
                posting.title.strip().lower(),
                posting.company.strip().lower(),
                (posting.location or "").strip().lower(),
            ]
        )

    async def _dedupe(
        self, postings: list[RawPosting]
    ) -> list[tuple[RawPosting, list[tuple[RawPosting, float]]]]:
        """Two-tier dedup, both tiers only ever comparing postings from
        *different* sources (same-source duplicates are already handled by
        the `(organization, source, external_id)` upsert key):

        1. stdlib `difflib.SequenceMatcher` ratio on a normalized
           `title|company|location` string (no new dependency —
           `packages/ai` has no embedding capability to reuse, confirmed by
           reading `packages/ai/client.py`) — cheap, O(n^2), fine at this
           pipeline's expected volume (dozens, not thousands, of postings
           per run).
        2. difflib alone is confident for near-identical titles but MISSES
           genuinely differently-worded duplicates of the same real job
           (e.g. "SOC Analyst I" vs "Security Operations Center Analyst"
           scores ~0.74, "Pentester" vs "Penetration Testing Engineer"
           scores ~0.75 — both below the 0.85 auto-match threshold, both
           real same-job duplicates in practice). Pairs whose ratio falls
           in the "gray zone" (`PLACEMENTS_DEDUP_AI_FALLBACK_THRESHOLD` <=
           ratio < `PLACEMENTS_DEDUP_SIMILARITY_THRESHOLD`) get a batched
           same-posting judgment call to the same `packages/ai` client the
           relevance filter uses, rather than a hard string-similarity
           cutoff. Pairs below the fallback threshold are never sent to the
           AI at all — bounds the number of AI calls a run can trigger.
        """
        high = settings.PLACEMENTS_DEDUP_SIMILARITY_THRESHOLD
        low = settings.PLACEMENTS_DEDUP_AI_FALLBACK_THRESHOLD

        # Pass 1: every cross-source pair's ratio, computed once up front
        # (not during the greedy walk below) so the AI fallback can be
        # batched across the whole run instead of one call per canonical.
        pair_ratios: dict[tuple[int, int], float] = {}
        for i in range(len(postings)):
            for j in range(i + 1, len(postings)):
                if postings[i].source == postings[j].source:
                    continue
                ratio = SequenceMatcher(
                    None, self._normalize_key(postings[i]), self._normalize_key(postings[j])
                ).ratio()
                pair_ratios[(i, j)] = ratio

        gray_pairs = [pair for pair, ratio in pair_ratios.items() if low <= ratio < high]
        ai_confirmed_same: set[tuple[int, int]] = set()
        if gray_pairs:
            ai_confirmed_same = await self._classify_same_posting_pairs(postings, gray_pairs)

        def _is_duplicate(i: int, j: int) -> tuple[bool, float]:
            key = (i, j) if i < j else (j, i)
            ratio = pair_ratios.get(key, 0.0)
            if ratio >= high or key in ai_confirmed_same:
                return True, ratio
            return False, ratio

        # Pass 2: the same greedy single-link clustering as before, now
        # consulting the precomputed pass-1 decision instead of re-running
        # SequenceMatcher inline.
        remaining_indexes = list(range(len(postings)))
        groups: list[tuple[RawPosting, list[tuple[RawPosting, float]]]] = []

        while remaining_indexes:
            canonical_idx = remaining_indexes.pop(0)
            duplicates: list[tuple[RawPosting, float]] = []
            still_remaining: list[int] = []

            for idx in remaining_indexes:
                if postings[idx].source == postings[canonical_idx].source:
                    still_remaining.append(idx)
                    continue
                is_dup, ratio = _is_duplicate(canonical_idx, idx)
                if is_dup:
                    duplicates.append((postings[idx], ratio))
                else:
                    still_remaining.append(idx)

            groups.append((postings[canonical_idx], duplicates))
            remaining_indexes = still_remaining

        return groups

    async def _classify_same_posting_pairs(
        self, postings: list[RawPosting], pairs: list[tuple[int, int]]
    ) -> set[tuple[int, int]]:
        """Batched AI fallback for dedup's "gray zone" pairs. Fails closed
        toward NOT merging: if the AI is unreachable or returns something
        unparseable mid-batch, those pairs are simply left out of the
        result (treated as different postings) rather than guessed at —
        showing two rows for what's actually one real job is a much smaller
        problem than silently merging two genuinely different openings. By
        the time dedup runs, `_filter_relevant` has already succeeded this
        run (a hard AI-unavailable failure aborts the whole run earlier,
        before reaching dedup), so this is a defensive fallback for a
        mid-run failure, not the primary "AI not configured" path."""
        confirmed: set[tuple[int, int]] = set()
        system_prompt = job_same_posting_classifier_prompt()

        for batch_start in range(0, len(pairs), _DEDUP_AI_BATCH_SIZE):
            batch = pairs[batch_start : batch_start + _DEDUP_AI_BATCH_SIZE]
            listing = "\n".join(
                f"{k}. A: {postings[i].title} at {postings[i].company} ({postings[i].location or 'n/a'})\n"
                f"   B: {postings[j].title} at {postings[j].company} ({postings[j].location or 'n/a'})"
                for k, (i, j) in enumerate(batch)
            )
            try:
                result = await self.ai_client.complete(
                    system_prompt, [AIMessage(role="user", content=listing)]
                )
                parsed = _parse_ai_json(result.text)
            except (ServiceUnavailableError, json.JSONDecodeError):
                logger.warning("aggregation_dedup_ai_fallback_batch_failed", batch_start=batch_start)
                continue
            if not isinstance(parsed, list):
                logger.warning("aggregation_dedup_ai_fallback_batch_not_list", batch_start=batch_start)
                continue

            same_indexes = {
                entry.get("index")
                for entry in parsed
                if isinstance(entry, dict) and entry.get("same_posting") is True
            }
            for k, pair in enumerate(batch):
                if k in same_indexes:
                    confirmed.add(pair)

        return confirmed
