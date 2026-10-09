"""
The nine-post grid preview: how the next posts will look together on the profile, with an honest list of what is wrong.

It is built from the artwork of planned and published posts known to ERPX. The live Instagram profile isn't readable
until the account is connected (a later phase), so the preview says which posts are missing instead of pretending to
be complete. Each check compares the stored measurements of the renders (dominant colour, brightness, a perceptual
hash, text amount, template, logo position); nothing is guessed from the picture again.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media.history import similarity
from modules.social_media.models import PostStatus, SocialPost, SocialSettings
from packages.storage.client import get_storage_client

GRID = 9
COLOR_CLOSE = 28  # RGB distance below which two neighbouring tiles look the same colour
LUMINANCE_JUMP = 0.55
HASH_CLOSE = 4  # Hamming distance (of 64 bits) below which two pieces of artwork are near-identical


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _distance(a: str, b: str) -> float:
    (r1, g1, b1), (r2, g2, b2) = _rgb(a), _rgb(b)
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _finding(severity: str, code: str, message: str, tiles: list[int]) -> dict:
    return {"severity": severity, "code": code, "message": message, "tiles": tiles}


def neighbours(count: int) -> list[tuple[int, int]]:
    """Pairs of tiles that touch in a 3-column grid (side by side, or one above the other)."""
    pairs = []
    for i in range(count):
        if i % 3 < 2 and i + 1 < count:
            pairs.append((i, i + 1))
        if i + 3 < count:
            pairs.append((i, i + 3))
    return pairs


def analyze(tiles: list[dict], rules: dict, live_available: bool) -> list[dict]:
    """Findings about a list of tiles (position 0 is top-left). Each tile carries `metrics` from its render."""
    findings: list[dict] = []
    if len(tiles) < 2:
        findings.append(_finding("info", "grid_too_small", "There are fewer than two designed posts, so there is nothing to compare yet.", []))
    pairs = neighbours(len(tiles))
    for a, b in pairs:
        ma, mb = tiles[a]["metrics"], tiles[b]["metrics"]
        if _distance(ma["dominant"], mb["dominant"]) < COLOR_CLOSE and ma["template"] == mb["template"]:
            findings.append(_finding("warning", "grid_same_look", "Two neighbouring posts have the same colour and layout, so they will merge into one block.", [a, b]))
        elif abs(ma["luminance"] - mb["luminance"]) > LUMINANCE_JUMP:
            findings.append(_finding("info", "grid_abrupt_change", "A very dark post sits next to a very light one. That is fine now and then, but not everywhere.", [a, b]))
    for start in (0, 3, 6):  # rows
        row = tiles[start : start + 3]
        if len(row) == 3 and len({t["metrics"]["template"] for t in row}) == 1:
            findings.append(_finding("warning", "grid_row_repeat", "A whole row uses the same layout.", list(range(start, start + 3))))
    for col in range(3):  # columns
        column = [tiles[i] for i in (col, col + 3, col + 6) if i < len(tiles)]
        if len(column) == 3 and len({t["metrics"]["template"] for t in column}) == 1:
            findings.append(_finding("warning", "grid_column_repeat", "A whole column uses the same layout.", [col, col + 3, col + 6]))
    templates = [t["metrics"]["template"] for t in tiles]
    if len(tiles) >= 5:
        most = max(set(templates), key=templates.count)
        if templates.count(most) >= 6:
            findings.append(_finding("warning", "grid_uniform", f"{templates.count(most)} of {len(tiles)} posts use the {most} layout. Mix in other formats, screenshots and photographs.", [i for i, t in enumerate(templates) if t == most]))
    for i in range(len(tiles)):
        for j in range(i + 1, len(tiles)):
            hi, hj = tiles[i]["metrics"], tiles[j]["metrics"]
            if hi.get("headline") and hj.get("headline") and similarity(hi["headline"], hj["headline"]) >= 0.6:
                findings.append(_finding("warning", "grid_repeated_headline", "Two posts have almost the same headline.", [i, j]))
            elif _hamming(hi["dhash"], hj["dhash"]) <= HASH_CLOSE and hi["template"] == hj["template"] and _distance(hi["dominant"], hj["dominant"]) < COLOR_CLOSE:
                findings.append(_finding("warning", "grid_repeated_artwork", "Two posts have near-identical artwork.", [i, j]))
    limit = int(rules.get("max_cover_text_chars", 90))
    for i, tile in enumerate(tiles):
        if tile["metrics"]["text_chars"] > limit:
            findings.append(_finding("warning", "grid_text_dense", f"This post has {tile['metrics']['text_chars']} characters of cover text; the design rules allow {limit}.", [i]))
    logos = {t["metrics"].get("logo") for t in tiles}
    if len(tiles) >= 2 and len(logos) > 1:
        findings.append(_finding("warning", "grid_logo_inconsistent", "The logo is missing or in a different place on some posts.", [i for i, t in enumerate(tiles) if t["metrics"].get("logo") != "bottom_left"]))
    sizes = [t["metrics"]["headline_px"] for t in tiles if t["metrics"].get("headline_px")]
    if len(sizes) >= 2 and max(sizes) / min(sizes) > 2.0:
        findings.append(_finding("info", "grid_type_scale", "Headline sizes vary a lot between posts, so the type looks inconsistent in the grid.", []))
    if not live_available:
        findings.append(
            _finding(
                "info",
                "grid_live_unavailable",
                "Your live Instagram profile isn't connected, so posts already on it are not shown and can't be compared. "
                "Whether this batch fits the existing posts can't be judged yet.",
                [],
            )
        )
    return findings


class GridService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage_client()

    async def build(self, organization_id: uuid.UUID, settings: SocialSettings, focus_post_id: uuid.UUID | None = None) -> dict:
        conditions = [
            SocialPost.organization_id == organization_id,
            SocialPost.status != PostStatus.CANCELLED.value,
            SocialPost.artwork["files"].isnot(None),
        ]
        rows = (
            await self.db.execute(
                select(SocialPost).where(*conditions).order_by(func.coalesce(SocialPost.scheduled_at, SocialPost.created_at).desc()).limit(GRID * 3)
            )
        ).scalars()
        posts = [p for p in rows if (p.artwork or {}).get("files")]
        if focus_post_id:
            focus = next((p for p in posts if p.id == focus_post_id), None)
            if focus is None:
                focus = (
                    await self.db.execute(select(SocialPost).where(SocialPost.id == focus_post_id, SocialPost.organization_id == organization_id))
                ).scalar_one_or_none()
                if focus is not None and not (focus.artwork or {}).get("files"):
                    focus = None
            posts = ([focus] if focus else []) + [p for p in posts if not focus or p.id != focus.id]
        posts = posts[:GRID]
        tiles = []
        for p in posts:
            first = p.artwork["files"][0]
            try:
                url = self.storage.presigned_download_url(first["key"])
            except Exception:  # noqa: BLE001
                url = None
            tiles.append(
                {
                    "post_id": str(p.id),
                    "title": p.title,
                    "status": p.status,
                    "format": p.format,
                    "slides": len(p.artwork["files"]),
                    "url": url,
                    "metrics": first["metrics"],
                    "synthetic_background": bool((p.artwork or {}).get("synthetic_background")),
                    "is_focus": bool(focus_post_id and p.id == focus_post_id),
                }
            )
        live_available = False
        findings = analyze(tiles, settings.design_rules or {}, live_available)
        warnings = [f for f in findings if f["severity"] == "warning"]
        return {
            "tiles": tiles,
            "findings": findings,
            "verdict": "review" if warnings else ("balanced" if len(tiles) >= 2 else "not_enough"),
            "live_available": live_available,
            "missing": max(0, GRID - len(tiles)),
            "note": (
                "Built from the designed posts known to ERPX. Posts already on your Instagram profile are not included "
                "until the account is connected, so this preview is not the complete grid."
            ),
        }
