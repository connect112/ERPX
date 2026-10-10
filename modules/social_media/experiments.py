"""
Experiments: a recorded comparison (two hooks, two cover styles, two posting times...) and what was observed.

ERPX shows each variant's posts and the median of the chosen figure, with the number of posts behind it. It never names a
"winner" and never says one thing caused another: posts differ in more than the tested variable, and a handful of posts is
not evidence. Until every variant has at least three posts with a figure, the only honest reading is "not enough yet".
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from modules.social_media import metrics as M
from modules.social_media.analytics import AnalyticsService
from modules.social_media.models import Experiment, SocialPost

VARIABLES = ("hook", "cover_style", "format", "time", "cta", "other")
METRICS = ("views", "reach", "likes", "comments", "saved", "shares", "total_interactions", "interactions", "er_reach")
STATUSES = ("planned", "running", "concluded", "dropped")
MIN_POSTS_PER_VARIANT = 3
CAUTION = "Posts differ in more than the tested change (topic, time, audience mood), so this is an observation, not proof of cause."


class ExperimentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _posts_exist(self, organization_id: uuid.UUID, ids: list[uuid.UUID]) -> None:
        if not ids:
            return
        found = set((await self.db.execute(select(SocialPost.id).where(SocialPost.organization_id == organization_id, SocialPost.id.in_(ids)))).scalars())
        if missing := [i for i in ids if i not in found]:
            raise ValidationError("One of the chosen posts doesn't exist.")

    @staticmethod
    def _clean_variants(variants: list[dict]) -> list[dict]:
        if not 2 <= len(variants) <= 4:
            raise ValidationError("An experiment compares two to four variants.")
        labels = [v["label"].strip() for v in variants]
        if any(not label for label in labels) or len(set(l.lower() for l in labels)) != len(labels):
            raise ValidationError("Each variant needs its own name.")
        seen: set[uuid.UUID] = set()
        out = []
        for label, v in zip(labels, variants):
            ids = list(dict.fromkeys(v.get("post_ids") or []))
            if seen.intersection(ids):
                raise ValidationError("A post can only belong to one variant.")
            seen.update(ids)
            out.append({"label": label, "post_ids": [str(i) for i in ids]})
        return out

    async def create(self, organization_id: uuid.UUID, user_id: uuid.UUID, data: dict) -> Experiment:
        variants = self._clean_variants(data["variants"])
        await self._posts_exist(organization_id, [uuid.UUID(i) for v in variants for i in v["post_ids"]])
        row = Experiment(
            organization_id=organization_id, created_by_user_id=user_id, name=data["name"].strip(), hypothesis=data["hypothesis"].strip(), variable=data["variable"],
            metric=data["metric"], audience=(data.get("audience") or "").strip() or None, variants=variants, status="planned",
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get(self, organization_id: uuid.UUID, experiment_id: uuid.UUID) -> Experiment:
        row = (await self.db.execute(select(Experiment).where(Experiment.id == experiment_id, Experiment.organization_id == organization_id))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Experiment not found.")
        return row

    async def everything(self, organization_id: uuid.UUID) -> list[Experiment]:
        return list((await self.db.execute(select(Experiment).where(Experiment.organization_id == organization_id).order_by(Experiment.created_at.desc()))).scalars())

    async def update(self, organization_id: uuid.UUID, experiment_id: uuid.UUID, data: dict, today: date | None = None) -> Experiment:
        row = await self.get(organization_id, experiment_id)
        today = today or datetime.now(timezone.utc).date()
        if row.status in ("concluded", "dropped") and set(data) - {"conclusion"}:
            raise ValidationError("A finished experiment can only have its conclusion edited.")
        if "variants" in data and data["variants"] is not None:
            variants = self._clean_variants(data["variants"])
            await self._posts_exist(organization_id, [uuid.UUID(i) for v in variants for i in v["post_ids"]])
            row.variants = variants
        for field in ("name", "hypothesis", "audience"):
            if data.get(field) is not None:
                setattr(row, field, data[field].strip() or None if field == "audience" else data[field].strip())
        if data.get("conclusion") is not None:
            row.conclusion = data["conclusion"].strip() or None
        if data.get("status") is not None and data["status"] != row.status:
            new = data["status"]
            allowed = {"planned": ("running", "dropped"), "running": ("concluded", "dropped"), "concluded": (), "dropped": ()}
            if new not in allowed[row.status]:
                raise ValidationError(f"An experiment can't go from {row.status} to {new}.")
            if new == "running":
                row.started_on = today
            elif new in ("concluded", "dropped"):
                row.ended_on = today
            row.status = new
        await self.db.flush()
        return row

    async def delete(self, organization_id: uuid.UUID, experiment_id: uuid.UUID) -> None:
        row = await self.get(organization_id, experiment_id)
        await self.db.delete(row)
        await self.db.flush()

    # ---------------- what was observed ----------------

    async def results(self, organization_id: uuid.UUID, row: Experiment) -> dict:
        analytics = AnalyticsService(self.db)
        by_post = {r["post_id"]: r for r in await analytics.posts(organization_id, limit=200) if r["post_id"]}
        titles = {str(p.id): p.title for p in (await self.db.execute(select(SocialPost).where(SocialPost.organization_id == organization_id))).scalars()} if row.variants else {}
        out = []
        for variant in row.variants:
            items = []
            for pid in variant["post_ids"]:
                found = by_post.get(uuid.UUID(pid))
                value = None
                if found is not None:
                    value = found.get(row.metric) if row.metric in ("interactions", "er_reach") else found["metrics"].get(row.metric)
                items.append({"post_id": pid, "title": titles.get(pid), "published": found is not None, "insights_read": bool(found and found["insights_read"]), "value": value})
            values = [i["value"] for i in items if i["value"] is not None]
            middle, n = M.typical(values)
            out.append({"label": variant["label"], "posts": items, "n": n, "median": middle, "low": min(values) if values else None, "high": max(values) if values else None})
        return {"metric": row.metric, "variants": out, "reading": self.reading(row.metric, out), "caution": CAUTION}

    @staticmethod
    def reading(metric: str, variants: list[dict]) -> str:
        short = [v for v in variants if v["n"] < MIN_POSTS_PER_VARIANT]
        if short:
            names = ", ".join(f"{v['label']} ({v['n']})" for v in short)
            return f"Not enough yet: each variant needs at least {MIN_POSTS_PER_VARIANT} published posts with a figure. Short of that: {names}. Nothing can be concluded."
        ranked = sorted(variants, key=lambda v: v["median"], reverse=True)
        top, bottom = ranked[0], ranked[-1]
        overlap = top["low"] <= bottom["high"]
        parts = ", ".join(f"{v['label']}: median {v['median']:.4g} over {v['n']} posts" for v in ranked)
        tail = "The posts' figures overlap, so the gap may be ordinary variation." if overlap else "In this sample the posts' figures don't overlap, which is suggestive but still not proof."
        return f"{parts}. {tail}"
