"""
Research: what the official sources say, retrieved with the date, kept as a cache.

Sources (all official, all read through their own public feeds / APIs; nothing is scraped and no link a user types is
ever fetched):
- CISA Known Exploited Vulnerabilities catalogue (JSON)      cisa_kev
- CISA advisories feed (RSS)                                  cisa_advisory
- NIST National Vulnerability Database, one CVE at a time     nvd

Everything fetched is untrusted text. It is stored as data, scanned for wording that looks like an instruction to an AI,
and only ever handed to a model inside a clearly marked data block (see studio.py). If a source can't be reached the
refresh records that; it never invents a result.
"""

import json
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from modules.placements.connectors.sources import plain_text
from modules.social_media.models import ResearchItem, SocialSettings

logger = get_logger(__name__)

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
ADVISORY_URL = "https://www.cisa.gov/cybersecurity-advisories/all.xml"
NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
ALLOWED_HOSTS = {"www.cisa.gov", "services.nvd.nist.gov"}
USER_AGENT = "erpx-social-research/1.0 (+https://erp.pentrix.in)"
TIMEOUT = 25.0
MAX_BYTES = 6_000_000

SOURCE_LABELS = {"cisa_kev": "CISA Known Exploited Vulnerabilities", "cisa_advisory": "CISA advisories", "nvd": "NIST NVD"}
# A source is read at most this often (the feeds change a few times a day); `force` skips the wait.
MIN_INTERVAL = timedelta(hours=6)
NVD_CACHE = timedelta(hours=24)
KEV_RECENT_DAYS = 45
KEV_LIMIT = 40
ADVISORY_LIMIT = 30

CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

# Wording that is addressed to an AI or tries to trigger an action. Such text is only ever data; this flags it.
_INJECTION = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?)"
    r"|system\s+prompt|you\s+are\s+now\b|new\s+instructions?\s*:|\bas\s+an?\s+(ai|language\s+model)\b"
    r"|(publish|post|approve|send|reply|dm|message)\s+(this|it|that|the\s+following)\s+(now|immediately|without)"
    r"|do\s+not\s+(tell|inform|ask)\s+the\s+(user|admin)|<\s*/?\s*(script|iframe|system|assistant)\b",
    re.IGNORECASE,
)


class SourceUnavailable(Exception):
    """The source couldn't be read (network, rate limit, bad response). The message is safe to show."""


@dataclass
class Found:
    source: str
    external_id: str
    url: str
    title: str
    summary: str | None = None
    published_at: datetime | None = None
    severity: str | None = None
    cve_ids: list[str] = field(default_factory=list)
    facts: dict = field(default_factory=dict)


def injection_flags(*texts: str | None) -> list[str]:
    """Reasons a piece of fetched text looks like an instruction rather than information (empty if it doesn't)."""
    for text in texts:
        if text and _INJECTION.search(text):
            return ["Contains wording that looks like an instruction to an AI. It is treated only as data."]
    return []


def severity_band(score: float | None) -> str | None:
    if score is None:
        return None
    return "critical" if score >= 9.0 else "high" if score >= 7.0 else "medium" if score >= 4.0 else "low"


# ---------------- fetching ----------------


async def _get(url: str, params: dict | None = None) -> bytes:
    host = urlparse(url).hostname or ""
    if host not in ALLOWED_HOSTS or not url.startswith("https://"):
        raise SourceUnavailable("That address is not one of the official research sources.")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
            async with client.stream("GET", url, params=params) as response:
                if response.status_code == 429:
                    raise SourceUnavailable("The source is rate limiting requests right now. Try again later.")
                if response.status_code != 200:
                    raise SourceUnavailable(f"The source answered with status {response.status_code}.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise SourceUnavailable("The source's answer was larger than expected and was ignored.")
                return bytes(body)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"The source could not be reached ({type(exc).__name__}).") from None


# ---------------- parsing (pure) ----------------


def _utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_kev(data: dict, now: datetime | None = None) -> list[Found]:
    """Entries CISA added to the Known Exploited Vulnerabilities catalogue recently (newest first)."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=KEV_RECENT_DAYS)
    found: list[Found] = []
    for entry in data.get("vulnerabilities") or []:
        cve = str(entry.get("cveID") or "").upper()
        added = _utc(entry.get("dateAdded"))
        if not CVE_RE.fullmatch(cve) or added is None or added < cutoff:
            continue
        name = " ".join(str(entry.get("vulnerabilityName") or cve).split())
        found.append(
            Found(
                source="cisa_kev",
                external_id=cve,
                url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={cve}",
                title=f"{cve}: {name}"[:400],
                summary=plain_text(str(entry.get("shortDescription") or "")),
                published_at=added,
                cve_ids=[cve],
                facts={
                    "kev": True,
                    "vendor": entry.get("vendorProject"),
                    "product": entry.get("product"),
                    "date_added": entry.get("dateAdded"),
                    "due_date": entry.get("dueDate"),
                    "known_ransomware_use": entry.get("knownRansomwareCampaignUse"),
                    "required_action": plain_text(str(entry.get("requiredAction") or ""))
                },
            )
        )
        if len(found) >= KEV_LIMIT:
            break
    return found


def parse_advisories(xml_bytes: bytes) -> list[Found]:
    """The newest items of CISA's advisories feed. XML with a DOCTYPE or entity declaration is refused outright."""
    head = xml_bytes[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in head:
        raise SourceUnavailable("The advisories feed was in an unexpected format and was ignored.")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        raise SourceUnavailable("The advisories feed could not be read.") from None
    found: list[Found] = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        title = " ".join((item.findtext("title") or "").split())
        if not title or not link.startswith("https://www.cisa.gov/"):
            continue
        description = item.findtext("description") or ""
        published = None
        raw_date = item.findtext("pubDate")
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published = None
        text = plain_text(description) or ""
        score = None
        match = re.search(r"\bv[34]\s+(\d{1,2}(?:\.\d)?)\b", text)
        if match:
            score = float(match.group(1))
        cves = sorted({c.upper() for c in CVE_RE.findall(f"{title} {text}")})[:10]
        found.append(
            Found(
                source="cisa_advisory",
                external_id=link.removeprefix("https://www.cisa.gov/").rstrip("/")[:255],
                url=link[:600],
                title=title[:400],
                summary=text[:600] or None,
                published_at=published,
                severity=severity_band(score),
                cve_ids=cves,
                facts={"cvss_v3_listed": score} if score is not None else {},
            )
        )
        if len(found) >= ADVISORY_LIMIT:
            break
    return found


def parse_nvd(data: dict, cve_id: str) -> Found | None:
    """One CVE's record from the National Vulnerability Database (None when NVD has no such CVE)."""
    vulnerabilities = data.get("vulnerabilities") or []
    if not vulnerabilities:
        return None
    cve = vulnerabilities[0].get("cve") or {}
    if str(cve.get("id", "")).upper() != cve_id.upper():
        return None
    description = next((d.get("value") for d in cve.get("descriptions", []) if d.get("lang") == "en"), "") or ""
    score = vector = None
    severity = None
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV40", "cvssMetricV2"):
        metrics = (cve.get("metrics") or {}).get(key)
        if metrics:
            cvss = metrics[0].get("cvssData") or {}
            score = cvss.get("baseScore")
            vector = cvss.get("vectorString")
            severity = (cvss.get("baseSeverity") or metrics[0].get("baseSeverity") or "").lower() or None
            break
    cwes = sorted(
        {
            d.get("value")
            for w in cve.get("weaknesses", [])
            for d in w.get("description", [])
            if str(d.get("value", "")).startswith("CWE-")
        }
    )
    kev = bool(cve.get("cisaExploitAdd"))
    return Found(
        source="nvd",
        external_id=cve_id.upper(),
        url=f"https://nvd.nist.gov/vuln/detail/{cve_id.upper()}",
        title=f"{cve_id.upper()} (NVD)",
        summary=plain_text(description),
        published_at=_utc(cve.get("published")),
        severity=severity,
        cve_ids=[cve_id.upper()],
        facts={
            "cvss_score": score,
            "cvss_vector": vector,
            "vuln_status": cve.get("vulnStatus"),
            "last_modified": cve.get("lastModified"),
            "cwes": cwes,
            "kev": kev,
            "kev_date_added": cve.get("cisaExploitAdd"),
        },
    )


# ---------------- the cache ----------------


class ResearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _upsert(self, organization_id: uuid.UUID, item: Found, now: datetime) -> tuple[ResearchItem, bool]:
        row = (
            await self.db.execute(
                select(ResearchItem).where(
                    ResearchItem.organization_id == organization_id,
                    ResearchItem.source == item.source,
                    ResearchItem.external_id == item.external_id,
                )
            )
        ).scalar_one_or_none()
        created = row is None
        if row is None:
            row = ResearchItem(organization_id=organization_id, source=item.source, external_id=item.external_id, status="new")
            self.db.add(row)
        row.url = item.url
        row.title = item.title
        row.summary = item.summary
        row.published_at = item.published_at
        row.retrieved_at = now
        row.severity = item.severity
        row.cve_ids = item.cve_ids
        row.facts = item.facts
        row.flags = injection_flags(item.title, item.summary, str(item.facts.get("required_action") or ""))
        await self.db.flush()
        return row, created

    async def refresh(self, organization_id: uuid.UUID, settings: SocialSettings, force: bool = False) -> list[dict]:
        """Read the CISA sources (each at most every few hours unless forced). One result per source: what happened."""
        now = datetime.now(timezone.utc)
        state = dict(settings.research_state or {})
        results: list[dict] = []
        for source, url in (("cisa_kev", KEV_URL), ("cisa_advisory", ADVISORY_URL)):
            last = _utc((state.get(source) or {}).get("last_fetch_at"))
            if not force and last and now - last < MIN_INTERVAL and (state.get(source) or {}).get("ok"):
                results.append({"source": source, "label": SOURCE_LABELS[source], "skipped": True, "ok": True, "new": 0, "count": (state[source] or {}).get("count", 0), "error": None})
                continue
            try:
                body = await _get(url)
                if source == "cisa_kev":
                    try:
                        items = parse_kev(json.loads(body), now)
                    except ValueError:
                        raise SourceUnavailable("The catalogue could not be read.") from None
                else:
                    items = parse_advisories(body)
                new = 0
                for item in items:
                    _row, created = await self._upsert(organization_id, item, now)
                    new += int(created)
                state[source] = {"last_fetch_at": now.isoformat(), "ok": True, "error": None, "count": len(items)}
                results.append({"source": source, "label": SOURCE_LABELS[source], "skipped": False, "ok": True, "new": new, "count": len(items), "error": None})
            except SourceUnavailable as exc:
                logger.warning("social_research_unavailable", source=source, reason=str(exc))
                previous = state.get(source) or {}
                state[source] = {**previous, "last_attempt_at": now.isoformat(), "ok": False, "error": str(exc)}
                results.append({"source": source, "label": SOURCE_LABELS[source], "skipped": False, "ok": False, "new": 0, "count": previous.get("count", 0), "error": str(exc)})
        settings.research_state = state
        await self.db.flush()
        return results

    async def lookup_cve(self, organization_id: uuid.UUID, cve_id: str, force: bool = False) -> ResearchItem | None:
        """The NVD record for a CVE (cached for a day). None means NVD has no such CVE; SourceUnavailable means unknown."""
        cve_id = cve_id.upper()
        if not CVE_RE.fullmatch(cve_id):
            return None
        now = datetime.now(timezone.utc)
        cached = (
            await self.db.execute(
                select(ResearchItem).where(
                    ResearchItem.organization_id == organization_id,
                    ResearchItem.source == "nvd",
                    ResearchItem.external_id == cve_id,
                )
            )
        ).scalar_one_or_none()
        if cached and not force and now - cached.retrieved_at < NVD_CACHE:
            return cached
        try:
            data = json.loads(await _get(NVD_URL, {"cveId": cve_id}))
        except ValueError:
            raise SourceUnavailable("NVD's answer could not be read.") from None
        found = parse_nvd(data, cve_id)
        if found is None:
            return None
        row, _ = await self._upsert(organization_id, found, now)
        return row

    async def list(
        self, organization_id: uuid.UUID, source: str | None, status: str | None, q: str | None, skip: int, limit: int
    ) -> tuple[list[ResearchItem], int]:
        conditions = [ResearchItem.organization_id == organization_id, ResearchItem.source != "nvd"]
        if source:
            conditions.append(ResearchItem.source == source)
        if status:
            conditions.append(ResearchItem.status == status)
        else:
            conditions.append(ResearchItem.status != "dismissed")
        if q:
            conditions.append(ResearchItem.title.ilike(f"%{q.strip()[:100]}%"))
        total = (await self.db.execute(select(func.count()).select_from(ResearchItem).where(*conditions))).scalar_one()
        rows = (
            await self.db.execute(
                select(ResearchItem)
                .where(*conditions)
                .order_by(ResearchItem.published_at.desc().nullslast(), ResearchItem.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars()
        return list(rows), total

    async def get(self, organization_id: uuid.UUID, item_id: uuid.UUID) -> ResearchItem | None:
        return (
            await self.db.execute(
                select(ResearchItem).where(ResearchItem.id == item_id, ResearchItem.organization_id == organization_id)
            )
        ).scalar_one_or_none()
