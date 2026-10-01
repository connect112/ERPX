"""
Arbeitnow connector — https://www.arbeitnow.com/api/job-board-api

No API key required (confirmed — this connector never skips on missing
credentials, unlike the other three). Paginated via `links.next` in the
response; capped at `ARBEITNOW_MAX_PAGES` (default 3) to bound run time,
since this API has no keyword-filtering query param documented — filtering
to cybersecurity-relevant roles happens client-side (a simple substring
match here, as a cheap pre-filter) and, more rigorously, in the shared
relevance-filter stage in `aggregation_service.py`.

No documented rate limit was found — throttled defensively like Reed, not
presented as an evidence-based Arbeitnow-specific limit.
"""

import html
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging_config import get_logger
from modules.placements.connectors.base import ConnectorResult, RawPosting, _Throttle

logger = get_logger(__name__)

_URL = "https://www.arbeitnow.com/api/job-board-api"
_throttle = _Throttle(min_interval_seconds=1.0)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """Stdlib-only HTML stripping (no new dependency) — Arbeitnow's
    `description` field is HTML, and (confirmed against the real live API,
    not assumed) HTML-ENTITY-ENCODED on top of that: the raw JSON value is
    literally `&lt;div class=&quot;...&quot;&gt;...`, not `<div class="...">`.
    Unescape entities FIRST, then strip tags — the reverse order silently
    no-ops the tag-stripping regex (there are no literal `<`/`>` characters
    to match until after unescaping), leaving raw HTML markup in the stored
    description. A hand-written test fixture using already-literal HTML
    (not entity-encoded) passed either order, which is exactly how this
    escaped the connector's own unit test — caught only by pulling a real
    live posting."""
    # Two unescape passes, not one: the first reveals the literal HTML tags
    # (needed before the tag-stripping regex can match anything at all —
    # see the docstring above). But the revealed HTML is real HTML written
    # by the original job posting's author, which can itself contain
    # ordinary entities like `&nbsp;` — confirmed against real live data,
    # where "...Identity:&amp;nbsp;..." unescapes once to
    # "...Identity:&nbsp;..." (still an unresolved entity) and needs a
    # second pass to become an actual non-breaking-space character.
    unescaped = html.unescape(html.unescape(text))
    stripped = _TAG_RE.sub(" ", unescaped)
    # Replacing each removed tag with a space (rather than "") avoids
    # accidentally gluing adjacent words together, but leaves doubled-up
    # whitespace wherever a tag sat next to real whitespace in the source —
    # collapse that down for a readable stored description. `\s` here also
    # normalizes the U+00A0 non-breaking space `&nbsp;` unescapes to, since
    # Python's `re` treats it as whitespace for `str` patterns.
    return _WHITESPACE_RE.sub(" ", stripped).strip()


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def _get(client: httpx.AsyncClient, url: str) -> dict:
    await _throttle.wait()
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


def _to_raw_posting(job: dict) -> RawPosting | None:
    try:
        created_at = job.get("created_at")
        posted_at = (
            datetime.fromtimestamp(created_at, tz=timezone.utc) if created_at is not None else None
        )
        return RawPosting(
            source="arbeitnow",
            external_id=job["slug"],
            title=job["title"],
            company=job.get("company_name") or "Unknown",
            location=job.get("location"),
            remote=bool(job.get("remote", False)),
            salary_min=None,
            salary_max=None,
            description=_strip_html(job.get("description", "")),
            posted_at=posted_at,
            source_url=job["url"],
        )
    except (KeyError, TypeError):
        logger.warning("arbeitnow_posting_malformed", slug=job.get("slug"))
        return None


def _is_keyword_relevant(job: dict, keywords: list[str]) -> bool:
    haystack = f"{job.get('title', '')} {' '.join(job.get('tags', []))}".lower()
    return any(kw.lower() in haystack for kw in keywords)


async def fetch_postings(keywords: list[str], db: AsyncSession) -> ConnectorResult:
    postings: list[RawPosting] = []
    request_count = 0

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url: str | None = _URL
            pages_fetched = 0
            while url and pages_fetched < settings.ARBEITNOW_MAX_PAGES:
                try:
                    data = await _get(client, url)
                    request_count += 1
                    pages_fetched += 1
                except httpx.HTTPStatusError as exc:
                    request_count += 1
                    logger.warning("arbeitnow_request_failed", status_code=exc.response.status_code)
                    break
                except httpx.TransportError:
                    request_count += 1
                    logger.warning("arbeitnow_request_failed", reason="transport_error")
                    break

                for job in data.get("data", []):
                    if not _is_keyword_relevant(job, keywords):
                        continue
                    raw = _to_raw_posting(job)
                    if raw is not None:
                        postings.append(raw)

                url = (data.get("links") or {}).get("next")
    except Exception:
        logger.exception("arbeitnow_connector_unexpected_error")
        return ConnectorResult(
            postings=postings, request_count=request_count, status="error",
            error_message="Unexpected error while calling Arbeitnow.",
        )

    return ConnectorResult(postings=postings, request_count=request_count, status="success")
