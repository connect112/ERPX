"""
Automated checks on a post. They flag problems for a person to decide on; they never approve or publish anything.

What is checked: CVE identifiers and the claims made about them (exists in NVD, CVSS score, "actively exploited" against
CISA's Known Exploited Vulnerabilities list), sources (official? dated? still current?), claims we never make, course
details that must come from verified data, the design limits, and the post's place in the content history.
A check that can't be completed says so (the source was unreachable); it never passes silently.

Warnings produced here carry a code starting `chk_`, so a re-run replaces them and leaves hand-written ones alone.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media import render
from modules.social_media.history import HistoryService
from modules.social_media.models import PostStatus, ResearchItem, SocialPost, SocialSettings, VerificationStatus
from modules.social_media.research import CVE_RE, ResearchService, SourceUnavailable

MAX_CVE_LOOKUPS = 8
STALE_AFTER = timedelta(days=30)
OFFICIAL_HOSTS = (
    "cisa.gov",
    "nvd.nist.gov",
    "nist.gov",
    "cve.org",
    "cert-in.org.in",
    "mitre.org",
    "owasp.org",
    "ncsc.gov.uk",
    "us-cert.gov",
)

_BLOCK = [
    (re.compile(r"\b(guarantee[ds]?|assured|100\s*%)\s+(a\s+)?(job|jobs|placement|placements|salary|offer)", re.I), "promises a job, placement or salary outcome"),
    (re.compile(r"\b(job|placement|salary)\s+guarantee", re.I), "promises a job, placement or salary outcome"),
    (re.compile(r"\b(go(ing)?\s+viral|guaranteed\s+(followers|reach|likes|growth))\b", re.I), "promises viral reach or follower growth"),
]
_WARN = [
    (re.compile(r"(₹\s?\d|\brs\.?\s?\d|\binr\s?\d|\b\d+(\.\d+)?\s?(lpa|lakhs?)\b)", re.I), "mentions an amount of money (fees and salaries must come from verified data)"),
    (re.compile(r"\b(course\s+fees?|fees?\s+(is|are|start)|batch(es)?\s+(start|begin|open)|starts?\s+on\s+\d|limited\s+seats?|admissions?\s+(open|close))\b", re.I), "states course fees, batches or schedules (check them against verified course data)"),
    (re.compile(r"\b(our\s+students?\s+(got|cracked|landed|placed)|alumni\s+(work|got|placed)|testimonial)", re.I), "makes a claim about students or alumni (use only genuine, evidenced ones)"),
]
_EXPLOIT = re.compile(r"\b(actively\s+exploited|exploited\s+in\s+the\s+wild|being\s+exploited|zero[- ]day|0[- ]day)\b", re.I)
# "CVSS 9.8", "CVSS score of 10.0", "CVSS v3.1 base score: 7.5" (a version like v3.1 or 3.1 is skipped, never read as the score)
_CVSS = re.compile(
    r"\bcvss(?:\s*:?\s*(?:v\d(?:\.\d)?|\d\.\d(?=\s+(?:base\s+)?score)))?\s*(?:base\s*)?(?:score\s*)?(?:of|is|:|=)?\s*(\d{1,2}(?:\.\d)?)\b",
    re.I,
)
_CRITICAL = re.compile(r"\bcritical\b", re.I)


def post_text(content: dict) -> str:
    parts = [content.get("headline"), content.get("caption"), content.get("cta"), content.get("thumbnail_text")]
    parts += list(content.get("hooks") or [])
    for slide in content.get("slides") or []:
        parts += [slide.get("heading"), slide.get("body")]
    return "\n".join(str(p) for p in parts if p)


def _warning(severity: str, code: str, message: str) -> dict:
    return {"severity": severity, "code": code, "message": message}


def _official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def run_checks(
    db: AsyncSession, organization_id: uuid.UUID, post: SocialPost, settings: SocialSettings, now: datetime | None = None
) -> tuple[list[dict], str | None, dict]:
    """(warnings, a new verification status or None, evidence). Evidence is what was looked up and when."""
    now = now or datetime.now(timezone.utc)
    content = post.content or {}
    text = post_text(content)
    warnings: list[dict] = []
    conflict = False
    evidence: dict = {"checked_at": now.isoformat(), "cves": {}}

    # ---- claims we never make ----
    for pattern, what in _BLOCK:
        match = pattern.search(text)
        if match:
            warnings.append(_warning("blocking", "chk_prohibited", f'"{match.group(0)}" {what}. This is never allowed.'))
    seen_warn: set[str] = set()
    for pattern, what in _WARN:
        match = pattern.search(text)
        if match and what not in seen_warn:
            seen_warn.add(what)
            warnings.append(_warning("warning", "chk_claim", f'"{match.group(0).strip()}" {what}.'))

    # ---- CVE facts ----
    cves = list(dict.fromkeys(c.upper() for c in CVE_RE.findall(text)))
    research = ResearchService(db)
    # CVEs that an official source the post is built on cites itself (a brand-new CVE may not be in NVD yet).
    cited: dict[str, str] = {}
    item_ids = []
    for raw in (post.generation or {}).get("research_items", []):
        try:
            item_ids.append(uuid.UUID(raw))
        except ValueError:
            continue
    if item_ids:
        rows = await db.execute(select(ResearchItem).where(ResearchItem.organization_id == organization_id, ResearchItem.id.in_(item_ids)))
        for item in rows.scalars():
            for cve in item.cve_ids or []:
                cited.setdefault(cve.upper(), item.title)
    facts: dict[str, dict] = {}
    for cve in cves[:MAX_CVE_LOOKUPS]:
        try:
            item = await research.lookup_cve(organization_id, cve)
        except SourceUnavailable as exc:
            warnings.append(_warning("warning", "chk_cve_unreachable", f"{cve} could not be checked against NVD ({exc}). Check it by hand."))
            evidence["cves"][cve] = {"checked": False}
            continue
        if item is None:
            evidence["cves"][cve] = {"checked": True, "found": False}
            if cve in cited:
                warnings.append(
                    _warning(
                        "warning",
                        "chk_cve_not_in_nvd_yet",
                        f'{cve} is cited by the source "{cited[cve]}" but is not in NVD yet (new CVEs can take a while), so its score and details could not be cross-checked.',
                    )
                )
            else:
                conflict = True
                warnings.append(_warning("blocking", "chk_cve_unknown", f"{cve} was not found in the National Vulnerability Database. Check the identifier."))
            continue
        facts[cve] = item.facts or {}
        facts[cve]["_severity"] = item.severity
        evidence["cves"][cve] = {
            "checked": True,
            "found": True,
            "cvss": facts[cve].get("cvss_score"),
            "severity": item.severity,
            "kev": bool(facts[cve].get("kev")),
            "status": facts[cve].get("vuln_status"),
            "retrieved_at": item.retrieved_at.isoformat(),
        }
        if str(facts[cve].get("vuln_status", "")).lower() == "rejected":
            conflict = True
            warnings.append(_warning("blocking", "chk_cve_rejected", f"{cve} has been rejected in NVD, so it is not a valid vulnerability."))
    if len(cves) > MAX_CVE_LOOKUPS:
        warnings.append(_warning("info", "chk_cve_many", f"Only the first {MAX_CVE_LOOKUPS} CVE identifiers were checked."))

    # ---- claims about those CVEs ----
    stated = [float(m) for m in _CVSS.findall(text)]
    scores = {c: f["cvss_score"] for c, f in facts.items() if f.get("cvss_score") is not None}
    if stated and scores:
        if len(scores) == 1 or len(set(scores.values())) == 1:
            actual = next(iter(scores.values()))
            for value in stated:
                if abs(value - float(actual)) > 0.05:
                    conflict = True
                    warnings.append(_warning("blocking", "chk_cvss_mismatch", f"The post says CVSS {value:g}, but NVD lists {actual}."))
                    break
        elif not any(any(abs(v - float(a)) <= 0.05 for a in scores.values()) for v in stated):
            warnings.append(_warning("warning", "chk_cvss_unmatched", "The CVSS score in the post matches none of the CVEs' scores in NVD."))
    if _CRITICAL.search(text) and scores and not any(float(s) >= 9.0 for s in scores.values()):
        warnings.append(_warning("warning", "chk_severity_wording", f'The post says "critical", but NVD lists {", ".join(str(s) for s in scores.values())}.'))
    exploit = _EXPLOIT.search(text)
    if exploit:
        if not cves:
            warnings.append(_warning("warning", "chk_exploited_claim", f'"{exploit.group(0)}" is claimed without naming a CVE or a source. Add one or remove the claim.'))
        elif facts and not any(f.get("kev") for f in facts.values()):
            warnings.append(_warning("warning", "chk_exploited_claim", f'"{exploit.group(0)}" is claimed, but none of the CVEs is in CISA\'s Known Exploited Vulnerabilities catalogue.'))

    # ---- sources ----
    factual = bool(cves or exploit or post.time_sensitive or post.sources or post.verification_status != VerificationStatus.NOT_REQUIRED.value)
    if factual and not any(_official(s.get("url", "")) for s in post.sources or []):
        warnings.append(_warning("warning", "chk_no_official_source", "No official source (CISA, NVD, NIST, CERT-In, MITRE, OWASP) is listed for this post's facts."))
    dates = [d for d in (_parse_date(s.get("published_at")) for s in post.sources or []) if d]
    stale = False
    if post.time_sensitive:
        if not dates:
            warnings.append(_warning("warning", "chk_undated_sources", "This is time-sensitive but its sources have no publication date."))
        elif now - max(dates) > STALE_AFTER:
            stale = True
            warnings.append(_warning("warning", "chk_stale", f"The newest source is older than {STALE_AFTER.days} days, so this may be out of date."))
    for item_id in (post.generation or {}).get("research_items", []):
        flagged = (post.generation or {}).get("flagged_items", {}).get(item_id)
        if flagged:
            warnings.append(_warning("warning", "chk_source_injection", f'The source "{flagged}" contained instruction-like wording. It was used only as data.'))

    # ---- design limits ----
    rules = settings.design_rules or {}
    headline_words = len((content.get("headline") or "").split())
    if rules.get("max_headline_words") and headline_words > rules["max_headline_words"]:
        warnings.append(_warning("warning", "chk_headline_long", f"The headline has {headline_words} words; the design rules allow {rules['max_headline_words']}."))
    cover = len(content.get("thumbnail_text") or "")
    if rules.get("max_cover_text_chars") and cover > rules["max_cover_text_chars"]:
        warnings.append(_warning("warning", "chk_cover_text_long", f"The cover text has {cover} characters; the design rules allow {rules['max_cover_text_chars']}."))

    # ---- artwork ----
    art = post.artwork or {}
    design = post.design or {}
    brand = settings.brand or {}
    if not art.get("files"):
        warnings.append(_warning("info", "chk_no_artwork", "No artwork has been made for this post yet."))
    else:
        problems = [p for f in art["files"] for p in f.get("validation", {}).get("problems", [])]
        if problems:
            warnings.append(_warning("blocking", "chk_artwork_invalid", f"The artwork doesn't meet the design rules: {problems[0]}"))
        pillar = next((p["label"] for p in settings.pillars or [] if p["key"] == post.pillar), None)
        now_fp = render.current_fingerprint(post.format, content, design, post.title, pillar, brand)
        if now_fp is None or now_fp != art.get("fingerprint"):
            warnings.append(_warning("blocking", "chk_artwork_stale", "The words or design have changed since the artwork was made. Make the artwork again so it matches."))
        if not brand.get("logo_key"):
            warnings.append(_warning("warning", "chk_no_logo", "No approved logo is uploaded, so the artwork has no logo."))
        if art.get("synthetic_background"):
            warnings.append(_warning("info", "chk_synthetic_background", "The background is AI-generated. It is decoration, not a real photograph, so don't present it as evidence."))

    # ---- a Reel concept is not a video ----
    if post.format == "reel" and not content.get("asset_key"):
        warnings.append(_warning("info", "chk_reel_script_only", "This is a script and storyboard only. No video exists yet, so it can't be published as a Reel."))

    # ---- history ----
    history = HistoryService(db)
    warnings.extend(history.findings(post, await history.recent(organization_id, exclude_id=post.id)))

    # ---- what the verification status should become ----
    current = post.verification_status
    new_status: str | None = None
    if conflict:
        new_status = VerificationStatus.CONFLICTING.value
    elif stale:
        new_status = VerificationStatus.OUTDATED.value
    elif current == VerificationStatus.NOT_REQUIRED.value and factual:
        new_status = VerificationStatus.UNVERIFIED.value
    elif current in (VerificationStatus.CONFLICTING.value, VerificationStatus.OUTDATED.value):
        new_status = VerificationStatus.UNVERIFIED.value  # the problem found earlier is gone; a person verifies again
    if new_status == current:
        new_status = None
    return warnings, new_status, evidence


def merge_warnings(existing: list[dict], system: list[dict]) -> list[dict]:
    """Hand-written warnings stay; every `chk_` warning is replaced by this run's."""
    kept = [w for w in existing if not str(w.get("code") or "").startswith("chk_")]
    return kept + system


async def check_and_store(db: AsyncSession, organization_id: uuid.UUID, post: SocialPost, settings: SocialSettings) -> None:
    """Run the checks and save the outcome on the post: warnings, verification status and the evidence looked up.
    Where a draft's CVEs were found in NVD, the NVD record is added to its sources. An approved post whose claims
    turn out to conflict, be outdated or carry a blocking warning has its approval withdrawn."""
    warnings, new_status, evidence = await run_checks(db, organization_id, post, settings)
    post.warnings = merge_warnings(post.warnings or [], warnings)
    if new_status:
        post.verification_status = new_status
    generation = dict(post.generation or {})
    generation["last_check"] = evidence
    post.generation = generation
    editable = post.status in (PostStatus.DRAFT.value, PostStatus.REVIEW.value)
    if editable:
        sources = list(post.sources or [])
        for cve, info in evidence["cves"].items():
            url = f"https://nvd.nist.gov/vuln/detail/{cve}"
            if info.get("found") and not any(src.get("url") == url for src in sources) and len(sources) < 20:
                sources.append({"url": url, "title": f"{cve} (NVD)", "published_at": None, "retrieved_at": info.get("retrieved_at")})
        post.sources = sources
    blocking = any(w.get("severity") == "blocking" for w in warnings)
    if post.status == PostStatus.APPROVED.value and (
        new_status in (VerificationStatus.CONFLICTING.value, VerificationStatus.OUTDATED.value) or blocking
    ):
        post.status = PostStatus.DRAFT.value
        post.approved_by_user_id = None
        post.approved_at = None
        post.approved_content_hash = None
        post.warnings = [
            *post.warnings,
            _warning("warning", "chk_approval_withdrawn", "The approval was withdrawn because a check found this post's claims conflict, are out of date or break a rule."),
        ]
    await db.flush()
