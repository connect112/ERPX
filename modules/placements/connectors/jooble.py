"""
Jooble connector — https://jooble.org/api/about

Auth: API key embedded in the URL path, `POST https://jooble.org/api/{key}`.

**Confirmed (Jooble's own help-center docs): the free plan is a 500-request
LIFETIME cap per key — not a recurring daily/monthly quota.** A literal
hourly cadence would exhaust the entire free-tier allocation in under 3
weeks even with zero pagination. Because of this, Jooble is deliberately
*not* wired into the hourly `placements.run_aggregation` beat entry —
it runs on its own weekly `placements.run_jooble_aggregation` schedule
instead (see `apps/api/app/core/celery_app.py`), and this connector
additionally enforces a hard lifetime call-budget guard (default 450,
`JOOBLE_LIFETIME_CALL_BUDGET`, leaving ~50 calls of headroom for manual
triggers) that degrades to a clean no-op once spent, rather than erroring.

One combined multi-keyword call per invocation (not one call per keyword,
unlike Adzuna) — deliberately minimizes lifetime-budget burn given how tight
it is.
"""

from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging_config import get_logger
from modules.placements.connectors.base import ConnectorResult, RawPosting
from modules.placements.repository import AggregationRunSourceRepository

logger = get_logger(__name__)


def _to_raw_posting(job: dict) -> RawPosting | None:
    try:
        updated = job.get("updated")
        posted_at = None
        if updated:
            try:
                posted_at = datetime.fromisoformat(updated)
            except ValueError:
                posted_at = None
        salary = job.get("salary") or ""
        description = job.get("snippet", "")
        if salary:
            description = f"{description}\n\nSalary: {salary}"
        return RawPosting(
            source="jooble",
            external_id=str(job["id"]),
            title=job["title"],
            company=job.get("company") or "Unknown",
            location=job.get("location"),
            remote=False,
            salary_min=None,
            salary_max=None,
            description=description,
            posted_at=posted_at,
            source_url=job["link"],
        )
    except (KeyError, TypeError):
        logger.warning("jooble_posting_malformed", job_id=job.get("id"))
        return None


async def fetch_postings(keywords: list[str], db: AsyncSession) -> ConnectorResult:
    if not settings.JOOBLE_API_KEY:
        logger.info("jooble_connector_skipped", reason="missing_credentials")
        return ConnectorResult(postings=[], request_count=0, status="skipped_no_credentials")

    lifetime_calls = await AggregationRunSourceRepository(db).sum_request_count("jooble")
    if lifetime_calls >= settings.JOOBLE_LIFETIME_CALL_BUDGET:
        logger.info(
            "jooble_lifetime_budget_exhausted", lifetime_calls=lifetime_calls,
            budget=settings.JOOBLE_LIFETIME_CALL_BUDGET,
        )
        return ConnectorResult(postings=[], request_count=0, status="skipped_budget")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://jooble.org/api/{settings.JOOBLE_API_KEY}",
                json={
                    "keywords": ", ".join(keywords),
                    "location": settings.JOOBLE_DEFAULT_LOCATION,
                    "ResultOnPage": 20,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("jooble_request_failed", status_code=exc.response.status_code)
        return ConnectorResult(
            postings=[], request_count=1, status="error",
            error_message=f"Jooble returned status {exc.response.status_code}.",
        )
    except httpx.TransportError:
        logger.warning("jooble_request_failed", reason="transport_error")
        return ConnectorResult(postings=[], request_count=1, status="error", error_message="Transport error.")
    except Exception:
        logger.exception("jooble_connector_unexpected_error")
        return ConnectorResult(postings=[], request_count=1, status="error", error_message="Unexpected error.")

    postings = [p for p in (_to_raw_posting(job) for job in data.get("jobs", [])) if p is not None]
    return ConnectorResult(postings=postings, request_count=1, status="success")
