"""
Connectors to outside job sources. Each one asks the source's own public feed or API (never a scraped web page) and
returns plain `JobItem`s; matching, saving and showing them is job_feed.py's job.

Sources:
- remotive   remote jobs, free feed (https://remotive.com/api-documentation). Their terms: link back to their page,
             name them as the source, and fetch at most ~4 times a day.
- arbeitnow  jobs from Germany / Europe and remote, free feed (https://www.arbeitnow.com/api/job-board-api).
- adzuna     India job search API, many job boards in one; needs ADZUNA_APP_ID / ADZUNA_APP_KEY.
- jooble     job search API across many boards; needs JOOBLE_API_KEY.
"""

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.core.config import settings

REQUEST_TIMEOUT = 25.0
MAX_SUMMARY_CHARS = 600


@dataclass
class JobItem:
    source: str
    external_id: str
    title: str
    company: str
    url: str
    location: str | None = None
    remote: bool = False
    job_type: str | None = None
    summary: str | None = None
    tags: list[str] = field(default_factory=list)
    posted_at: datetime | None = None
    salary_text: str | None = None


class SourceError(Exception):
    """A source could not be read; the message is shown to admins."""


# name -> (label, needs a key from settings)
SOURCES: dict[str, str] = {
    "remotive": "Remotive (remote jobs)",
    "arbeitnow": "Arbeitnow (Europe and remote)",
    "adzuna": "Adzuna (India)",
    "jooble": "Jooble",
}
# Hours between two reads of the same source (Remotive asks for at most four a day).
MIN_INTERVAL_HOURS = {"remotive": 5.5, "arbeitnow": 1.0, "adzuna": 3.0, "jooble": 3.0}
# Searches sent to the search-style sources (they return the newest matches for each).
SEARCH_QUERIES = [
    "cyber security fresher",
    "cyber security intern",
    "devsecops",
    "devops fresher",
    "devops intern",
    "cloud engineer fresher",
    "soc analyst",
    "security analyst trainee",
]


def is_configured(source: str) -> bool:
    if source == "adzuna":
        return bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)
    if source == "jooble":
        return bool(settings.JOOBLE_API_KEY)
    return source in SOURCES


def plain_text(value: str | None) -> str | None:
    """Job descriptions come as HTML: the first few hundred characters of readable text."""
    if not value:
        return None
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", value, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</li>|</div>", "\n", text, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    if not text:
        return None
    return text if len(text) <= MAX_SUMMARY_CHARS else text[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "..."


def _when(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _clean_url(value) -> str | None:
    url = str(value or "").strip()
    return url if url.lower().startswith(("http://", "https://")) else None


async def _get_json(client: httpx.AsyncClient, url: str, **kwargs):
    try:
        response = await client.get(url, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise SourceError(f"the site answered with status {exc.response.status_code}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SourceError("the site could not be reached or sent something unreadable") from exc


async def fetch_remotive(client: httpx.AsyncClient) -> list[JobItem]:
    data = await _get_json(client, "https://remotive.com/api/remote-jobs")
    items = []
    for job in data.get("jobs", []):
        url = _clean_url(job.get("url"))
        if not url or not job.get("title"):
            continue
        items.append(
            JobItem(
                source="remotive",
                external_id=str(job.get("id")),
                title=str(job["title"])[:255],
                company=str(job.get("company_name") or "Unknown")[:255],
                url=url,
                location=(job.get("candidate_required_location") or None),
                remote=True,
                job_type=job.get("job_type") or None,
                summary=plain_text(job.get("description")),
                tags=[str(t) for t in (job.get("tags") or [])][:12] + ([job["category"]] if job.get("category") else []),
                posted_at=_when(job.get("publication_date")),
                salary_text=(job.get("salary") or None),
            )
        )
    return items


async def fetch_arbeitnow(client: httpx.AsyncClient) -> list[JobItem]:
    items = []
    for page in (1, 2, 3):
        data = await _get_json(client, "https://www.arbeitnow.com/api/job-board-api", params={"page": page})
        rows = data.get("data", [])
        for job in rows:
            url = _clean_url(job.get("url"))
            if not url or not job.get("title"):
                continue
            kinds = job.get("job_types") or []
            items.append(
                JobItem(
                    source="arbeitnow",
                    external_id=str(job.get("slug")),
                    title=str(job["title"])[:255],
                    company=str(job.get("company_name") or "Unknown")[:255],
                    url=url,
                    location=(job.get("location") or None),
                    remote=bool(job.get("remote")),
                    job_type=(str(kinds[0]).lower().replace(" ", "_") if kinds else None),
                    summary=plain_text(job.get("description")),
                    tags=[str(t) for t in (job.get("tags") or [])][:12],
                    posted_at=_when(job.get("created_at")),
                )
            )
        if not rows or not data.get("links", {}).get("next"):
            break
    return items


async def fetch_adzuna(client: httpx.AsyncClient) -> list[JobItem]:
    items: dict[str, JobItem] = {}
    for query in SEARCH_QUERIES:
        data = await _get_json(
            client,
            "https://api.adzuna.com/v1/api/jobs/in/search/1",
            params={
                "app_id": settings.ADZUNA_APP_ID,
                "app_key": settings.ADZUNA_APP_KEY,
                "results_per_page": 50,
                "what": query,
                "sort_by": "date",
                "content-type": "application/json",
            },
        )
        for job in data.get("results", []):
            url = _clean_url(job.get("redirect_url"))
            if not url or not job.get("title") or not job.get("id"):
                continue
            low, high = job.get("salary_min"), job.get("salary_max")
            salary = f"INR {int(low):,} - {int(high):,}" if low and high else None
            items.setdefault(
                str(job["id"]),
                JobItem(
                    source="adzuna",
                    external_id=str(job["id"]),
                    title=plain_text(str(job["title"])) or "",
                    company=str((job.get("company") or {}).get("display_name") or "Unknown")[:255],
                    url=url,
                    location=(job.get("location") or {}).get("display_name"),
                    job_type=job.get("contract_time") or job.get("contract_type"),
                    summary=plain_text(job.get("description")),
                    posted_at=_when(job.get("created")),
                    salary_text=salary,
                ),
            )
    return list(items.values())


async def fetch_jooble(client: httpx.AsyncClient) -> list[JobItem]:
    items: dict[str, JobItem] = {}
    for query in SEARCH_QUERIES:
        try:
            response = await client.post(
                f"https://jooble.org/api/{settings.JOOBLE_API_KEY}",
                json={"keywords": query, "location": "India", "page": "1"},
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            raise SourceError(f"the site answered with status {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise SourceError("the site could not be reached or sent something unreadable") from exc
        for job in data.get("jobs", []):
            url = _clean_url(job.get("link"))
            if not url or not job.get("title"):
                continue
            key = str(job.get("id") or url)
            items.setdefault(
                key,
                JobItem(
                    source="jooble",
                    external_id=key[:255],
                    title=plain_text(str(job["title"])) or "",
                    company=str(job.get("company") or "Unknown")[:255],
                    url=url,
                    location=job.get("location") or None,
                    job_type=(job.get("type") or None),
                    summary=plain_text(job.get("snippet")),
                    posted_at=_when(job.get("updated")),
                    salary_text=(job.get("salary") or None),
                ),
            )
    return list(items.values())


FETCHERS = {"remotive": fetch_remotive, "arbeitnow": fetch_arbeitnow, "adzuna": fetch_adzuna, "jooble": fetch_jooble}


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "ERPX-Placements/1.0 (+https://erp.pentrix.in)"},
        follow_redirects=True,
    )
