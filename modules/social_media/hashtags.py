"""
Hashtags: what the profile's own posts show, kept apart from what an AI suggests.

- measured: for each hashtag the profile has used, the reach of the posts that used it against the posts that didn't, with how many
  posts are behind each side. These are observations from this profile only. Posts that share a hashtag also share other things
  (topic, time, format), so a difference is never called an effect, and nothing is said below three posts on each side.
- suggested: the Studio's AI hashtags are labelled as suggestions (not measured) wherever they appear.
- trending: Meta offers hashtag search only in a restricted form and gives no popularity counts, and ERPX does not scrape, so there is
  no measured trend figure. The screen says so instead of showing an invented one.
"""

import unicodedata
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media import metrics as M
from modules.social_media.models import IgMedia, MediaMetric

INSTAGRAM_LIMIT = 30
MANY = 15
MIN_EACH_SIDE = 3
OVERUSED_SHARE = 0.7
RECENT = 10

TREND_UNAVAILABLE = (
    "Measured hashtag trends aren't available. Meta's hashtag search is restricted and doesn't return how popular a hashtag is, "
    "and ERPX doesn't scrape Instagram. Hashtags the Studio suggests are suggestions, not measurements."
)


def _tag_char(ch: str) -> bool:
    # Letters and numbers of any script, underscores, and the combining marks that Hindi and other scripts need inside a word.
    return ch == "_" or ch.isalnum() or unicodedata.category(ch) in ("Mn", "Mc")


def extract(caption: str | None) -> list[str]:
    """Distinct hashtags in a caption, lower case, in the order first used. A '#' inside a word ('c#', 'me@x.com#a') isn't a tag."""
    text = caption or ""
    seen: dict[str, None] = {}
    i = 0
    while i < len(text):
        if text[i] == "#" and (i == 0 or not (_tag_char(text[i - 1]) or text[i - 1] == "#")):
            j = i + 1
            while j < len(text) and _tag_char(text[j]):
                j += 1
            tag = text[i + 1 : j]
            if len(tag) >= 2 and (tag[0].isalnum()) and len(tag) <= 100:
                seen.setdefault(tag.lower(), None)
            i = j
        else:
            i += 1
    return list(seen)


async def report(db: AsyncSession, organization_id: uuid.UUID) -> dict:
    media = list((await db.execute(select(IgMedia).where(IgMedia.organization_id == organization_id).order_by(IgMedia.posted_at.desc().nullslast()))).scalars())
    reach = {
        r.media_external_id: r.value
        for r in (await db.execute(select(MediaMetric).where(MediaMetric.organization_id == organization_id, MediaMetric.metric == "reach"))).scalars()
        if r.value is not None
    }
    rows = [{"id": m.external_id, "tags": extract(m.caption), "reach": reach.get(m.external_id)} for m in media]
    overall, overall_n = M.typical([r["reach"] for r in rows])
    uses = Counter(tag for r in rows for tag in r["tags"])
    recent = rows[:RECENT]
    items = []
    for tag, count in uses.most_common():
        with_tag = [r["reach"] for r in rows if tag in r["tags"]]
        without = [r["reach"] for r in rows if tag not in r["tags"]]
        median_with, n_with = M.typical(with_tag)
        median_without, n_without = M.typical(without)
        enough = n_with >= MIN_EACH_SIDE and n_without >= MIN_EACH_SIDE
        items.append(
            {
                "tag": tag, "posts": count, "median_reach_with": median_with, "posts_with_reach": n_with, "median_reach_without": median_without, "posts_without_reach": n_without,
                "comparison": (
                    None if not enough else ("higher" if median_with > median_without else "lower" if median_with < median_without else "same")
                ),
                "caution": None if enough else f"Needs at least {MIN_EACH_SIDE} posts with and {MIN_EACH_SIDE} without a figure to compare; this has {n_with} and {n_without}.",
                "overused": len(recent) >= 5 and sum(1 for r in recent if tag in r["tags"]) / len(recent) >= OVERUSED_SHARE,
                "kind": M.OBSERVED,
            }
        )
    sets = Counter(tuple(sorted(r["tags"])) for r in rows if len(r["tags"]) >= 3)
    per_post = [len(r["tags"]) for r in rows]
    return {
        "posts_read": len(rows), "typical_reach": overall, "typical_reach_posts": overall_n,
        "items": items,
        "average_per_post": (sum(per_post) / len(per_post)) if per_post else None,
        "too_many": sum(1 for n in per_post if n > INSTAGRAM_LIMIT), "many": sum(1 for n in per_post if n > MANY),
        "repeated_sets": [{"tags": list(s), "posts": n} for s, n in sets.most_common(3) if n >= 3],
        "label": "Measured from this profile's own posts",
        "limitations": [
            "Only the 25 most recent posts are read, and only posts with a readable reach figure are compared.",
            "Posts that share a hashtag also share other things (topic, format, time), so a difference doesn't show the hashtag caused it.",
        ],
        "trend": {"available": False, "reason": TREND_UNAVAILABLE},
    }
