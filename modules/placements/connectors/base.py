"""
Shared interface every job-board connector implements — the same
"one interface, one concrete implementation per provider" pattern
`packages/ai/client.py` uses for LLM providers (an ABC-equivalent contract
plus one module per provider, selected by the caller rather than a dynamic
plugin-discovery mechanism, since this repo has no such mechanism
elsewhere).

A connector is a plain module (not a class) exposing one async function:

    async def fetch_postings(keywords: list[str], db: AsyncSession) -> ConnectorResult

`db` is passed through so budget-constrained connectors (Adzuna, Jooble) can
read their own call history via `AggregationRunSourceRepository.
sum_request_count(...)` before deciding whether to call out at all —
connectors that don't need it (Reed, Arbeitnow) simply ignore the parameter.

Every connector MUST:
  - never raise — any failure (missing credentials, HTTP error, malformed
    response) is caught internally, logged, and results in `[]` for that
    keyword/call, not a propagated exception. `modules/placements/
    connectors/__init__.py::fetch_all` adds a second, defensive layer of
    exception-catching around each connector call, but connectors should
    not rely on that as their primary safety net.
  - skip cleanly (log a clear "not configured" message, return `[]`
    immediately, make zero HTTP calls) when its required credential(s) are
    unset — never treat a missing API key as an error.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawPosting:
    source: str
    external_id: str
    title: str
    company: str
    location: str | None
    remote: bool
    salary_min: float | None
    salary_max: float | None
    description: str
    posted_at: datetime | None
    source_url: str


@dataclass
class ConnectorResult:
    """What a connector hands back to `aggregation_service.py`, which writes
    it straight into one `AggregationRunSource` row. `status` is one of
    "success" | "skipped_no_credentials" | "skipped_budget" | "error"."""

    postings: list[RawPosting]
    request_count: int
    status: str
    error_message: str | None = None


class _Throttle:
    """Per-connector-instance last-call-timestamp gate. Deliberately a
    simple in-process `asyncio.sleep`, not a distributed/Redis-backed rate
    limiter — sufficient at this pipeline's actual call volume (single-digit
    HTTP calls per hourly run, per source) and this repo has no existing
    distributed-rate-limiter precedent to reuse. Documented here as a
    conscious simplification, not an oversight."""

    def __init__(self, min_interval_seconds: float):
        self.min_interval_seconds = min_interval_seconds
        self._last_call: float | None = None

    async def wait(self) -> None:
        if self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_call = time.monotonic()
