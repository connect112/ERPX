"""
Content history: what has been posted before, so the studio and the checks can spot near-duplicates, repeated hooks,
overused hashtags and an unbalanced mix of topics. Everything here is computed from this organisation's own posts.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media.models import PostStatus, SocialPost, SocialSettings

HISTORY = 40  # how many recent posts are compared
NEAR_DUPLICATE = 0.6  # Jaccard similarity of 5-word shingles
HASHTAG_WINDOW = 10
HASHTAG_LIMIT = 6  # a tag already in this many of the last 10 posts is overused
TOPIC_WINDOW = 20


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def shingles(text: str, size: int = 5) -> set[str]:
    words = _norm(text).split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def similarity(a: str, b: str) -> float:
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


@dataclass
class PillarBalance:
    key: str
    label: str
    target: int  # percent
    actual: int  # percent of the recent posts
    recent: int


class HistoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def recent(self, organization_id: uuid.UUID, exclude_id: uuid.UUID | None = None, limit: int = HISTORY) -> list[SocialPost]:
        conditions = [SocialPost.organization_id == organization_id, SocialPost.status != PostStatus.CANCELLED.value]
        if exclude_id:
            conditions.append(SocialPost.id != exclude_id)
        rows = await self.db.execute(select(SocialPost).where(*conditions).order_by(SocialPost.created_at.desc()).limit(limit))
        return list(rows.scalars())

    @staticmethod
    def findings(post: SocialPost, others: list[SocialPost]) -> list[dict]:
        """Warnings about this post against the others (each with a code starting `chk_`)."""
        out: list[dict] = []
        content = post.content or {}
        caption = content.get("caption") or ""
        for other in others:
            score = similarity(caption, (other.content or {}).get("caption") or "")
            if score >= NEAR_DUPLICATE:
                out.append(
                    {
                        "severity": "warning",
                        "code": "chk_near_duplicate",
                        "message": f'The caption is very similar ({round(score * 100)}%) to the post "{other.title}".',
                    }
                )
                break
        hooks = {_norm(h) for h in content.get("hooks") or [] if h} | ({_norm(content["headline"])} if content.get("headline") else set())
        for other in others:
            oc = other.content or {}
            used = {_norm(h) for h in oc.get("hooks") or [] if h} | ({_norm(oc["headline"])} if oc.get("headline") else set())
            shared = hooks & used
            if shared:
                out.append(
                    {
                        "severity": "warning",
                        "code": "chk_repeated_hook",
                        "message": f'A hook or headline repeats one already used in "{other.title}".',
                    }
                )
                break
        window = others[:HASHTAG_WINDOW]
        overused = []
        for tag in content.get("hashtags") or []:
            count = sum(1 for o in window if tag.lower() in {t.lower() for t in (o.content or {}).get("hashtags") or []})
            if count >= HASHTAG_LIMIT:
                overused.append(f"#{tag}")
        if overused:
            out.append(
                {
                    "severity": "warning",
                    "code": "chk_hashtag_overuse",
                    "message": f"Used in {HASHTAG_LIMIT} or more of the last {HASHTAG_WINDOW} posts: {', '.join(overused[:5])}.",
                }
            )
        return out

    async def balance(self, organization_id: uuid.UUID, settings: SocialSettings) -> list[PillarBalance]:
        recent = (await self.recent(organization_id, limit=TOPIC_WINDOW))
        counts: dict[str, int] = {}
        for post in recent:
            if post.pillar:
                counts[post.pillar] = counts.get(post.pillar, 0) + 1
        total = sum(counts.values())
        return [
            PillarBalance(
                key=p["key"],
                label=p["label"],
                target=int(p.get("share", 0)),
                actual=round(100 * counts.get(p["key"], 0) / total) if total else 0,
                recent=counts.get(p["key"], 0),
            )
            for p in settings.pillars
            if p.get("enabled")
        ]

    @staticmethod
    def suggestions(balance: list[PillarBalance], posts_considered: int) -> list[str]:
        """Which topics to cover next: enabled pillars furthest below their target share (needs some history first)."""
        if posts_considered < 5:
            return []
        gaps = sorted(((b.target - b.actual, b) for b in balance if b.target - b.actual >= 5), key=lambda t: -t[0])
        return [f'"{b.label}" is at {b.actual}% of recent posts against a {b.target}% target.' for _gap, b in gaps[:3]]
