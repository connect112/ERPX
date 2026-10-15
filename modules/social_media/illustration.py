"""
One AI illustration for one post, on request, inside the hard image budget (see image_budget.py).

Rules of this workflow:
- It only runs when a person asks for it (a button on the post), never automatically while drafting.
- One asset per concept: the same concept (same prompt, size and model) reuses the picture already made and costs nothing.
- The brand's restrictions come first: the prompt carries the brand's own forbidden visuals as things to avoid, asks for flat shapes and
  no text, people, faces, screens or code, and the picture is only ever a visual element: the words and the logo are drawn by code.
- The picture is stored as a synthetic asset with its prompt, model and time, labelled as AI-made wherever it is shown.
- It is mapped to the brand's two tones when drawn, so a generated picture cannot fall outside the palette.
- Attaching one changes the post's artwork, so an earlier approval is withdrawn; nothing here approves, schedules or publishes.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.exceptions import ValidationError
from modules.social_media import art_direction, image_budget, image_provider
from modules.social_media.artwork import ArtworkService
from modules.social_media.assets import AssetService
from modules.social_media.models import SocialAsset, SocialPost, SocialSettings
from modules.social_media.schemas import Design
from modules.social_media.service import content_hash

SQUARE = "1024x1024"  # for the circle of the poster
WIDE = "1536x1024"  # for the panel of the "visual" composition


def size_for(composition: str) -> str:
    return SQUARE if composition == "poster" else WIDE


def build_prompt(brief: art_direction.ArtBrief, headline: str, brand: dict, rules: dict, size: str, direction: str = "") -> str:
    colors = brand.get("colors", {})
    avoid = "; ".join(rules.get("forbidden_visuals", []))
    subject = brief.concept or headline
    idea = f" Visual idea: {brief.metaphor}." if brief.metaphor else ""
    shape = "square composition" if size == SQUARE else "wide landscape composition"
    return (
        "A flat, minimal vector-style illustration for a cybersecurity education brand's Instagram post. "
        f"Subject: {subject}.{idea} "
        f"Style: simple geometric shapes, flat colour, generous empty space, one clear focal point, {shape}. "
        f"Palette: only {colors.get('accent', '#9AD62B')}, {colors.get('accent2', '#06B4D7')} and {colors.get('primary', '#2E9E3E')} on near-black. "
        "Absolutely no text, letters, numbers, logos, watermarks, people, hands, faces, screens, keyboards or code. "
        f"Avoid: {avoid}. "
        f"{('Direction from the team: ' + direction.strip()) if direction.strip() else ''}"
    ).strip()


def prompt_hash(prompt: str, size: str) -> str:
    quality = (app_settings.SOCIAL_IMAGE_QUALITY or "").strip().lower()
    return hashlib.sha256(f"{prompt}|{size}|{app_settings.SOCIAL_IMAGE_MODEL}|{quality}".encode()).hexdigest()


class IllustrationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.artwork = ArtworkService(db)
        self.assets = AssetService(db)

    async def _existing(self, organization_id: uuid.UUID, digest: str) -> SocialAsset | None:
        return (
            await self.db.execute(
                select(SocialAsset).where(
                    SocialAsset.organization_id == organization_id,
                    SocialAsset.synthetic.is_(True),
                    SocialAsset.provenance["prompt_hash"].astext == digest,
                )
            )
        ).scalars().first()

    async def make(self, organization_id: uuid.UUID, user_id: uuid.UUID, post: SocialPost, settings: SocialSettings, direction: str = "") -> bool:
        """Make (or reuse) the illustration, attach it and draw the artwork again. Returns True if that withdrew an approval."""
        self.artwork._editable(post)
        design = Design.model_validate(post.design or {})
        if design.engine != "v2" or not design.show_icon:
            raise ValidationError("Switch this post to the new design engine first (Artwork, \"Add an illustration\" and \"New design engine\").")
        if post.format not in ("image", "carousel"):
            raise ValidationError("Illustrations are made for single images and carousels.")
        if not image_provider.configured():
            raise ValidationError("AI illustrations aren't set up on this server. Ask your administrator to configure an image provider.")
        content = dict(post.content or {})
        slides = [s for s in (content.get("slides") or []) if isinstance(s, dict)]
        headline = (content.get("headline") or post.title or "").strip()
        brief = art_direction.lenient(content.get("art_direction"))
        base = art_direction.derive(headline, slides, content.get("support_line") or "", content.get("icon") or "")
        brief.concept, brief.metaphor = brief.concept or base.concept, brief.metaphor or base.metaphor
        composition = "poster" if brief.composition == "poster" else "visual"
        size = size_for(composition)
        prompt = build_prompt(brief, headline, settings.brand or {}, settings.design_rules or {}, size, direction)
        digest = prompt_hash(prompt, size)
        before = content_hash(post)

        asset = await self._existing(organization_id, digest)  # one asset per concept: the same concept costs nothing again
        if asset is None:
            async with image_budget.one_at_a_time(post.id):
                asset = await self._existing(organization_id, digest)  # another request may have just made it
                if asset is None:
                    await image_budget.reserve(self.db, organization_id, user_id, post.id, app_settings.SOCIAL_IMAGE_MODEL)
                    raw = await image_provider.generate_image(prompt, size)
                    asset = await self.assets.create(
                        organization_id,
                        user_id,
                        kind="background",
                        filename="ai-illustration.png",
                        raw=raw,
                        alt_text="AI-generated illustration (not a real photograph)",
                        synthetic=True,
                        provenance={
                            "prompt": prompt,
                            "prompt_hash": digest,
                            "model": app_settings.SOCIAL_IMAGE_MODEL,
                            "size": size,
                            "quality": (app_settings.SOCIAL_IMAGE_QUALITY or "").strip() or None,
                            "post_id": str(post.id),
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )

        brief.imagery, brief.composition = "illustration", composition
        content["art_direction"] = brief.model_dump(mode="json")
        if brief.concept:
            content["visual_direction"] = brief.concept[:1000]
        post.content = content
        design.art_asset_id = asset.id
        post.design = design.model_dump(mode="json")
        rendered_withdrew = await self.artwork.render(organization_id, post, settings)
        # The approval was for the artwork as it was: the new picture withdraws it (the drawing step may already have done so).
        withdrew = self.artwork._withdraw_if_changed(post, before) or rendered_withdrew
        await self.db.flush()
        return withdrew

    async def remove(self, organization_id: uuid.UUID, post: SocialPost, settings: SocialSettings) -> bool:
        """Take the illustration off the post (the asset stays in the library) and draw again without it."""
        self.artwork._editable(post)
        before = content_hash(post)
        design = Design.model_validate(post.design or {})
        content = dict(post.content or {})
        brief = art_direction.lenient(content.get("art_direction"))
        brief.imagery = "none"
        if brief.composition == "visual":
            brief.composition = ""  # chosen again from the words
        content["art_direction"] = brief.model_dump(mode="json")
        post.content = content
        design.art_asset_id = None
        post.design = design.model_dump(mode="json")
        rendered_withdrew = await self.artwork.render(organization_id, post, settings)
        withdrew = self.artwork._withdraw_if_changed(post, before) or rendered_withdrew
        await self.db.flush()
        return withdrew
