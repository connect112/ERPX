"""
Connectors to outside job sources. Each one asks the source's own public feed or API (never a scraped web page) and
returns plain `JobItem`s; matching, saving and showing them is job_feed.py's job.

Sources:
- remotive   remote jobs, free feed (https://remotive.com/api-documentation). Their terms: link back to their page,
             name them as the source, and fetch at most ~4 times a day.
- arbeitnow  jobs from Germany / Europe and remote, free feed (https://www.arbeitnow.com/api/job-board-api).
- adzuna     India job search API, many job boards in one; needs ADZUNA_APP_ID / ADZUNA_APP_KEY.
- jooble     job search API across many boards; needs JOOBLE_API_KEY.
- greenhouse, lever  the public job boards companies publish through these hiring systems (one request per
             company, listed in the settings); direct from the employer, no key.
"""

import asyncio
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
    # The whole description (up to 20,000 characters) when the source gives it: read for experience, never stored.
    details: str | None = None


class SourceError(Exception):
    """A source could not be read; the message is shown to admins."""


SOURCES: dict[str, str] = {
    "adzuna": "Adzuna (India)",
    "greenhouse": "Company career pages (Greenhouse)",
    "lever": "Company career pages (Lever)",
    "remotive": "Remotive (remote jobs)",
    "arbeitnow": "Arbeitnow (Europe and remote)",
    "jooble": "Jooble",
}
# Hours between two reads of the same source (Remotive asks for at most four a day; Adzuna's free plan has a request
# allowance, so it is read twice a day).
MIN_INTERVAL_HOURS = {"remotive": 5.5, "arbeitnow": 1.0, "adzuna": 11.5, "jooble": 3.0, "greenhouse": 3.0, "lever": 3.0}

# Company career boards read by default (all verified to exist and to list jobs in India or remote). Admins can edit.
DEFAULT_BOARDS: dict[str, list[str]] = {
    "greenhouse": [
        "okta", "datadog", "elastic", "mongodb", "databricks", "twilio", "gitlab", "rubrik", "zscaler", "newrelic",
        "sumologic", "abnormalsecurity", "netskope", "guidepoint", "jfrog", "cloudflare", "stripe", "payoneer",
        "fivetran", "toast", "roblox", "singlestore", "yugabyte", "thoughtworks", "mixpanel", "airbnb", "coinbase",
    ],
    "lever": ["cred", "meesho", "paytm", "nium", "zeta", "pocketfm"],
}

# Searches sent to the search-style sources (they return the newest matches for each).
SEARCH_QUERIES = [
    "cyber security",
    "information security",
    "security analyst",
    "soc analyst",
    "devsecops",
    "devops engineer",
    "cloud engineer",
    "site reliability engineer",
    "penetration tester",
    "cloud security",
    "network security engineer",
    "linux administrator",
    "ethical hacker",
    "vapt",
    "digital forensics",
    "grc analyst",
    "network engineer",
    "cyber security fresher",
    "devops intern",
]
ADZUNA_PAGES = 3  # 50 results a page
# Adzuna allows a limited number of requests a minute.
REQUEST_GAP_SECONDS = 2.5


def is_configured(source: str) -> bool:
    if source == "adzuna":
        return bool(settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY)
    if source == "jooble":
        return bool(settings.JOOBLE_API_KEY)
    return source in SOURCES


def plain_text(value: str | None, limit: int = MAX_SUMMARY_CHARS) -> str | None:
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
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."


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


async def fetch_remotive(client: httpx.AsyncClient, options: dict) -> list[JobItem]:
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


async def fetch_arbeitnow(client: httpx.AsyncClient, options: dict) -> list[JobItem]:
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


async def fetch_adzuna(client: httpx.AsyncClient, options: dict) -> list[JobItem]:
    items: dict[str, JobItem] = {}
    calls = 0
    for query in SEARCH_QUERIES:
        for page in range(1, ADZUNA_PAGES + 1):
            if calls:
                await asyncio.sleep(REQUEST_GAP_SECONDS)
            calls += 1
            data = await _get_json(
                client,
                f"https://api.adzuna.com/v1/api/jobs/in/search/{page}",
                params={
                    "app_id": settings.ADZUNA_APP_ID,
                    "app_key": settings.ADZUNA_APP_KEY,
                    "results_per_page": 50,
                    "what": query,
                    "sort_by": "date",
                    "max_days_old": 30,
                    "content-type": "application/json",
                },
            )
            results = data.get("results", [])
            for job in results:
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
            if len(results) < 50:
                break  # no further pages for this search
    return list(items.values())


async def fetch_jooble(client: httpx.AsyncClient, options: dict) -> list[JobItem]:
    items: dict[str, JobItem] = {}
    for number, query in enumerate(SEARCH_QUERIES):
        if number:
            await asyncio.sleep(REQUEST_GAP_SECONDS)
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


async def _read_boards(client: httpx.AsyncClient, tokens: list[str], read_one) -> list[JobItem]:
    """Read many company boards a few at a time. A board that doesn't exist (or is down) is skipped; only when every
    board fails is it reported as an error."""
    gate = asyncio.Semaphore(4)
    failures = 0

    async def one(token: str) -> list[JobItem]:
        nonlocal failures
        async with gate:
            try:
                return await read_one(client, token)
            except SourceError:
                failures += 1
                return []

    batches = await asyncio.gather(*(one(t) for t in tokens))
    if tokens and failures == len(tokens):
        raise SourceError("none of the company career pages could be read")
    return [item for batch in batches for item in batch]


def _company_name(token: str) -> str:
    return token.replace("-", " ").replace("_", " ").title()


async def fetch_greenhouse(client: httpx.AsyncClient, options: dict) -> list[JobItem]:
    async def read_one(client: httpx.AsyncClient, token: str) -> list[JobItem]:
        data = await _get_json(client, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
        items = []
        for job in data.get("jobs", []):
            url = _clean_url(job.get("absolute_url"))
            if not url or not job.get("title") or not job.get("id"):
                continue
            where = (job.get("location") or {}).get("name") or None
            items.append(
                JobItem(
                    source="greenhouse",
                    external_id=f"{token}:{job['id']}",
                    title=str(job["title"])[:255],
                    company=str(job.get("company_name") or _company_name(token))[:255],
                    url=url,
                    location=where,
                    remote=bool(where and "remote" in where.lower()),
                    posted_at=_when(job.get("first_published") or job.get("updated_at")),
                )
            )
        return items

    return await _read_boards(client, list(options.get("greenhouse") or []), read_one)


def _lever_details(job: dict) -> str | None:
    """Lever's own plain-text description plus its requirement lists (where years of experience are usually said)."""
    parts = [str(job.get("descriptionPlain") or "")]
    for block in job.get("lists") or []:
        parts.append(f"{block.get('text') or ''}\n{plain_text(block.get('content'), 20_000) or ''}")
    parts.append(str(job.get("additionalPlain") or ""))
    text = "\n".join(p for p in parts if p.strip()).strip()
    return text[:20_000] or None


async def fetch_lever(client: httpx.AsyncClient, options: dict) -> list[JobItem]:
    async def read_one(client: httpx.AsyncClient, token: str) -> list[JobItem]:
        data = await _get_json(client, f"https://api.lever.co/v0/postings/{token}", params={"mode": "json"})
        items = []
        for job in data if isinstance(data, list) else []:
            url = _clean_url(job.get("hostedUrl"))
            if not url or not job.get("text") or not job.get("id"):
                continue
            cats = job.get("categories") or {}
            where = cats.get("location") or None
            kind = cats.get("commitment")
            items.append(
                JobItem(
                    source="lever",
                    external_id=f"{token}:{job['id']}",
                    title=str(job["text"])[:255],
                    company=_company_name(token),
                    url=url,
                    location=where,
                    remote=(job.get("workplaceType") == "remote") or bool(where and "remote" in where.lower()),
                    job_type=(str(kind).lower().replace(" ", "_") if kind else None),
                    summary=plain_text(job.get("descriptionPlain")),
                    details=_lever_details(job),
                    tags=[t for t in (cats.get("team"),) if t],
                    posted_at=_when(job.get("createdAt") and int(job["createdAt"]) // 1000),
                )
            )
        return items

    return await _read_boards(client, list(options.get("lever") or []), read_one)


async def enrich_greenhouse(client: httpx.AsyncClient, items: list[JobItem]) -> None:
    """Greenhouse's list has no descriptions: read each wanted job's own page of data for its full text."""
    gate = asyncio.Semaphore(5)

    async def one(item: JobItem) -> None:
        token, _, job_id = item.external_id.partition(":")
        async with gate:
            try:
                data = await _get_json(client, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}")
            except SourceError:
                return
        content = html.unescape(str(data.get("content") or ""))  # the HTML arrives escaped
        item.details = plain_text(content, 20_000)
        item.summary = plain_text(content)

    await asyncio.gather(*(one(item) for item in items))


# Sources whose list has too little text: after filtering, fetch the full text of the jobs that are kept.
ENRICHERS = {"greenhouse": enrich_greenhouse}

FETCHERS = {
    "adzuna": fetch_adzuna,
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
    "jooble": fetch_jooble,
}


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "ERPX-Placements/1.0 (+https://erp.pentrix.in)"},
        follow_redirects=True,
    )
