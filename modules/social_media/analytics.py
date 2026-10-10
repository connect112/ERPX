"""
Analytics: reading Instagram's own figures into ERPX and showing them honestly.

- Only what Instagram's official API returns. A value Instagram didn't give is stored as "not available" (no row, or a null
  with a note), never as zero.
- Every figure carries its source, period, last read time, whether it is observed or calculated, and its limits (metrics.py).
- Reading is bounded: at most 14 days of account figures and 40 posts per run, at most one run every 15 minutes, and a
  temporary problem stops that part of the run instead of hammering Instagram.
- Nothing here claims who saved or shared anything, and nothing here predicts growth.
"""

import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.logging_config import get_logger
from modules.social_media import instagram, metrics as M
from modules.social_media.connection import ConnectionService, computed_status
from modules.social_media.inbox import InboxService, parse_time
from modules.social_media.instagram import InstagramError
from modules.social_media.models import AccountDay, IgMedia, MediaMetric, SocialAccount, SocialPost, SocialSettings
from modules.social_media.token_crypto import TokenUnreadable, decrypt_token

logger = get_logger(__name__)

MIN_INTERVAL = timedelta(minutes=15)
HISTORY_DAYS = 28  # how far back account figures are read
DAYS_PER_SYNC = 14
ALWAYS_REREAD_DAYS = 3  # Instagram can revise the latest days
MEDIA_PER_SYNC = 40
ACCOUNT_TOTAL_METRICS = ["reach", "views", "accounts_engaged", "total_interactions", "likes", "comments", "saves", "shares", "replies", "reposts", "profile_links_taps"]
SNAPSHOT_METRICS = ["followers_count", "follows_count", "media_count"]
# Distinct-account figures can't be added across days, so they are shown as a daily average instead of a total.
NOT_ADDITIVE = {"reach", "accounts_engaged"}
UNSUPPORTED_NOTE = "Instagram doesn't provide this figure for this post."
MISSING_NOTE = "Instagram returned no value (it may not be available yet or for this kind of post)."


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def kind_of(media: IgMedia) -> str:
    """image | carousel | reel | story, from what Instagram says the post is."""
    product = (media.product_type or "").upper()
    if product == "REELS":
        return "reel"
    if product == "STORY":
        return "story"
    return "carousel" if (media.media_type or "").upper() == "CAROUSEL_ALBUM" else "image"


def hook_kind(text: str | None) -> str:
    text = (text or "").strip()
    if not text:
        return "unknown"
    if "?" in text:
        return "question"
    return "number" if text[0].isdigit() else "statement"


_CTA_WORDS = (
    ("save", ("save",)),
    ("comment", ("comment", "tell us", "let us know", "drop a")),
    ("follow", ("follow",)),
    ("message", ("dm", "message us", "message me", "inbox")),
    ("link", ("link in bio", "click", "visit", "register", "sign up", "enrol", "enroll", "apply")),
    ("share", ("share", "send this", "tag a")),
)


def cta_kind(text: str | None) -> str:
    lowered = (text or "").strip().lower()
    if not lowered:
        return "none"
    for kind, words in _CTA_WORDS:
        if any(w in lowered for w in words):
            return kind
    return "other"


def time_of_day(at: datetime | None, zone: str) -> str:
    if at is None:
        return "unknown"
    try:
        hour = at.astimezone(ZoneInfo(zone)).hour
    except Exception:  # noqa: BLE001 - a bad zone name must not break the report
        hour = at.hour
    return "morning (5-11)" if 5 <= hour < 11 else "midday (11-16)" if 11 <= hour < 16 else "evening (16-21)" if 16 <= hour < 21 else "night (21-5)"


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- reading from Instagram ----------------

    async def sync(self, organization_id: uuid.UUID, now: datetime | None = None, force: bool = False) -> dict:
        now = now or datetime.now(timezone.utc)
        connections = ConnectionService(self.db)
        account = await connections.get(organization_id)
        if account is None or computed_status(account, now) not in ("connected", "expiring"):
            raise ConflictError("Instagram isn't connected, so there are no figures to read.")
        state = dict(account.sync_state or {})
        mine = dict(state.get("analytics") or {})
        last = parse_time(mine.get("last_at"))
        if not force and last and now - last < MIN_INTERVAL:
            minutes = max(1, int((now - last).total_seconds() // 60))
            return {"skipped": True, "message": f"Already read {minutes} minute(s) ago. Instagram is only asked at most every 15 minutes.", "stages": mine.get("stages", {})}
        caps = account.capabilities or {}
        if caps.get("insights") == "unavailable":
            return {"skipped": True, "message": "Instagram hasn't given this app permission to read insights (see Settings, Check what it can do).", "stages": mine.get("stages", {})}
        try:
            client = instagram.get_instagram_client(account.external_account_id, decrypt_token(account.token_encrypted or ""))
        except TokenUnreadable as exc:
            await connections._mark_failed(account, str(exc), now)
            raise ConflictError(str(exc)) from None

        stages: dict[str, dict] = {}
        unsupported = set(mine.get("unsupported_account") or [])
        for name, runner in (("profile", self._profile), ("media", self._media_list), ("account", self._account_days), ("posts", self._posts)):
            try:
                if name == "account":
                    count = await runner(account, client, now, unsupported)
                else:
                    count = await runner(account, client, now)
                stages[name] = {"ok": True, "error": None, "count": count}
            except InstagramError as exc:
                stages[name] = {"ok": False, "error": exc.message}
                if exc.kind == "token":
                    await connections._mark_failed(account, exc.message, now)
                    break
        state["analytics"] = {"last_at": now.isoformat(), "stages": stages, "unsupported_account": sorted(unsupported)}
        account.sync_state = state
        await self.db.flush()
        return {"skipped": False, "message": None, "stages": stages}

    async def _put_days(self, organization_id: uuid.UUID, rows: list[tuple[date, str, float]], now: datetime) -> None:
        if not rows:
            return
        stmt = pg_insert(AccountDay).values(
            [{"id": uuid.uuid4(), "organization_id": organization_id, "day": d, "metric": m, "value": v, "synced_at": now, "created_at": now, "updated_at": now} for d, m, v in rows]
        )
        await self.db.execute(stmt.on_conflict_do_update(constraint="uq_social_account_day_metric", set_={"value": stmt.excluded.value, "synced_at": now, "updated_at": now}))

    async def _profile(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime) -> int:
        counts = await client.profile_counts()
        await self._put_days(account.organization_id, [(now.date(), key, float(value)) for key, value in counts.items()], now)
        return len(counts)

    async def _media_list(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime) -> int:
        """Which posts are on the profile (the same list the inbox uses), so their figures can be read."""
        return await InboxService(self.db)._media(account, client, now)

    async def _account_days(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime, unsupported: set[str]) -> int:
        yesterday = now.date() - timedelta(days=1)  # today is still filling up
        wanted = [yesterday - timedelta(days=i) for i in range(HISTORY_DAYS)]
        have = {
            d
            for d in (
                await self.db.execute(
                    select(AccountDay.day).where(AccountDay.organization_id == account.organization_id, AccountDay.metric == "views", AccountDay.day >= wanted[-1])
                )
            ).scalars()
        }
        todo = [d for d in wanted if d not in have or (yesterday - d).days < ALWAYS_REREAD_DAYS][:DAYS_PER_SYNC]
        stored = 0
        for day in todo:
            metrics = [m for m in ACCOUNT_TOTAL_METRICS if m not in unsupported]
            if not metrics:
                break
            since, until = _day_start(day), _day_start(day) + timedelta(days=1)
            try:
                values = await client.account_totals(metrics, since, until)
            except InstagramError as exc:
                if exc.kind != "permanent":
                    raise
                # One unsupported metric fails the whole request. Ask one by one and remember which ones Instagram refuses.
                values = {}
                for metric in metrics:
                    try:
                        values.update(await client.account_totals([metric], since, until))
                    except InstagramError as single:
                        if single.kind != "permanent":
                            raise
                        unsupported.add(metric)
            rows = [(day, key, value) for key, value in values.items()]
            await self._put_days(account.organization_id, rows, now)
            stored += len(rows)
        return stored

    async def _posts(self, account: SocialAccount, client: instagram.InstagramClient, now: datetime) -> int:
        org = account.organization_id
        media = list(
            (await self.db.execute(select(IgMedia).where(IgMedia.organization_id == org).order_by(IgMedia.posted_at.desc().nullslast()).limit(MEDIA_PER_SYNC))).scalars()
        )
        synced: dict[str, datetime] = {}
        for row in (await self.db.execute(select(MediaMetric).where(MediaMetric.organization_id == org))).scalars():
            if row.media_external_id not in synced or row.synced_at > synced[row.media_external_id]:
                synced[row.media_external_id] = row.synced_at
        done = 0
        for item in media:
            kind = kind_of(item)
            if kind == "story":
                continue  # stories disappear after 24 hours; their figures can't be read later
            age = now - (item.posted_at or now)
            last = synced.get(item.external_id)
            if last is not None and now - last < (timedelta(hours=20) if age < timedelta(days=14) else timedelta(days=7)):
                continue
            wanted = M.REEL_METRICS if kind == "reel" else M.FEED_METRICS
            try:
                values = await client.media_insights(item.external_id, wanted)
                refused: set[str] = set()
            except InstagramError as exc:
                if exc.kind != "permanent":
                    raise
                values, refused = {}, set()
                for metric in wanted:
                    try:
                        values.update(await client.media_insights(item.external_id, [metric]))
                    except InstagramError as single:
                        if single.kind != "permanent":
                            raise
                        refused.add(metric)
            await self._put_media(org, item.external_id, wanted, values, refused, now)
            done += 1
        return done

    async def _put_media(self, org: uuid.UUID, external_id: str, wanted: list[str], values: dict[str, float], refused: set[str], now: datetime) -> None:
        rows = [
            {
                "id": uuid.uuid4(), "organization_id": org, "media_external_id": external_id, "metric": metric,
                "value": values.get(metric), "note": None if metric in values else (UNSUPPORTED_NOTE if metric in refused else MISSING_NOTE),
                "synced_at": now, "created_at": now, "updated_at": now,
            }
            for metric in wanted
        ]
        stmt = pg_insert(MediaMetric).values(rows)
        await self.db.execute(stmt.on_conflict_do_update(constraint="uq_social_media_metric", set_={"value": stmt.excluded.value, "note": stmt.excluded.note, "synced_at": now, "updated_at": now}))

    # ---------------- reading what was stored ----------------

    async def _zone(self, organization_id: uuid.UUID) -> str:
        row = (await self.db.execute(select(SocialSettings.timezone).where(SocialSettings.organization_id == organization_id))).scalar_one_or_none()
        return row or "Asia/Kolkata"

    async def account_series(self, organization_id: uuid.UUID, start: date, end: date) -> dict[str, dict[date, tuple[float, datetime]]]:
        """{metric: {day: (value, synced_at)}} for the days in [start, end] that have a figure."""
        out: dict[str, dict[date, tuple[float, datetime]]] = defaultdict(dict)
        for row in (await self.db.execute(select(AccountDay).where(AccountDay.organization_id == organization_id, AccountDay.day >= start, AccountDay.day <= end))).scalars():
            out[row.metric][row.day] = (row.value, row.synced_at)
        return out

    def summarise_metric(self, key: str, series: dict[date, tuple[float, datetime]], start: date, end: date) -> dict:
        info = M.ACCOUNT_METRICS[key]
        days = (end - start).days + 1
        present = {d: v for d, (v, _) in series.items() if start <= d <= end}
        average = (sum(present.values()) / len(present)) if present else None
        last = max((s for d, (_, s) in series.items() if start <= d <= end), default=None)
        additive = key not in NOT_ADDITIVE
        return {
            "key": key, "label": info.label, "kind": info.kind, "source": info.source, "period": info.period, "definition": info.definition, "limitation": info.limitation,
            "value": (sum(present.values()) if additive and present else average),
            "value_kind": "total" if additive else "daily_average",
            "daily_average": average,
            "days_with_data": len(present), "days_in_period": days,
            "last_synced_at": last,
            "series": [{"day": start + timedelta(days=i), "value": present.get(start + timedelta(days=i))} for i in range(days)],
        }

    def cards_for(self, series: dict, start: date, end: date) -> list[dict]:
        """One card per account metric for [start, end], compared with the equally long period right before it."""
        days = (end - start).days + 1
        prev_end, prev_start = start - timedelta(days=1), start - timedelta(days=days)
        cards = []
        for key in ACCOUNT_TOTAL_METRICS:
            current = self.summarise_metric(key, series.get(key, {}), start, end)
            before = self.summarise_metric(key, series.get(key, {}), prev_start, prev_end)
            change = None
            if current["days_with_data"] >= 0.7 * days and before["days_with_data"] >= 0.7 * days and before["daily_average"]:
                change = (current["daily_average"] - before["daily_average"]) / before["daily_average"]
            cards.append({**current, "previous_daily_average": before["daily_average"] if before["days_with_data"] else None, "change_vs_previous": change})
        return cards

    async def overview(self, organization_id: uuid.UUID, days: int, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        end = now.date() - timedelta(days=1)
        start = end - timedelta(days=days - 1)
        prev_start = start - timedelta(days=days)
        series = await self.account_series(organization_id, prev_start, now.date())
        cards = self.cards_for(series, start, end)
        snapshots = {key: series.get(key, {}) for key in SNAPSHOT_METRICS}
        followers = snapshots["followers_count"]
        inside = sorted((d, v) for d, (v, _) in followers.items() if start <= d <= now.date())
        follower_change = (inside[-1][1] - inside[0][1]) if len(inside) >= 2 else None
        info = M.ACCOUNT_METRICS["followers_count"]
        return {
            "period": {"start": start, "end": end, "days": days},
            "cards": cards,
            "snapshots": {
                key: {
                    "key": key, "label": M.ACCOUNT_METRICS[key].label, "kind": M.OBSERVED, "source": M.ACCOUNT_METRICS[key].source, "limitation": M.ACCOUNT_METRICS[key].limitation,
                    "latest": (max(s.items())[1][0] if s else None), "latest_day": (max(s) if s else None),
                    "last_synced_at": (max(v[1] for v in s.values()) if s else None),
                    "series": [{"day": d, "value": v} for d, (v, _) in sorted(s.items()) if d >= prev_start],
                }
                for key, s in snapshots.items()
            },
            "follower_change": {
                "value": follower_change, "kind": M.CALCULATED, "source": M.ACCOUNT_METRICS["follower_change"].source, "limitation": M.ACCOUNT_METRICS["follower_change"].limitation,
                "from_day": inside[0][0] if len(inside) >= 2 else None, "to_day": inside[-1][0] if len(inside) >= 2 else None,
                "note": None if follower_change is not None else "Needs follower snapshots on at least two different days. ERPX only has snapshots from the day it started reading.",
            },
            "notes": [M.DATA_DELAY_NOTE, "Instagram assigns days using its own cut-off, so a day's figure may not line up exactly with your calendar day."],
            "followers_source": info.source,
        }

    async def posts(self, organization_id: uuid.UUID, limit: int = 40, now: datetime | None = None) -> list[dict]:
        zone = await self._zone(organization_id)
        media = list(
            (await self.db.execute(select(IgMedia).where(IgMedia.organization_id == organization_id).order_by(IgMedia.posted_at.desc().nullslast()).limit(limit))).scalars()
        )
        values: dict[str, dict[str, float | None]] = defaultdict(dict)
        notes: dict[str, dict[str, str]] = defaultdict(dict)
        synced: dict[str, datetime] = {}
        for row in (await self.db.execute(select(MediaMetric).where(MediaMetric.organization_id == organization_id, MediaMetric.media_external_id.in_([m.external_id for m in media])))).scalars():
            values[row.media_external_id][row.metric] = row.value
            if row.note:
                notes[row.media_external_id][row.metric] = row.note
            if row.media_external_id not in synced or row.synced_at > synced[row.media_external_id]:
                synced[row.media_external_id] = row.synced_at
        post_ids = [m.post_id for m in media if m.post_id]
        posts = {p.id: p for p in (await self.db.execute(select(SocialPost).where(SocialPost.id.in_(post_ids)))).scalars()} if post_ids else {}
        snapshots = sorted(
            (await self.db.execute(select(AccountDay.day, AccountDay.value).where(AccountDay.organization_id == organization_id, AccountDay.metric == "followers_count"))).all()
        )
        out = []
        for m in media:
            kind = kind_of(m)
            vals = values.get(m.external_id, {})
            post = posts.get(m.post_id) if m.post_id else None
            content = (post.content or {}) if post else {}
            hooks = content.get("hooks") or []
            near = next((v for d, v in snapshots if m.posted_at and 0 <= (d - m.posted_at.date()).days <= 3), None)
            out.append(
                {
                    "external_id": m.external_id, "kind": kind, "permalink": m.permalink, "caption": (m.caption or "")[:200], "posted_at": m.posted_at, "thumbnail_url": m.thumbnail_url,
                    "post_id": post.id if post else None, "title": post.title if post else None, "pillar": post.pillar if post else None,
                    "hook": hook_kind(hooks[0] if hooks else content.get("headline")) if post else "unknown", "cta": cta_kind(content.get("cta")) if post else "unknown",
                    "time_of_day": time_of_day(m.posted_at, zone),
                    "insights_read": m.external_id in synced, "last_synced_at": synced.get(m.external_id),
                    "metrics": {k: vals.get(k) for k in (M.REEL_METRICS if kind == "reel" else M.FEED_METRICS) if k in vals},
                    "unavailable": notes.get(m.external_id, {}),
                    "interactions": M.interactions(vals), "er_reach": M.er_reach(vals), "er_followers": M.er_followers(vals, near),
                }
            )
        return out

    def breakdown(self, rows: list[dict], by: str) -> list[dict]:
        """Group posts by format, pillar, hook, call to action or time of day. Small groups are labelled, never ranked as proof."""
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            if r["kind"] == "story" or not r["insights_read"]:
                continue
            groups[str(r.get(by) or "unknown")].append(r)
        result = []
        for label, items in sorted(groups.items()):
            vectors = [r["metrics"] for r in items]
            reach, n_reach = M.typical([v.get("reach") for v in vectors])
            views, n_views = M.typical([v.get("views") for v in vectors])
            saves, n_saves = M.typical([v.get("saved") for v in vectors])
            rate, n_rate = M.pooled_er_reach(vectors)
            result.append(
                {
                    "label": label, "posts": len(items), "median_reach": reach, "reach_posts": n_reach, "median_views": views, "views_posts": n_views,
                    "median_saves": saves, "saves_posts": n_saves, "er_reach_pooled": rate, "er_reach_posts": n_rate,
                    "caution": "Too few posts to conclude anything." if len(items) < 5 else None,
                }
            )
        return sorted(result, key=lambda g: (-g["posts"], g["label"]))

    async def consistency(self, organization_id: uuid.UUID, start: date, end: date) -> dict:
        times = sorted(
            t.date()
            for t in (
                await self.db.execute(
                    select(IgMedia.posted_at).where(IgMedia.organization_id == organization_id, IgMedia.posted_at >= _day_start(start), IgMedia.posted_at < _day_start(end + timedelta(days=1)))
                )
            ).scalars()
            if t is not None
        )
        days = (end - start).days + 1
        distinct = sorted(set(times))
        gaps = [(b - a).days for a, b in zip(distinct, distinct[1:])]
        edges = [(distinct[0] - start).days, (end - distinct[-1]).days] if distinct else [days]
        return {
            "posts": len(times), "days_in_period": days, "days_with_a_post": len(distinct), "longest_gap_days": max(gaps + edges) if (gaps or edges) else None,
            "kind": M.CALCULATED, "source": "ERPX: posts Instagram lists on the profile, by posting day", "limitation": "Only counts posts ERPX has read from Instagram (the 25 most recent).",
        }
