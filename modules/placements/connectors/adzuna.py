"""
Adzuna connector — https://developer.adzuna.com

Auth: `app_id` + `app_key` as query params. No embedding/search-suggestion
endpoints used, just the plain job search endpoint.

Confirmed rate limits (Adzuna's own Terms of Service page): 25 hits/minute,
250/day, 1000/week, 2500/month. This connector throttles to a 2.5s floor
between calls (keeps it under 25/min even at max burst) and additionally
checks a *daily* call budget (default 240, `ADZUNA_DAILY_CALL_BUDGET`)
against `AggregationRunSource.request_count` history before calling, so a
day with multiple manual triggers on top of the hourly schedule can't blow
through the real 250/day cap.

Confirmed attribution requirement (Adzuna's own ToS, not just courtesy):
"Jobs by Adzuna" (min 116x23px) hyperlinked to adzuna.co.uk using Adzuna's
own logo must be displayed alongside any listing sourced from this API —
see `apps/web/src/features/placements/components/adzuna-attribution.tsx`
and its student-portal equivalent, which render this specifically for
`source == "adzuna"` postings, in addition to the generic "via X" badge.
"""

from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging_config import get_logger
from modules.placements.connectors.base import ConnectorResult, RawPosting, _Throttle
from modules.placements.repository import AggregationRunSourceRepository

logger = get_logger(__name__)

_BASE_URL = "https://api.adzuna.com/v1/api"
_throttle = _Throttle(min_interval_seconds=2.5)


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _search_page(client: httpx.AsyncClient, keyword: str) -> list[dict]:
    await _throttle.wait()
    response = await client.get(
        f"{_BASE_URL}/jobs/{settings.ADZUNA_COUNTRY}/search/1",
        params={
            "app_id": settings.ADZUNA_APP_ID,
            "app_key": settings.ADZUNA_APP_KEY,
            "what": keyword,
            "results_per_page": 20,
            "content-type": "application/json",
        },
    )
    response.raise_for_status()
    return response.json().get("results", [])


def _to_raw_posting(job: dict) -> RawPosting | None:
    try:
        created = job.get("created")
        posted_at = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None
        return RawPosting(
            source="adzuna",
            external_id=str(job["id"]),
            title=job["title"],
            company=(job.get("company") or {}).get("display_name", "Unknown"),
            location=(job.get("location") or {}).get("display_name"),
            remote=False,
            salary_min=job.get("salary_min"),
            salary_max=job.get("salary_max"),
            description=job.get("description", ""),
            posted_at=posted_at,
            source_url=job["redirect_url"],
        )
    except (KeyError, TypeError):
        logger.warning("adzuna_posting_malformed", job_id=job.get("id"))
        return None


async def fetch_postings(keywords: list[str], db: AsyncSession) -> ConnectorResult:
    if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
        logger.info("adzuna_connector_skipped", reason="missing_credentials")
        return ConnectorResult(postings=[], request_count=0, status="skipped_no_credentials")

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    calls_today = await AggregationRunSourceRepository(db).sum_request_count(
        "adzuna", since=today_start
    )
    if calls_today >= settings.ADZUNA_DAILY_CALL_BUDGET:
        logger.info(
            "adzuna_daily_budget_exhausted", calls_today=calls_today,
            budget=settings.ADZUNA_DAILY_CALL_BUDGET,
        )
        return ConnectorResult(postings=[], request_count=0, status="skipped_budget")

    postings: list[RawPosting] = []
    request_count = 0
    remaining_budget = settings.ADZUNA_DAILY_CALL_BUDGET - calls_today

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for keyword in keywords:
                if request_count >= remaining_budget:
                    logger.info("adzuna_daily_budget_exhausted_mid_run", keyword_skipped=keyword)
                    break
                try:
                    jobs = await _search_page(client, keyword)
                    request_count += 1
                except httpx.HTTPStatusError as exc:
                    request_count += 1
                    logger.warning(
                        "adzuna_request_failed", keyword=keyword, status_code=exc.response.status_code
                    )
                    continue
                except httpx.TransportError:
                    request_count += 1
                    logger.warning("adzuna_request_failed", keyword=keyword, reason="transport_error")
                    continue

                for job in jobs:
                    raw = _to_raw_posting(job)
                    if raw is not None:
                        postings.append(raw)
    except Exception:
        logger.exception("adzuna_connector_unexpected_error")
        return ConnectorResult(
            postings=postings, request_count=request_count, status="error",
            error_message="Unexpected error while calling Adzuna.",
        )

    return ConnectorResult(postings=postings, request_count=request_count, status="success")
