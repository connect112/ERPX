"""
Integration tests for `AggregationService` — real Postgres, real
Company/JobPosting/JobPostingMatch rows. Connector HTTP calls are mocked out
entirely (`fetch_all` is monkeypatched to return canned `ConnectorResult`s,
so these tests exercise normalization-through-upsert without touching the
network — each connector's own request/response mapping is covered
separately in `tests/unit/test_placements_connectors.py`), and the AI
relevance filter is mocked via a fake `AIClient`, since no fake/stub LLM
client fixture exists elsewhere in this repo to reuse.
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.core.exceptions import ServiceUnavailableError
from modules.placements.aggregation_service import AggregationService
from modules.placements.connectors.base import ConnectorResult, RawPosting
from modules.placements.models import (
    AggregationRun,
    AggregationRunStatus,
    JobPosting,
    JobPostingMatch,
    JobPostingStatus,
)
from packages.ai.client import AICompletionResult, AIMessage

pytestmark = pytest.mark.integration


class _FakeAIClient:
    """Stub for `packages.ai.client.AIClient`. The pipeline can call
    `complete()` more than once per run now (relevance filter, then
    optionally the dedup gray-zone fallback) — `responses` is a queue,
    popped in call order and repeating the last entry once exhausted, so
    single-call tests can keep passing `response_text=` as before while
    multi-call tests pass an explicit `responses=[...]` list. Raises
    `ServiceUnavailableError` if `unavailable` is set, mirroring what a real
    `AnthropicClient`/`OpenAICompatibleClient` does when `AI_API_KEY` is
    unset."""

    def __init__(
        self,
        response_text: str | None = None,
        responses: list[str] | None = None,
        unavailable: bool = False,
    ):
        self.responses = responses if responses is not None else (
            [response_text] if response_text is not None else []
        )
        self.unavailable = unavailable
        self.calls: list[list[AIMessage]] = []

    async def complete(self, system_prompt, messages, max_tokens=None, temperature=0.7):
        self.calls.append(messages)
        if self.unavailable:
            raise ServiceUnavailableError("AI provider is not configured.")
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return AICompletionResult(text=self.responses[index], model="fake-model")


def _all_relevant_response(count: int) -> str:
    return json.dumps([{"index": i, "relevant": True, "reason": "cybersecurity role"} for i in range(count)])


def _same_posting_response(true_indexes: set[int], count: int) -> str:
    return json.dumps(
        [
            {
                "index": i,
                "same_posting": i in true_indexes,
                "reason": "same role, reworded title" if i in true_indexes else "different opening",
            }
            for i in range(count)
        ]
    )


def _raw(source: str, external_id: str, title: str, company: str, location: str = "Remote") -> RawPosting:
    return RawPosting(
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        remote=False,
        salary_min=None,
        salary_max=None,
        description="A real cybersecurity role.",
        posted_at=datetime.now(timezone.utc),
        source_url=f"https://example.com/{source}/{external_id}",
    )


async def _run(monkeypatch, db_session, connector_results, ai_client):
    async def _fake_fetch_all(keywords, db, sources=None):
        return connector_results

    monkeypatch.setattr("modules.placements.aggregation_service.fetch_all", _fake_fetch_all)
    monkeypatch.setattr("modules.placements.aggregation_service.get_ai_client", lambda: ai_client)

    service = AggregationService(db_session)
    return await service.run_aggregation(triggered_by="test")


async def test_dedup_creates_one_match_not_two_independent_postings(db_session, organization, monkeypatch):
    canonical = _raw("adzuna", "aa-1", "SOC Analyst", "Acme Security", "Bengaluru")
    duplicate = _raw("reed", "rr-1", "SOC Analyst", "Acme Security", "Bengaluru")
    connector_results = {
        "adzuna": ConnectorResult(postings=[canonical], request_count=1, status="success"),
        "reed": ConnectorResult(postings=[duplicate], request_count=1, status="success"),
    }
    ai_client = _FakeAIClient(response_text=_all_relevant_response(2))

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.status == AggregationRunStatus.COMPLETED
    assert run.matches_created == 1

    postings = (
        await db_session.execute(
            select(JobPosting).where(JobPosting.organization_id == organization.id)
        )
    ).scalars().all()
    assert len(postings) == 2  # both rows kept, each with its own source/source_url

    matches = (await db_session.execute(select(JobPostingMatch))).scalars().all()
    assert len(matches) == 1


async def test_rerun_against_identical_data_creates_no_duplicates(db_session, organization, monkeypatch):
    posting = _raw("adzuna", "aa-2", "Penetration Tester", "Beta Corp")
    connector_results = {"adzuna": ConnectorResult(postings=[posting], request_count=1, status="success")}
    ai_client = _FakeAIClient(response_text=_all_relevant_response(1))

    first_run = await _run(monkeypatch, db_session, connector_results, ai_client)
    assert first_run.postings_created == 1
    assert first_run.postings_updated == 0

    second_run = await _run(monkeypatch, db_session, connector_results, ai_client)
    assert second_run.postings_created == 0
    assert second_run.postings_updated == 1

    postings = (
        await db_session.execute(
            select(JobPosting).where(
                JobPosting.organization_id == organization.id, JobPosting.source == "adzuna"
            )
        )
    ).scalars().all()
    assert len(postings) == 1


async def test_absence_past_grace_period_closes_not_deletes(db_session, organization, monkeypatch):
    from modules.placements.repository import CompanyRepository, JobPostingRepository

    company = await CompanyRepository(db_session).create(organization_id=organization.id, name="Gamma Inc")
    existing = await JobPostingRepository(db_session).create(
        organization_id=organization.id,
        company_id=company.id,
        title="Cloud Security Engineer",
        status=JobPostingStatus.OPEN,
        source="adzuna",
        external_id="aa-missing",
        source_url="https://example.com/adzuna/aa-missing",
        last_seen_at=datetime.now(timezone.utc),
        absence_streak=2,
    )

    # This run's Adzuna connector succeeds but doesn't see `aa-missing`
    # again — the 3rd consecutive miss.
    connector_results = {"adzuna": ConnectorResult(postings=[], request_count=1, status="success")}
    ai_client = _FakeAIClient(response_text="[]")

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.postings_closed == 1
    await db_session.refresh(existing)
    assert existing.status == JobPostingStatus.CLOSED
    assert existing.absence_streak == 3


async def test_relevance_filter_skips_irrelevant_postings(db_session, organization, monkeypatch):
    relevant = _raw("adzuna", "aa-3", "SOC Analyst", "Delta Security")
    irrelevant = _raw("adzuna", "aa-4", "Airport Security Guard", "Delta Airport Services")
    connector_results = {
        "adzuna": ConnectorResult(postings=[relevant, irrelevant], request_count=1, status="success")
    }
    ai_response = json.dumps(
        [
            {"index": 0, "relevant": True, "reason": "genuine SOC role"},
            {"index": 1, "relevant": False, "reason": "physical security, not cyber"},
        ]
    )
    ai_client = _FakeAIClient(response_text=ai_response)

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.postings_created == 1
    postings = (
        await db_session.execute(
            select(JobPosting).where(JobPosting.organization_id == organization.id)
        )
    ).scalars().all()
    assert len(postings) == 1
    assert postings[0].title == "SOC Analyst"


async def test_dedup_ai_fallback_catches_differently_worded_duplicate(db_session, organization, monkeypatch):
    """The gap this pass exists to close: 'SOC Analyst I' vs 'Security
    Operations Center Analyst' scores ~0.74 on difflib alone (measured
    directly — see docs/architecture/placements-job-aggregation.md), well
    below the 0.85 auto-match threshold, despite being the same real job.
    Confirms the AI gray-zone fallback (not string similarity alone) is
    what merges them into one JobPostingMatch."""
    canonical = _raw("adzuna", "aa-6", "SOC Analyst I", "Zeta Security", "Pune")
    duplicate = _raw("reed", "rr-6", "Security Operations Center Analyst", "Zeta Security", "Pune")
    connector_results = {
        "adzuna": ConnectorResult(postings=[canonical], request_count=1, status="success"),
        "reed": ConnectorResult(postings=[duplicate], request_count=1, status="success"),
    }
    # Call 1: relevance filter (both postings relevant). Call 2: dedup
    # gray-zone fallback for the one pair that lands between the two
    # thresholds — confirms it's genuinely the AI call, not the string
    # ratio, that produces the match.
    ai_client = _FakeAIClient(
        responses=[_all_relevant_response(2), _same_posting_response({0}, 1)]
    )

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.status == AggregationRunStatus.COMPLETED
    assert run.matches_created == 1
    assert len(ai_client.calls) == 2  # proves the fallback call actually happened

    matches = (await db_session.execute(select(JobPostingMatch))).scalars().all()
    assert len(matches) == 1


async def test_dedup_ai_fallback_declines_when_ai_says_different(db_session, organization, monkeypatch):
    """Same borderline similarity score as the test above, but the AI
    fallback judges them as genuinely different roles — confirms the
    fallback isn't a rubber stamp and two separate JobPosting rows are kept,
    with no JobPostingMatch created."""
    canonical = _raw("adzuna", "aa-7", "SOC Analyst I", "Zeta Security", "Pune")
    duplicate = _raw("reed", "rr-7", "Security Operations Center Analyst", "Omega Security", "Pune")
    connector_results = {
        "adzuna": ConnectorResult(postings=[canonical], request_count=1, status="success"),
        "reed": ConnectorResult(postings=[duplicate], request_count=1, status="success"),
    }
    ai_client = _FakeAIClient(
        responses=[_all_relevant_response(2), _same_posting_response(set(), 1)]
    )

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.matches_created == 0
    matches = (await db_session.execute(select(JobPostingMatch))).scalars().all()
    assert len(matches) == 0
    postings = (
        await db_session.execute(
            select(JobPosting).where(JobPosting.organization_id == organization.id)
        )
    ).scalars().all()
    assert len(postings) == 2


async def test_dedup_ai_fallback_not_triggered_for_clearly_different_postings(
    db_session, organization, monkeypatch
):
    """Postings with a low string-similarity score across all of
    title/company/location (< the AI-fallback threshold) must never trigger
    an AI dedup call at all — only the relevance-filter call should happen.
    Bounds AI cost/latency; also guards against the fallback silently
    becoming the primary mechanism.

    Note: identical company/location alone (even with wildly different
    titles) is NOT enough to land below the fallback threshold — measured
    directly, "SOC Analyst" vs "Payroll Coordinator" at the *same* company/
    location still scores ~0.74 (the shared company/location substrings
    dominate a short normalized string), correctly landing in the gray zone
    for an AI judgment rather than being silently treated as unrelated. This
    test uses postings that differ on all three fields to get a genuinely
    low score."""
    posting_a = _raw("adzuna", "aa-8", "SOC Analyst", "Theta Security", "Chennai")
    posting_b = _raw("reed", "rr-8", "Payroll Coordinator", "Nimbus Logistics", "Remote")
    connector_results = {
        "adzuna": ConnectorResult(postings=[posting_a], request_count=1, status="success"),
        "reed": ConnectorResult(postings=[posting_b], request_count=1, status="success"),
    }
    ai_client = _FakeAIClient(response_text=_all_relevant_response(2))

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.matches_created == 0
    assert len(ai_client.calls) == 1  # relevance filter only — no dedup fallback call


async def test_run_aggregation_updates_the_queued_run_not_a_new_one(db_session, organization, monkeypatch):
    """Regression test for a real bug caught only by a live end-to-end run
    against an actual Celery worker (mocking `.delay()` to a no-op, as the
    API-level tests do, can never exercise this): the manual-trigger route
    pre-creates a QUEUED `AggregationRun` row via `queue_run()` so the 202
    response has something to reference, then hands the task to Celery.
    `run_aggregation` must be given that row's id (`run_id=`) and update
    THAT row — passing no `run_id` (the bug's actual former behavior)
    silently created a second, disconnected row instead, leaving the
    original permanently stuck at `queued`."""
    posting = _raw("adzuna", "aa-9", "Application Security Engineer", "Sigma Corp")
    connector_results = {"adzuna": ConnectorResult(postings=[posting], request_count=1, status="success")}
    ai_client = _FakeAIClient(response_text=_all_relevant_response(1))

    async def _fake_fetch_all(keywords, db, sources=None):
        return connector_results

    # Patch BEFORE constructing AggregationService — __init__ captures
    # get_ai_client()'s return value once, so patching after construction
    # would leave the real (unconfigured) AnthropicClient in place.
    monkeypatch.setattr("modules.placements.aggregation_service.fetch_all", _fake_fetch_all)
    monkeypatch.setattr("modules.placements.aggregation_service.get_ai_client", lambda: ai_client)

    service = AggregationService(db_session)
    queued_run = await service.queue_run(triggered_by="manual:test-user")
    assert queued_run.status == AggregationRunStatus.QUEUED

    completed_run = await service.run_aggregation(triggered_by="manual:test-user", run_id=queued_run.id)

    assert completed_run.id == queued_run.id  # the SAME row, not a new one
    assert completed_run.status == AggregationRunStatus.COMPLETED
    assert completed_run.postings_created == 1

    all_runs = (await db_session.execute(select(AggregationRun))).scalars().all()
    assert len(all_runs) == 1  # exactly one row total — no orphaned second run


async def test_ai_unavailable_aborts_run_with_zero_writes(db_session, organization, monkeypatch):
    posting = _raw("adzuna", "aa-5", "Security Engineer", "Epsilon Ltd")
    connector_results = {"adzuna": ConnectorResult(postings=[posting], request_count=1, status="success")}
    ai_client = _FakeAIClient(unavailable=True)

    run = await _run(monkeypatch, db_session, connector_results, ai_client)

    assert run.status == AggregationRunStatus.SKIPPED_NO_AI
    postings = (
        await db_session.execute(
            select(JobPosting).where(JobPosting.organization_id == organization.id)
        )
    ).scalars().all()
    assert len(postings) == 0
