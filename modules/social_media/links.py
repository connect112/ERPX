"""
Tracked links: a short address for a bio, caption, story or message that counts opens and sends the visitor on with UTM
parameters, so the website's own analytics can see where visits came from.

What it does and doesn't know:
- it counts opens per day. It records no address, device or visitor, so it cannot say which person opened it
- common link-preview robots are not counted, but a count can still include some automated visits
- an open is not an enquiry and an enquiry is not an enrolment; nothing here links a click to a person
- the destination is typed by staff with permission; the redirect never accepts a destination from the address it was opened with
"""

import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from modules.marketing.campaigns.models import Campaign
from modules.social_media.models import LinkDay, SocialPost, TrackedLink

PLACEMENTS = ("bio", "post", "story", "dm", "comment", "other")
UTM_SOURCE = "instagram"
UTM_MEDIUM = "social"
_BOT = re.compile(r"bot|crawl|spider|preview|facebookexternalhit|slurp|headless|monitor|curl|python-requests", re.I)
_SLUG = re.compile(r"[^a-z0-9_-]+")


def is_robot(user_agent: str | None) -> bool:
    return bool(user_agent and _BOT.search(user_agent))


def slug(text: str, fallback: str = "link") -> str:
    cleaned = _SLUG.sub("-", text.strip().lower()).strip("-")[:100]
    return cleaned or fallback


def clean_destination(url: str) -> str:
    """https only, no embedded credentials, a real host, a sensible length."""
    url = (url or "").strip()
    if len(url) > 500:
        raise ValidationError("The destination address is too long (500 characters at most).")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ValidationError("The destination must be a secure https:// address.")
    if parts.username or parts.password:
        raise ValidationError("The destination can't contain a username or password.")
    host = parts.hostname or ""
    if "." not in host:
        raise ValidationError("The destination needs a real website address.")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def target_url(link: TrackedLink) -> str:
    """The destination with UTM parameters added. Parameters already on the destination are kept, never overwritten."""
    parts = urlsplit(link.destination)
    existing = parse_qsl(parts.query, keep_blank_values=True)
    have = {k for k, _ in existing}
    added = [("utm_source", UTM_SOURCE), ("utm_medium", UTM_MEDIUM), ("utm_campaign", link.utm_campaign)]
    content = link.utm_content or link.placement
    added.append(("utm_content", content))
    query = urlencode(existing + [(k, v) for k, v in added if k not in have])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def short_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/api/v1/social-media/l/{token}"


class LinkService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _check_refs(self, organization_id: uuid.UUID, post_id: uuid.UUID | None, campaign_id: uuid.UUID | None) -> None:
        if post_id is not None and (await self.db.execute(select(SocialPost.id).where(SocialPost.id == post_id, SocialPost.organization_id == organization_id))).scalar_one_or_none() is None:
            raise ValidationError("That post doesn't exist.")
        if campaign_id is not None and (await self.db.execute(select(Campaign.id).where(Campaign.id == campaign_id, Campaign.organization_id == organization_id))).scalar_one_or_none() is None:
            raise ValidationError("That campaign doesn't exist.")

    async def create(self, organization_id: uuid.UUID, user_id: uuid.UUID, data: dict) -> TrackedLink:
        if data["placement"] not in PLACEMENTS:
            raise ValidationError("Choose where the link will be used.")
        await self._check_refs(organization_id, data.get("post_id"), data.get("marketing_campaign_id"))
        name = data["name"].strip()
        link = TrackedLink(
            organization_id=organization_id, created_by_user_id=user_id, name=name, token=secrets.token_urlsafe(7), destination=clean_destination(data["destination"]),
            placement=data["placement"], post_id=data.get("post_id"), course_label=(data.get("course_label") or "").strip() or None,
            marketing_campaign_id=data.get("marketing_campaign_id"), utm_campaign=slug(data.get("utm_campaign") or name), utm_content=slug(data["utm_content"]) if data.get("utm_content") else None,
        )
        self.db.add(link)
        await self.db.flush()
        return link

    async def get(self, organization_id: uuid.UUID, link_id: uuid.UUID) -> TrackedLink:
        row = (await self.db.execute(select(TrackedLink).where(TrackedLink.id == link_id, TrackedLink.organization_id == organization_id))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Link not found.")
        return row

    async def update(self, organization_id: uuid.UUID, link_id: uuid.UUID, data: dict) -> TrackedLink:
        link = await self.get(organization_id, link_id)
        if data.get("name") is not None:
            link.name = data["name"].strip()
        if data.get("is_active") is not None:
            link.is_active = data["is_active"]
        if "course_label" in data:
            link.course_label = (data["course_label"] or "").strip() or None
        await self.db.flush()
        return link

    async def stats(self, organization_id: uuid.UUID, today: date | None = None) -> list[dict]:
        today = today or datetime.now(timezone.utc).date()
        links = list((await self.db.execute(select(TrackedLink).where(TrackedLink.organization_id == organization_id).order_by(TrackedLink.created_at.desc()))).scalars())
        if not links:
            return []
        rows = (await self.db.execute(select(LinkDay.link_id, LinkDay.day, LinkDay.clicks).where(LinkDay.link_id.in_([l.id for l in links])))).all()
        out = []
        for link in links:
            mine = [(d, c) for lid, d, c in rows if lid == link.id]
            recent = sum(c for d, c in mine if (today - d).days < 28)
            out.append({"link": link, "clicks_total": sum(c for _, c in mine), "clicks_28d": recent, "last_click_day": max((d for d, _ in mine), default=None)})
        return out

    async def record_click(self, token: str, now: datetime | None = None) -> str | None:
        """Count one open and return where to send the visitor, or None when the link is unknown or paused."""
        now = now or datetime.now(timezone.utc)
        link = (await self.db.execute(select(TrackedLink).where(TrackedLink.token == token, TrackedLink.is_active.is_(True)))).scalar_one_or_none()
        if link is None:
            return None
        stmt = pg_insert(LinkDay).values(id=uuid.uuid4(), link_id=link.id, day=now.date(), clicks=1, created_at=now, updated_at=now)
        await self.db.execute(stmt.on_conflict_do_update(constraint="uq_social_link_day", set_={"clicks": LinkDay.clicks + 1, "updated_at": now}))
        return target_url(link)

    async def clicks_between(self, organization_id: uuid.UUID, start: date, end: date) -> dict[uuid.UUID, int]:
        rows = (
            await self.db.execute(
                select(LinkDay.link_id, func.sum(LinkDay.clicks))
                .join(TrackedLink, TrackedLink.id == LinkDay.link_id)
                .where(TrackedLink.organization_id == organization_id, LinkDay.day >= start, LinkDay.day <= end)
                .group_by(LinkDay.link_id)
            )
        ).all()
        return {lid: int(total) for lid, total in rows}


def recent_window(days: int, today: date | None = None) -> tuple[date, date]:
    today = today or datetime.now(timezone.utc).date()
    return today - timedelta(days=days - 1), today
