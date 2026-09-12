"""
Reed connector — https://www.reed.co.uk/developers/Jobseeker

Auth: API key sent as the HTTP Basic auth username, password left blank.

No documented rate limit was found in Reed's current public docs — this
connector still throttles defensively (a flat 1s floor between calls), but
that number is NOT presented as an evidence-based Reed-specific limit the
way Adzuna's and Jooble's are; it's just conservative default behavior.
"""

from datetime import date, datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging_config import get_logger
from modules.placements.connectors.base import ConnectorResult, RawPosting, _Throttle

logger = get_logger(__name__)

_BASE_URL = "https://www.reed.co.uk/api/1.0"
_throttle = _Throttle(min_interval_seconds=1.0)


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _search(client: httpx.AsyncClient, keyword: str) -> list[dict]:
    await _throttle.wait()
    response = await client.get(
        f"{_BASE_URL}/search", params={"keywords": keyword, "resultsToTake": 50}
    )
    response.raise_for_status()
    return response.json().get("results", [])


def _to_raw_posting(job: dict) -> RawPosting | None:
    try:
        posted = job.get("date")
        posted_at = None
        if posted:
            try:
                posted_at = datetime.combine(
                    datetime.strptime(posted, "%d/%m/%Y").date(), datetime.min.time()
                )
            except ValueError:
                posted_at = None
        return RawPosting(
            source="reed",
            external_id=str(job["jobId"]),
            title=job["jobTitle"],
            company=job.get("employerName") or "Unknown",
            location=job.get("locationName"),
            remote=False,
            salary_min=job.get("minimumSalary"),
            salary_max=job.get("maximumSalary"),
            description=job.get("jobDescription", ""),
            posted_at=posted_at,
            source_url=job["jobUrl"],
        )
    except (KeyError, TypeError):
        logger.warning("reed_posting_malformed", job_id=job.get("jobId"))
        return None


async def fetch_postings(keywords: list[str], db: AsyncSession) -> ConnectorResult:
    if not settings.REED_API_KEY:
        logger.info("reed_connector_skipped", reason="missing_credentials")
        return ConnectorResult(postings=[], request_count=0, status="skipped_no_credentials")

    postings: list[RawPosting] = []
    request_count = 0

    try:
        async with httpx.AsyncClient(auth=(settings.REED_API_KEY, ""), timeout=15) as client:
            for keyword in keywords:
                try:
                    jobs = await _search(client, keyword)
                    request_count += 1
                except httpx.HTTPStatusError as exc:
                    request_count += 1
                    logger.warning(
                        "reed_request_failed", keyword=keyword, status_code=exc.response.status_code
                    )
                    continue
                except httpx.TransportError:
                    request_count += 1
                    logger.warning("reed_request_failed", keyword=keyword, reason="transport_error")
                    continue

                for job in jobs:
                    raw = _to_raw_posting(job)
                    if raw is not None:
                        postings.append(raw)
    except Exception:
        logger.exception("reed_connector_unexpected_error")
        return ConnectorResult(
            postings=postings, request_count=request_count, status="error",
            error_message="Unexpected error while calling Reed.",
        )

    return ConnectorResult(postings=postings, request_count=request_count, status="success")
