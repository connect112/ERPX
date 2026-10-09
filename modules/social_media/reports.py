"""
Weekly and monthly reports: what worked, what didn't, and what to test next, worked out from the stored figures only.

Every statement comes from a rule applied to numbers ERPX holds (no AI wrote it), names the figures and how many posts or days
are behind it, and says so when there isn't enough to say anything. Missing figures are reported as missing, never as zero.
A report never promises growth.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from modules.social_media import metrics as M
from modules.social_media.analytics import AnalyticsService
from modules.social_media.models import Experiment, Report, SocialPost

KINDS = ("weekly", "monthly")
MIN_POSTS_FOR_COMPARISON = 4  # fewer posts than this and "best" and "worst" mean nothing
STANDS_OUT_ABOVE = 1.25  # a post is called out as strong only when its reach is this many times the typical post's
STANDS_OUT_BELOW = 0.6  # ... and as weak only when it is at most this fraction of it


def last_period(kind: str, today: date) -> tuple[date, date]:
    """The most recent complete week (Monday to Sunday) or calendar month before `today`."""
    if kind == "weekly":
        monday = today - timedelta(days=today.weekday())
        return monday - timedelta(days=7), monday - timedelta(days=1)
    first = today.replace(day=1)
    previous_last = first - timedelta(days=1)
    return previous_last.replace(day=1), previous_last


def period_for(kind: str, start: date) -> tuple[date, date]:
    if kind == "weekly":
        if start.weekday() != 0:
            raise ValidationError("A weekly report starts on a Monday.")
        return start, start + timedelta(days=6)
    if start.day != 1:
        raise ValidationError("A monthly report starts on the first of a month.")
    nxt = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, nxt - timedelta(days=1)


def _fmt(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:,.0f}" if abs(value) >= 100 else f"{value:,.2f}".rstrip("0").rstrip(".")


def _pct(value: float) -> str:
    return f"{abs(value) * 100:.0f}%"


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, organization_id: uuid.UUID, kind: str, start: date, user_id: uuid.UUID | None = None, now: datetime | None = None) -> Report:
        if kind not in KINDS:
            raise ValidationError("A report is weekly or monthly.")
        now = now or datetime.now(timezone.utc)
        start, end = period_for(kind, start)
        if end >= now.date():
            raise ValidationError("That period isn't over yet, so there is nothing complete to report.")
        data = await self.build(organization_id, kind, start, end, now)
        stmt = pg_insert(Report).values(
            id=uuid.uuid4(), organization_id=organization_id, kind=kind, period_start=start, period_end=end, data=data, generated_by_user_id=user_id, created_at=now, updated_at=now
        )
        await self.db.execute(stmt.on_conflict_do_update(constraint="uq_social_report_period", set_={"data": data, "generated_by_user_id": user_id, "updated_at": now}))
        await self.db.flush()
        return await self.find(organization_id, kind, start)

    async def find(self, organization_id: uuid.UUID, kind: str, start: date) -> Report:
        row = (await self.db.execute(select(Report).where(Report.organization_id == organization_id, Report.kind == kind, Report.period_start == start).execution_options(populate_existing=True))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Report not found.")
        return row

    async def get(self, organization_id: uuid.UUID, report_id: uuid.UUID) -> Report:
        row = (await self.db.execute(select(Report).where(Report.organization_id == organization_id, Report.id == report_id))).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Report not found.")
        return row

    async def recent(self, organization_id: uuid.UUID, kind: str | None = None) -> list[Report]:
        query = select(Report).where(Report.organization_id == organization_id).order_by(Report.period_start.desc()).limit(60)
        if kind:
            query = query.where(Report.kind == kind)
        return list((await self.db.execute(query)).scalars())

    async def ensure_latest(self, organization_id: uuid.UUID, kind: str, now: datetime | None = None) -> Report | None:
        """Used by the schedule: make the report for the last complete period if it doesn't exist yet."""
        now = now or datetime.now(timezone.utc)
        start, _ = last_period(kind, now.date())
        existing = (await self.db.execute(select(Report).where(Report.organization_id == organization_id, Report.kind == kind, Report.period_start == start))).scalar_one_or_none()
        if existing is not None:
            return None
        return await self.generate(organization_id, kind, start, None, now)

    # ---------------- the content ----------------

    async def build(self, organization_id: uuid.UUID, kind: str, start: date, end: date, now: datetime) -> dict:
        analytics = AnalyticsService(self.db)
        days = (end - start).days + 1
        prev_start = start - timedelta(days=days)
        series = await analytics.account_series(organization_id, prev_start, now.date())
        cards = analytics.cards_for(series, start, end)
        for card in cards:
            card.pop("series", None)  # the report keeps the totals; the charts live on the analytics screen
        followers = sorted((d, v) for d, (v, _) in series.get("followers_count", {}).items() if start <= d <= end)
        follower_block = {
            "start": followers[0][1] if followers else None, "end": followers[-1][1] if len(followers) >= 2 else None,
            "change": (followers[-1][1] - followers[0][1]) if len(followers) >= 2 else None, "kind": M.CALCULATED,
            "source": M.ACCOUNT_METRICS["follower_change"].source, "limitation": M.ACCOUNT_METRICS["follower_change"].limitation,
        }
        every = await analytics.posts(organization_id, limit=200)
        window = [r for r in every if r["posted_at"] and start <= r["posted_at"].date() <= end and r["kind"] != "story"]
        read = [r for r in window if r["insights_read"]]
        with_reach = [r for r in read if r["metrics"].get("reach") is not None]
        top = sorted(with_reach, key=lambda r: -r["metrics"]["reach"])[:3]
        bottom = sorted(with_reach, key=lambda r: r["metrics"]["reach"])[:1] if len(with_reach) >= MIN_POSTS_FOR_COMPARISON else []
        rate, rate_n = M.pooled_er_reach([r["metrics"] for r in read])
        consistency = await analytics.consistency(organization_id, start, end)
        made = (
            await self.db.execute(
                select(func.count()).select_from(SocialPost).where(
                    SocialPost.organization_id == organization_id, SocialPost.status == "published",
                    SocialPost.published_at >= datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc),
                    SocialPost.published_at < datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
                )
            )
        ).scalar_one()
        experiments = [
            {"id": str(e.id), "name": e.name, "status": e.status, "variable": e.variable}
            for e in (await self.db.execute(select(Experiment).where(Experiment.organization_id == organization_id, Experiment.status.in_(("running", "concluded"))))).scalars()
            if (e.started_on or start) <= end and (e.ended_on or end) >= start
        ]

        def brief(r: dict) -> dict:
            return {
                "external_id": r["external_id"], "title": r["title"] or (r["caption"][:80] or "Post"), "kind": r["kind"], "permalink": r["permalink"], "posted_at": r["posted_at"].isoformat() if r["posted_at"] else None,
                "reach": r["metrics"].get("reach"), "views": r["metrics"].get("views"), "saves": r["metrics"].get("saved"), "shares": r["metrics"].get("shares"), "er_reach": r["er_reach"],
            }

        data = {
            "period": {"kind": kind, "start": start.isoformat(), "end": end.isoformat(), "days": days},
            "generated_at": now.isoformat(),
            "account": {"cards": _jsonable(cards), "followers": follower_block},
            "posts": {
                "on_instagram": len(window), "insights_read": len(read), "published_from_erpx": made,
                "top": [brief(r) for r in top], "lowest": [brief(r) for r in bottom],
                "er_reach_pooled": rate, "er_reach_posts": rate_n, "er_reach_note": M.POOLED_NOTE,
                "by_format": analytics.breakdown(read, "kind"), "by_pillar": analytics.breakdown(read, "pillar"),
            },
            "consistency": consistency,
            "experiments": experiments,
        }
        data["findings"] = self.findings(data, cards, window, read, with_reach)
        data["caveats"] = self.caveats(data, cards, window, read)
        return _jsonable(data)

    @staticmethod
    def findings(data: dict, cards: list[dict], window: list[dict], read: list[dict], with_reach: list[dict]) -> dict:
        worked: list[str] = []
        didnt: list[str] = []
        test: list[str] = []
        days = data["period"]["days"]
        for card in cards:
            if card["change_vs_previous"] is None or card["key"] not in ("reach", "views", "total_interactions", "saves", "shares"):
                continue
            direction = "higher" if card["change_vs_previous"] > 0 else "lower"
            if abs(card["change_vs_previous"]) < 0.05:
                continue
            line = f"{card['label']} per day was {_pct(card['change_vs_previous'])} {direction} than the previous {days} days ({card['days_with_data']} of {card['days_in_period']} days had figures)."
            (worked if card["change_vs_previous"] > 0 else didnt).append(line)
        if data["account"]["followers"]["change"] is not None:
            change = data["account"]["followers"]["change"]
            if change:
                line = f"Followers changed by {change:+,.0f} between the first and last snapshot in the period (a net figure; unfollows aren't separated)."
                (worked if change > 0 else didnt).append(line)
        if len(with_reach) >= MIN_POSTS_FOR_COMPARISON:
            typical_reach = median(r["metrics"]["reach"] for r in with_reach)
            best, low = data["posts"]["top"][0], data["posts"]["lowest"][0]
            standouts = False
            if typical_reach and best["reach"] >= STANDS_OUT_ABOVE * typical_reach:
                worked.append(f"Highest reach: \"{best['title']}\" ({best['kind']}) reached {_fmt(best['reach'])} accounts, against a typical {_fmt(typical_reach)} for the {len(with_reach)} posts.")
                standouts = True
            if typical_reach and low["reach"] <= STANDS_OUT_BELOW * typical_reach:
                didnt.append(f"Lowest reach: \"{low['title']}\" ({low['kind']}) reached {_fmt(low['reach'])} accounts, against a typical {_fmt(typical_reach)} for the {len(with_reach)} posts.")
                standouts = True
            if not standouts:
                worked.append(f"Reach was similar across the {len(with_reach)} posts ({_fmt(low['reach'])} to {_fmt(best['reach'])} accounts), so no post clearly stood out.")
        gap = data["consistency"].get("longest_gap_days")
        has_figures = any(c["days_with_data"] for c in cards)
        if data["consistency"]["posts"] == 0:
            # Only a statement about the profile when ERPX was demonstrably reading it; otherwise it just hasn't read any posts.
            if has_figures or data["posts"]["published_from_erpx"]:
                didnt.append("ERPX found no posts on Instagram for this period.")
        elif gap is not None and gap >= 5:
            didnt.append(f"There was a gap of {gap} days without a post.")
        else:
            worked.append(f"Published {data['consistency']['posts']} post(s) on {data['consistency']['days_with_a_post']} of {days} days.")
        if len(read) < MIN_POSTS_FOR_COMPARISON:
            test.append(f"Only {len(read)} post(s) have readable figures this period, too few to say which format, topic or hook does better. Keep publishing and compare over a longer period.")
        else:
            counts = {g["label"]: g["posts"] for g in data["posts"]["by_format"]}
            for fmt in ("image", "carousel", "reel"):
                if counts.get(fmt, 0) < 3:
                    test.append(f"Try more {fmt} posts: only {counts.get(fmt, 0)} this period, which can't be compared fairly with the others.")
        if not data["experiments"]:
            test.append("No experiment is running. Pick one thing to change (a hook style, a cover style, a posting time) and record it under Experiments.")
        if not worked and not didnt:
            didnt.append("There wasn't enough data to say what worked or didn't. See the notes below.")
        return {"worked": worked, "didnt": didnt, "test_next": test[:5]}

    @staticmethod
    def caveats(data: dict, cards: list[dict], window: list[dict], read: list[dict]) -> list[str]:
        notes = [M.DATA_DELAY_NOTE]
        thin = [c["label"] for c in cards if 0 < c["days_with_data"] < c["days_in_period"]]
        if thin:
            notes.append(f"Some days have no figure from Instagram, so these cover fewer days than the period: {', '.join(thin)}.")
        silent = [c["label"] for c in cards if c["days_with_data"] == 0]
        if silent:
            notes.append(f"No figures at all for: {', '.join(silent)}. They are shown as not available, not as zero.")
        if len(window) > len(read):
            notes.append(f"{len(window) - len(read)} post(s) in this period have no readable figures yet.")
        notes.append("Only the 25 most recent posts are read from Instagram, so a long period can include posts that were never read.")
        notes.append("Reach is estimated by Instagram and can't be added across days; it is shown as a daily average.")
        notes.append("This report describes what happened. It does not predict growth, and a change doesn't prove what caused it.")
        return notes


def _jsonable(value):
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value
