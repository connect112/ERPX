"""
Social Media phase 5a: insights, honest metrics, experiments and reports.

The rules these tests hold the code to: a figure Instagram didn't give is never turned into zero; every figure says where it came
from and whether it was observed or calculated; a rate over several posts is total interactions over total reach (never an average
of percentages); small samples are labelled instead of ranked; nothing here claims a cause, a winner or future growth.
"""

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.exceptions import ConflictError, ValidationError
from modules.social_media import metrics as M
from modules.social_media.analytics import AnalyticsService, cta_kind, hook_kind, time_of_day
from modules.social_media.experiments import ExperimentService
from modules.social_media.instagram import InstagramError
from modules.social_media.models import AccountDay, Experiment, IgMedia, MediaMetric, Report, SocialAccount, SocialPost
from modules.social_media.reports import ReportService, last_period, period_for
from tests._fixtures import _make_user
from tests.api.social_inbox_fakes import NOW, add_media, connected_account, install

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
FEED = {"views": 900, "reach": 600, "likes": 40, "comments": 5, "saved": 20, "shares": 5, "total_interactions": 70, "follows": 3, "profile_visits": 12}
DAY = {"reach": 300, "views": 800, "accounts_engaged": 40, "total_interactions": 70, "likes": 50, "comments": 5, "saves": 10, "shares": 5, "profile_links_taps": 3}


@pytest.fixture
def ig(monkeypatch):
    fake = install(monkeypatch)
    fake.account_default = dict(DAY)
    return fake


async def _media(db, org, ident="m1", product="FEED", media_type="IMAGE", ago=timedelta(days=2), post=None):
    row = await add_media(db, org, ident, product_type=product, media_type=media_type, post_id=post.id if post else None)
    row.posted_at = NOW - ago
    await db.flush()
    return row


async def _post(db, org, title="SIEM", pillar="education", hooks=("What is a SIEM?",), cta="Save this post.", fmt="image"):
    post = SocialPost(organization_id=org.id, title=title, format=fmt, pillar=pillar, status="published", external_media_id=f"x-{uuid.uuid4().hex[:6]}", content={"hooks": list(hooks), "cta": cta}, artwork={})
    db.add(post)
    await db.flush()
    return post


async def _metrics(db, org, ident, values, synced=None):
    for key, value in values.items():
        db.add(MediaMetric(organization_id=org.id, media_external_id=ident, metric=key, value=value, note=None if value is not None else "n/a", synced_at=synced or NOW))
    await db.flush()


async def _days(db, org, start, count, metric="views", value=100.0, followers=None):
    for i in range(count):
        db.add(AccountDay(organization_id=org.id, day=start + timedelta(days=i), metric=metric, value=value, synced_at=NOW))
    await db.flush()


# ---------------- what the numbers mean ----------------


def test_interactions_exist_only_when_all_four_parts_do():
    assert M.interactions({"likes": 1, "comments": 2, "saved": 3, "shares": 4}) == 10
    assert M.interactions({"likes": 1, "comments": 2, "saved": 3}) is None, "a missing part is not zero"
    assert M.interactions({"likes": 0, "comments": 0, "saved": 0, "shares": 0}) == 0, "a real zero stays a zero"


def test_the_rate_by_reach_needs_reach_and_a_pooled_rate_is_not_an_average_of_percentages():
    assert M.er_reach({"likes": 10, "comments": 0, "saved": 0, "shares": 0, "reach": 0}) is None
    assert M.er_reach({"likes": 10, "comments": 0, "saved": 0, "shares": 0}) is None
    small = {"likes": 5, "comments": 0, "saved": 0, "shares": 0, "reach": 10}  # 50%
    big = {"likes": 10, "comments": 0, "saved": 0, "shares": 0, "reach": 1000}  # 1%
    rate, n = M.pooled_er_reach([small, big, {"likes": 3, "reach": 100}])  # the last has no comments/saves/shares, so it can't count
    assert n == 2 and rate == pytest.approx(15 / 1010), "the pooled rate is total interactions over total reach, not (50% + 1%) / 2"


def test_the_typical_value_is_a_median_and_ignores_missing_values():
    assert M.typical([1, 100, None, 3]) == (3.0, 3)
    assert M.typical([None, None]) == (None, 0)


def test_the_follower_rate_needs_a_follower_count():
    values = {"likes": 5, "comments": 0, "saved": 0, "shares": 0}
    assert M.er_followers(values, None) is None and M.er_followers(values, 100) == pytest.approx(0.05)


def test_every_metric_says_where_it_comes_from_and_whether_it_is_observed_or_calculated():
    for table in (M.ACCOUNT_METRICS, M.POST_METRICS):
        for info in table.values():
            assert info.source and info.period and info.definition and info.kind in (M.OBSERVED, M.CALCULATED)
    assert M.POST_METRICS["er_reach"].kind == M.CALCULATED and M.POST_METRICS["reach"].kind == M.OBSERVED
    text = " ".join((i.definition + " " + (i.limitation or "")).lower() for t in (M.ACCOUNT_METRICS, M.POST_METRICS) for i in t.values())
    assert "who saved" in text or "does not say who" in text, "the saves and shares notes say identities aren't available"


def test_posts_are_described_without_guessing():
    assert hook_kind("What is a SIEM?") == "question" and hook_kind("5 SOC skills") == "number" and hook_kind("Logs lie") == "statement" and hook_kind("") == "unknown"
    assert cta_kind("Save this post for later") == "save" and cta_kind("Tell us in the comments") == "comment" and cta_kind("") == "none" and cta_kind("Stay curious") == "other"
    morning = datetime(2026, 10, 5, 4, 0, tzinfo=timezone.utc)  # 09:30 in India
    assert time_of_day(morning, "Asia/Kolkata").startswith("morning") and time_of_day(None, "Asia/Kolkata") == "unknown" and time_of_day(morning, "Not/AZone").startswith("night")


# ---------------- reading from Instagram ----------------


async def test_a_read_stores_the_profile_the_days_and_the_posts_and_skips_stories(db_session, organization, ig):
    await connected_account(db_session, organization)
    await _media(db_session, organization, "feed1")
    await _media(db_session, organization, "reel1", product="REELS", media_type="VIDEO")
    await _media(db_session, organization, "story1", product="STORY")
    ig.insights = {"feed1": dict(FEED), "reel1": {"views": 5000, "reach": 3000, "likes": 100, "comments": 10, "saved": 40, "shares": 30, "total_interactions": 180, "ig_reels_avg_watch_time": 4200}}
    result = await AnalyticsService(db_session).sync(organization.id, NOW)
    assert result["skipped"] is False and all(s["ok"] for s in result["stages"].values()), result
    days = (await db_session.execute(select(AccountDay).where(AccountDay.organization_id == organization.id))).scalars().all()
    assert {d.metric for d in days if d.day == NOW.date()} == {"followers_count", "follows_count", "media_count"}
    assert {d.day for d in days if d.metric == "views"} == {NOW.date() - timedelta(days=i) for i in range(1, 15)}, "14 completed days, never today (still filling up)"
    asked = [args[0] for name, args in ig.calls if name == "media_insights"]
    assert sorted(asked) == ["feed1", "reel1"], "stories aren't read: Instagram only keeps their figures for 24 hours"
    reel_asked = next(args[1] for name, args in ig.calls if name == "media_insights" and args[0] == "reel1")
    assert "ig_reels_avg_watch_time" in reel_asked and "follows" not in reel_asked
    feed_asked = next(args[1] for name, args in ig.calls if name == "media_insights" and args[0] == "feed1")
    assert "follows" in feed_asked and "ig_reels_avg_watch_time" not in feed_asked


async def test_a_figure_instagram_did_not_give_is_stored_as_unavailable_never_as_zero(db_session, organization, ig):
    await connected_account(db_session, organization)
    await _media(db_session, organization, "feed1")
    ig.insights = {"feed1": {"views": 900, "reach": 600}}  # no likes, saves ...
    ig.account_default = {"views": 800}  # no reach on any day
    await AnalyticsService(db_session).sync(organization.id, NOW)
    rows = {m.metric: m for m in (await db_session.execute(select(MediaMetric).where(MediaMetric.organization_id == organization.id, MediaMetric.media_external_id == "feed1"))).scalars()}
    assert rows["views"].value == 900 and rows["likes"].value is None and rows["likes"].note
    assert not [m for m in rows.values() if m.value == 0], "nothing was turned into a zero"
    assert (await db_session.execute(select(AccountDay).where(AccountDay.organization_id == organization.id, AccountDay.metric == "reach"))).first() is None, "no reach figure means no row"


async def test_a_metric_instagram_refuses_is_asked_for_alone_remembered_and_not_asked_again(db_session, organization, ig):
    account = await connected_account(db_session, organization)
    ig.refuse_account = {"replies"}
    service = AnalyticsService(db_session)
    first = await service.sync(organization.id, NOW)
    assert first["stages"]["account"]["ok"] is True
    await db_session.refresh(account)
    assert account.sync_state["analytics"]["unsupported_account"] == ["replies"]
    stored = {d.metric for d in (await db_session.execute(select(AccountDay).where(AccountDay.organization_id == organization.id, AccountDay.day == NOW.date() - timedelta(days=1)))).scalars()}
    assert "views" in stored and "replies" not in stored, "the others were still read"
    before = ig.count("account_totals")
    await service.sync(organization.id, NOW + timedelta(hours=1))
    later = [args[0] for name, args in ig.calls[before:] if name == "account_totals"]
    assert later and all("replies" not in metrics for metrics in later) and all(len(m) > 1 for m in later), "no more one-by-one probing"


async def test_a_post_metric_instagram_refuses_is_marked_unsupported_for_that_post(db_session, organization, ig):
    await connected_account(db_session, organization)
    await _media(db_session, organization, "feed1")
    ig.insights = {"feed1": dict(FEED)}
    ig.refuse_media = {"follows"}
    await AnalyticsService(db_session).sync(organization.id, NOW)
    rows = {m.metric: m for m in (await db_session.execute(select(MediaMetric).where(MediaMetric.organization_id == organization.id, MediaMetric.media_external_id == "feed1"))).scalars()}
    assert rows["follows"].value is None and "doesn't provide" in rows["follows"].note and rows["reach"].value == 600


async def test_a_temporary_problem_stops_that_stage_without_hiding_the_others(db_session, organization, ig):
    await connected_account(db_session, organization)
    await _media(db_session, organization, "feed1")
    ig.insights = {"feed1": dict(FEED)}
    ig.errors["account_totals"] = [InstagramError("transient", "Instagram is busy.", http_status=503)]
    result = await AnalyticsService(db_session).sync(organization.id, NOW)
    assert result["stages"]["account"] == {"ok": False, "error": "Instagram is busy."}
    assert result["stages"]["profile"]["ok"] and result["stages"]["posts"]["ok"]
    assert ig.count("account_totals") == 1, "a busy Instagram isn't hammered"


async def test_a_rejected_token_marks_the_account_and_stops(db_session, organization, ig):
    account = await connected_account(db_session, organization)
    ig.errors["profile_counts"] = [InstagramError("token", "The access token is no longer valid. Reconnect the account.", code=190, http_status=401)]
    result = await AnalyticsService(db_session).sync(organization.id, NOW)
    assert result["stages"] == {"profile": {"ok": False, "error": "The access token is no longer valid. Reconnect the account."}}
    await db_session.refresh(account)
    assert account.status == "revoked" and ig.count("account_totals") == 0


async def test_a_read_waits_fifteen_minutes_unless_forced_and_respects_a_missing_permission(db_session, organization, ig):
    account = await connected_account(db_session, organization)
    service = AnalyticsService(db_session)
    await service.sync(organization.id, NOW)
    calls = len(ig.calls)
    again = await service.sync(organization.id, NOW + timedelta(minutes=5))
    assert again["skipped"] and "15 minutes" in again["message"] and len(ig.calls) == calls
    assert (await service.sync(organization.id, NOW + timedelta(minutes=5), force=True))["skipped"] is False
    account.capabilities = {**account.capabilities, "insights": "unavailable"}
    blocked = await service.sync(organization.id, NOW + timedelta(hours=2))
    assert blocked["skipped"] and "permission" in blocked["message"]


async def test_nothing_is_read_without_a_usable_connection(db_session, organization, ig):
    with pytest.raises(ConflictError):
        await AnalyticsService(db_session).sync(organization.id, NOW)
    await connected_account(db_session, organization, token_expires_at=NOW - timedelta(days=1))
    with pytest.raises(ConflictError):
        await AnalyticsService(db_session).sync(organization.id, NOW)
    assert ig.calls == []


async def test_the_next_day_only_reads_the_new_days_and_the_last_few_that_may_be_revised(db_session, organization, ig):
    await connected_account(db_session, organization)
    service = AnalyticsService(db_session)
    await service.sync(organization.id, NOW)  # 14 days
    # the latest days are always re-read, so the 28-day window fills over three runs; after that only they are re-read
    await service.sync(organization.id, NOW + timedelta(minutes=20))
    await service.sync(organization.id, NOW + timedelta(minutes=40))
    done = {d for d in (await db_session.execute(select(AccountDay.day).where(AccountDay.organization_id == organization.id, AccountDay.metric == "views"))).scalars()}
    assert len(done) == 28
    ig.calls.clear()
    tomorrow = NOW + timedelta(days=1, minutes=1)
    await service.sync(organization.id, tomorrow)
    asked = sorted(args[1] for name, args in ig.calls if name == "account_totals")
    assert asked == [tomorrow.date() - timedelta(days=i) for i in (3, 2, 1)], "yesterday's figure plus the two before it, which Instagram may still revise"


async def test_recent_posts_are_read_again_after_a_day_old_ones_after_a_week(db_session, organization, ig):
    await connected_account(db_session, organization)
    await _media(db_session, organization, "new", ago=timedelta(days=2))
    await _media(db_session, organization, "old", ago=timedelta(days=60))
    ig.insights = {"new": dict(FEED), "old": dict(FEED)}
    service = AnalyticsService(db_session)
    await service.sync(organization.id, NOW)
    assert ig.count("media_insights") == 2
    await service.sync(organization.id, NOW + timedelta(hours=10), force=True)
    assert ig.count("media_insights") == 2
    await service.sync(organization.id, NOW + timedelta(hours=22), force=True)
    assert [a[0] for n, a in ig.calls if n == "media_insights"].count("new") == 2 and [a[0] for n, a in ig.calls if n == "media_insights"].count("old") == 1
    await service.sync(organization.id, NOW + timedelta(days=8), force=True)
    assert [a[0] for n, a in ig.calls if n == "media_insights"].count("old") == 2


# ---------------- showing what was stored ----------------


async def test_the_overview_gives_totals_coverage_source_and_never_a_zero_for_a_missing_day(db_session, organization):
    today = NOW.date()
    start = today - timedelta(days=7)
    await _days(db_session, organization, start, 3, "views", 100.0)  # only 3 of the last 7 days have a figure
    overview = await AnalyticsService(db_session).overview(organization.id, 7, NOW)
    card = next(c for c in overview["cards"] if c["key"] == "views")
    assert card["value"] == 300 and card["value_kind"] == "total" and (card["days_with_data"], card["days_in_period"]) == (3, 7)
    assert card["kind"] == "observed" and "Instagram" in card["source"] and card["last_synced_at"] and card["limitation"]
    assert [p["value"] for p in card["series"]].count(None) == 4, "missing days are null, not 0"
    assert card["change_vs_previous"] is None, "too little data to compare"
    silent = next(c for c in overview["cards"] if c["key"] == "likes")
    assert silent["value"] is None and silent["days_with_data"] == 0 and silent["series"] and all(p["value"] is None for p in silent["series"])


async def test_reach_is_a_daily_average_because_it_cannot_be_added_across_days(db_session, organization):
    await _days(db_session, organization, NOW.date() - timedelta(days=7), 7, "reach", 200.0)
    card = next(c for c in (await AnalyticsService(db_session).overview(organization.id, 7, NOW))["cards"] if c["key"] == "reach")
    assert card["value"] == 200 and card["value_kind"] == "daily_average" and "can't be added" in card["limitation"]


async def test_a_change_is_only_reported_when_both_periods_are_mostly_covered(db_session, organization):
    today = NOW.date()
    await _days(db_session, organization, today - timedelta(days=14), 7, "views", 100.0)  # the 7 days before
    await _days(db_session, organization, today - timedelta(days=7), 7, "views", 150.0)  # the last 7 days
    card = next(c for c in (await AnalyticsService(db_session).overview(organization.id, 7, NOW))["cards"] if c["key"] == "views")
    assert card["change_vs_previous"] == pytest.approx(0.5) and card["previous_daily_average"] == 100


async def test_follower_change_needs_two_snapshots_and_says_what_it_is(db_session, organization):
    service = AnalyticsService(db_session)
    one = await service.overview(organization.id, 7, NOW)
    assert one["follower_change"]["value"] is None and "two different days" in one["follower_change"]["note"]
    today = NOW.date()
    db_session.add_all([AccountDay(organization_id=organization.id, day=today - timedelta(days=5), metric="followers_count", value=1000, synced_at=NOW), AccountDay(organization_id=organization.id, day=today, metric="followers_count", value=1030, synced_at=NOW)])
    await db_session.flush()
    two = await service.overview(organization.id, 7, NOW)
    assert two["follower_change"]["value"] == 30 and two["follower_change"]["kind"] == "calculated" and "net" in two["follower_change"]["limitation"].lower()
    assert two["snapshots"]["followers_count"]["latest"] == 1030 and two["snapshots"]["followers_count"]["kind"] == "observed"


async def test_post_rows_calculate_rates_from_observed_figures_and_link_back_to_the_erpx_post(db_session, organization):
    post = await _post(db_session, organization, hooks=("What is a SIEM?",), cta="Save this post.")
    await _media(db_session, organization, "m1", post=post)
    await _metrics(db_session, organization, "m1", {"reach": 600, "views": 900, "likes": 40, "comments": 5, "saved": 20, "shares": 5})
    db_session.add(AccountDay(organization_id=organization.id, day=(NOW - timedelta(days=2)).date(), metric="followers_count", value=1000, synced_at=NOW))
    await db_session.flush()
    (row,) = await AnalyticsService(db_session).posts(organization.id)
    assert row["interactions"] == 70 and row["er_reach"] == pytest.approx(70 / 600) and row["er_followers"] == pytest.approx(70 / 1000)
    assert (row["title"], row["pillar"], row["hook"], row["cta"], row["kind"]) == ("SIEM", "education", "question", "save", "image")
    assert row["insights_read"] and row["last_synced_at"]


async def test_a_post_without_its_figures_gets_no_rate_and_a_post_with_zero_reach_gets_none_either(db_session, organization):
    await _media(db_session, organization, "a")
    await _media(db_session, organization, "b")
    await _media(db_session, organization, "c")
    await _metrics(db_session, organization, "b", {"reach": 0, "likes": 3, "comments": 0, "saved": 0, "shares": 0})
    await _metrics(db_session, organization, "c", {"reach": 100, "likes": None, "comments": 0, "saved": 0, "shares": 0})
    rows = {r["external_id"]: r for r in await AnalyticsService(db_session).posts(organization.id)}
    assert rows["a"]["insights_read"] is False and rows["a"]["er_reach"] is None and rows["a"]["metrics"] == {}
    assert rows["b"]["er_reach"] is None, "no division by zero"
    assert rows["c"]["er_reach"] is None and rows["c"]["interactions"] is None, "a missing like count isn't a zero"
    assert rows["c"]["unavailable"].get("likes")


async def test_groups_of_posts_are_labelled_small_use_medians_and_a_pooled_rate(db_session, organization):
    service = AnalyticsService(db_session)
    specs = [("p1", 1000, 100), ("p2", 10, 5), ("p3", 100, 8)]
    for ident, reach, likes in specs:
        await _media(db_session, organization, ident)
        await _metrics(db_session, organization, ident, {"reach": reach, "views": reach * 2, "likes": likes, "comments": 0, "saved": 0, "shares": 0})
    await _media(db_session, organization, "story", product="STORY")
    await _metrics(db_session, organization, "story", {"reach": 99999})
    await _media(db_session, organization, "unread")
    groups = service.breakdown(await service.posts(organization.id), "kind")
    assert [g["label"] for g in groups] == ["image"] and groups[0]["posts"] == 3, "stories and unread posts are left out"
    g = groups[0]
    assert g["median_reach"] == 100 and g["er_reach_pooled"] == pytest.approx(113 / 1110) and g["er_reach_posts"] == 3
    assert g["caution"] == "Too few posts to conclude anything."


async def test_consistency_counts_posting_days_and_the_longest_gap(db_session, organization):
    for ident, ago in (("a", 1), ("b", 2), ("c", 9)):
        await _media(db_session, organization, ident, ago=timedelta(days=ago))
    result = await AnalyticsService(db_session).consistency(organization.id, NOW.date() - timedelta(days=13), NOW.date())
    assert (result["posts"], result["days_with_a_post"], result["days_in_period"], result["longest_gap_days"]) == (3, 3, 14, 7)
    assert result["kind"] == "calculated" and "25 most recent" in result["limitation"]


# ---------------- experiments ----------------


async def _experiment(db, org, user, posts_a, posts_b, metric="reach", **kw):
    data = {"name": "Question vs statement", "hypothesis": "Question hooks get more reach.", "variable": "hook", "metric": metric, "audience": None,
            "variants": [{"label": "Question", "post_ids": [p.id for p in posts_a]}, {"label": "Statement", "post_ids": [p.id for p in posts_b]}]}
    data.update(kw)
    return await ExperimentService(db).create(org.id, user.id, data)


async def _publish_pair(db, org, ident, reach, ago=2):
    post = await _post(db, org, title=f"Post {ident}")
    await _media(db, org, ident, post=post, ago=timedelta(days=ago))
    await _metrics(db, org, ident, {"reach": reach, "views": reach * 2, "likes": 1, "comments": 1, "saved": 1, "shares": 1})
    return post


async def test_an_experiment_with_too_few_posts_concludes_nothing(db_session, organization, superuser):
    a, b = await _publish_pair(db_session, organization, "a1", 500), await _publish_pair(db_session, organization, "b1", 100)
    row = await _experiment(db_session, organization, superuser[0], [a], [b])
    results = await ExperimentService(db_session).results(organization.id, row)
    assert "Not enough yet" in results["reading"] and "Nothing can be concluded" in results["reading"] and "Question (1)" in results["reading"]
    assert results["variants"][0]["median"] == 500 and results["variants"][0]["n"] == 1


async def test_with_enough_posts_it_reports_medians_and_whether_the_posts_overlap_without_naming_a_cause_or_winner(db_session, organization, superuser):
    q = [await _publish_pair(db_session, organization, f"q{i}", r) for i, r in enumerate((300, 500, 700))]
    s = [await _publish_pair(db_session, organization, f"s{i}", r) for i, r in enumerate((100, 200, 400))]
    row = await _experiment(db_session, organization, superuser[0], q, s)
    results = await ExperimentService(db_session).results(organization.id, row)
    assert "Question: median 500 over 3 posts" in results["reading"] and "Statement: median 200 over 3 posts" in results["reading"]
    assert "overlap" in results["reading"] and "ordinary variation" in results["reading"]
    lowered = (results["reading"] + results["caution"]).lower()
    assert "winner" not in lowered and "caused by" not in lowered and "proves" not in lowered.replace("not proof", "").replace("isn't proof", "")
    assert "not proof of cause" in results["caution"]
    s2 = [await _publish_pair(db_session, organization, f"t{i}", r) for i, r in enumerate((10, 20, 30))]
    apart = await _experiment(db_session, organization, superuser[0], q, s2)
    assert "don't overlap" in (await ExperimentService(db_session).results(organization.id, apart))["reading"]


async def test_posts_without_readable_figures_do_not_count_toward_a_variant(db_session, organization, superuser):
    unread = await _post(db_session, organization, title="not read yet")
    await _media(db_session, organization, "u1", post=unread)
    never_posted = await _post(db_session, organization, title="never published")
    other = await _publish_pair(db_session, organization, "o1", 100)
    row = await _experiment(db_session, organization, superuser[0], [unread, never_posted], [other])
    variant = (await ExperimentService(db_session).results(organization.id, row))["variants"][0]
    assert variant["n"] == 0 and variant["median"] is None
    assert [(p["published"], p["insights_read"]) for p in variant["posts"]] == [(True, False), (False, False)]


async def test_experiment_input_is_checked(db_session, organization, superuser):
    a, b = await _publish_pair(db_session, organization, "a1", 5), await _publish_pair(db_session, organization, "b1", 5)
    service = ExperimentService(db_session)
    base = {"name": "x", "hypothesis": "h", "variable": "hook", "metric": "reach", "audience": None}
    cases = [
        ([{"label": "Only one", "post_ids": []}], "two to four"),
        ([{"label": "Same", "post_ids": []}, {"label": "same", "post_ids": []}], "own name"),
        ([{"label": "A", "post_ids": [a.id]}, {"label": "B", "post_ids": [a.id]}], "only belong to one"),
        ([{"label": "A", "post_ids": [uuid.uuid4()]}, {"label": "B", "post_ids": [b.id]}], "doesn't exist"),
    ]
    for variants, text in cases:
        with pytest.raises(ValidationError, match=text):
            await service.create(organization.id, superuser[0].id, {**base, "variants": variants})


async def test_an_experiment_moves_forward_only_and_a_finished_one_keeps_only_its_conclusion_editable(db_session, organization, superuser):
    a, b = await _publish_pair(db_session, organization, "a1", 5), await _publish_pair(db_session, organization, "b1", 5)
    service = ExperimentService(db_session)
    row = await _experiment(db_session, organization, superuser[0], [a], [b])
    assert row.status == "planned" and row.started_on is None
    with pytest.raises(ValidationError, match="can't go from planned to concluded"):
        await service.update(organization.id, row.id, {"status": "concluded"})
    today = date(2026, 10, 10)
    await service.update(organization.id, row.id, {"status": "running"}, today)
    assert row.started_on == today
    await service.update(organization.id, row.id, {"status": "concluded", "conclusion": "Inconclusive: too few posts."}, today + timedelta(days=14))
    assert row.ended_on == today + timedelta(days=14)
    with pytest.raises(ValidationError, match="only have its conclusion edited"):
        await service.update(organization.id, row.id, {"name": "renamed"})
    await service.update(organization.id, row.id, {"conclusion": "Still inconclusive."})
    assert row.conclusion == "Still inconclusive."


# ---------------- reports ----------------


def test_periods_are_whole_weeks_and_months():
    assert last_period("weekly", date(2026, 10, 14)) == (date(2026, 10, 5), date(2026, 10, 11))
    assert last_period("weekly", date(2026, 10, 12)) == (date(2026, 10, 5), date(2026, 10, 11)), "on a Monday, the week that just ended"
    assert last_period("monthly", date(2026, 10, 9)) == (date(2026, 9, 1), date(2026, 9, 30))
    assert last_period("monthly", date(2026, 1, 3)) == (date(2025, 12, 1), date(2025, 12, 31))
    assert period_for("monthly", date(2026, 2, 1)) == (date(2026, 2, 1), date(2026, 2, 28))
    with pytest.raises(ValidationError, match="Monday"):
        period_for("weekly", date(2026, 10, 6))
    with pytest.raises(ValidationError, match="first of a month"):
        period_for("monthly", date(2026, 10, 2))


async def test_a_report_cannot_be_made_for_a_period_that_is_not_over(db_session, organization):
    monday = NOW.date() - timedelta(days=NOW.date().weekday())
    with pytest.raises(ValidationError, match="isn't over yet"):
        await ReportService(db_session).generate(organization.id, "weekly", monday, None, NOW)


async def _week_with_data(db, org):
    start, end = last_period("weekly", NOW.date())
    previous = start - timedelta(days=7)
    await _days(db, org, previous, 7, "views", 100.0)
    await _days(db, org, start, 7, "views", 160.0)
    await _days(db, org, start, 7, "reach", 400.0)
    for i, (ident, reach) in enumerate((("w1", 900), ("w2", 300), ("w3", 120), ("w4", 60))):
        post = await _post(db, org, title=f"Week post {i}", fmt="image" if i % 2 == 0 else "carousel")
        row = await _media(db, org, ident, post=post, media_type="IMAGE" if i % 2 == 0 else "CAROUSEL_ALBUM")
        row.posted_at = datetime.combine(start + timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=9)
        await _metrics(db, org, ident, {"reach": reach, "views": reach * 2, "likes": reach // 10, "comments": 2, "saved": 3, "shares": 1})
    await db.flush()
    return start, end


async def test_a_weekly_report_states_figures_sources_and_findings_from_the_data(db_session, organization):
    start, end = await _week_with_data(db_session, organization)
    row = await ReportService(db_session).generate(organization.id, "weekly", start, None, NOW)
    data = row.data
    assert data["period"] == {"kind": "weekly", "start": start.isoformat(), "end": end.isoformat(), "days": 7}
    views = next(c for c in data["account"]["cards"] if c["key"] == "views")
    assert views["value"] == 160 * 7 and views["days_with_data"] == 7 and views["source"] and views["kind"] == "observed"
    assert views["change_vs_previous"] == pytest.approx(0.6)
    assert [p["reach"] for p in data["posts"]["top"]] == [900, 300, 120] and [p["reach"] for p in data["posts"]["lowest"]] == [60]
    findings = data["findings"]
    assert any("Views per day was 60% higher than the previous 7 days (7 of 7 days had figures)" in w for w in findings["worked"])
    assert any("Highest reach" in w and "900" in w and "typical 210" in w for w in findings["worked"])
    assert any("Lowest reach" in d and "60" in d and "typical 210" in d for d in findings["didnt"])
    assert findings["test_next"], "something to test next is always suggested"
    assert any("does not predict growth" in c for c in data["caveats"]) and any("48 hours" in c for c in data["caveats"])
    assert data["posts"]["er_reach_note"] == M.POOLED_NOTE and data["posts"]["er_reach_posts"] == 4
    likes = next(c for c in data["account"]["cards"] if c["key"] == "likes")
    assert likes["value"] is None and any("No figures at all for" in c and "Likes" in c for c in data["caveats"]), "missing is reported as missing, not zero"


async def test_a_report_with_no_data_says_there_is_not_enough_and_makes_no_claims(db_session, organization):
    start, _ = last_period("weekly", NOW.date())
    data = (await ReportService(db_session).generate(organization.id, "weekly", start, None, NOW)).data
    assert data["findings"]["worked"] == [] and data["findings"]["didnt"] == ["There wasn't enough data to say what worked or didn't. See the notes below."], "no claim that nothing was posted when nothing was read"
    assert all(c["value"] is None for c in data["account"]["cards"])
    assert data["posts"]["top"] == [] and data["posts"]["lowest"] == []
    assert any("Only 0 post(s)" in t for t in data["findings"]["test_next"])
    text = " ".join(data["findings"]["worked"] + data["findings"]["didnt"] + data["findings"]["test_next"]).lower()
    assert not re.search(r"\b(grow|viral|guarantee|will increase)\b", text)


async def test_regenerating_replaces_the_report_for_that_period_instead_of_adding_another(db_session, organization, superuser):
    start, _ = await _week_with_data(db_session, organization)
    service = ReportService(db_session)
    first = await service.generate(organization.id, "weekly", start, None, NOW)
    assert (await service.ensure_latest(organization.id, "weekly", NOW)) is None, "the scheduled run doesn't redo an existing report"
    second = await service.generate(organization.id, "weekly", start, superuser[0].id, NOW + timedelta(hours=1))
    assert second.id == first.id and second.generated_by_user_id == superuser[0].id
    assert len((await db_session.execute(select(Report).where(Report.organization_id == organization.id))).scalars().all()) == 1


async def test_the_schedule_makes_the_last_complete_week_and_month_once(db_session, organization):
    service = ReportService(db_session)
    week = await service.ensure_latest(organization.id, "weekly", NOW)
    month = await service.ensure_latest(organization.id, "monthly", NOW)
    assert week.kind == "weekly" and month.kind == "monthly" and week.generated_by_user_id is None
    assert (week.period_start, week.period_end) == last_period("weekly", NOW.date()) and (month.period_start, month.period_end) == last_period("monthly", NOW.date())
    assert await service.ensure_latest(organization.id, "weekly", NOW) is None and await service.ensure_latest(organization.id, "monthly", NOW) is None


async def test_few_posts_means_no_best_and_worst(db_session, organization):
    start, _ = last_period("weekly", NOW.date())
    for i, reach in enumerate((500, 50)):
        row = await _media(db_session, organization, f"f{i}")
        row.posted_at = datetime.combine(start + timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc)
        await _metrics(db_session, organization, f"f{i}", {"reach": reach})
    data = (await ReportService(db_session).generate(organization.id, "weekly", start, None, NOW)).data
    assert data["posts"]["lowest"] == [], "two posts can't have a meaningful worst"
    assert any("too few to say which format" in t for t in data["findings"]["test_next"])


async def test_posts_with_similar_reach_are_not_called_best_or_worst(db_session, organization):
    start, _ = last_period("weekly", NOW.date())
    for i, reach in enumerate((900, 930, 960, 990)):
        row = await _media(db_session, organization, f"s{i}")
        row.posted_at = datetime.combine(start + timedelta(days=i), datetime.min.time(), tzinfo=timezone.utc)
        await _metrics(db_session, organization, f"s{i}", {"reach": reach})
    findings = (await ReportService(db_session).generate(organization.id, "weekly", start, None, NOW)).data["findings"]
    assert any("Reach was similar across the 4 posts" in w for w in findings["worked"])
    assert not any("Lowest reach" in d for d in findings["didnt"]) and not any("Highest reach" in w for w in findings["worked"])


# ---------------- through the API ----------------


async def _limited_user(client, db_session, organization, rbac_seeded, perms):
    from modules.authorization.service import AuthorizationService

    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"a-{uuid.uuid4().hex[:6]}@erpx.example.com")
    service = AuthorizationService(db_session)
    role = await service.create_role(organization.id, "Analyst", f"an-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, perms)
    await service.assign_role(user.id, role.id, organization.id, None)
    return {"Authorization": f"Bearer {token}"}


async def test_the_analytics_screens_are_readable_with_view_but_reading_instagram_and_writing_need_manage(client, auth_headers, db_session, organization, rbac_seeded, ig):
    await connected_account(db_session, organization)
    viewer = await _limited_user(client, db_session, organization, rbac_seeded, ["social_media.view"])
    for path in ("analytics/status", "analytics/overview", "analytics/posts", "analytics/metrics", "experiments", "reports"):
        assert (await client.get(f"{_BASE}/{path}", headers=viewer)).status_code == 200, path
        assert (await client.get(f"{_BASE}/{path}")).status_code == 401
    assert (await client.post(f"{_BASE}/analytics/sync", headers=viewer)).status_code == 403
    assert (await client.post(f"{_BASE}/reports", json={"kind": "weekly"}, headers=viewer)).status_code == 403
    body = {"name": "x", "hypothesis": "h", "variable": "hook", "metric": "reach", "variants": [{"label": "A"}, {"label": "B"}]}
    assert (await client.post(f"{_BASE}/experiments", json=body, headers=viewer)).status_code == 403
    assert ig.calls == []
    assert (await client.post(f"{_BASE}/experiments", json=body, headers=auth_headers)).status_code == 201


async def test_a_read_from_the_screen_stores_what_instagram_says_and_the_screens_show_it(client, auth_headers, db_session, organization, ig):
    await connected_account(db_session, organization)
    await _media(db_session, organization, "feed1")
    ig.insights = {"feed1": dict(FEED)}
    sync = await client.post(f"{_BASE}/analytics/sync", headers=auth_headers)
    assert sync.status_code == 200 and sync.json()["skipped"] is False
    again = await client.post(f"{_BASE}/analytics/sync", headers=auth_headers)
    assert again.json()["skipped"] is True
    status = (await client.get(f"{_BASE}/analytics/status", headers=auth_headers)).json()
    assert status["connected"] and status["can_read"] and status["last_sync_at"] and status["stages"]["posts"]["ok"]
    posts = (await client.get(f"{_BASE}/analytics/posts", headers=auth_headers)).json()
    assert posts["items"][0]["metrics"]["reach"] == 600 and posts["items"][0]["er_reach"] == pytest.approx(70 / 600)
    assert set(posts["breakdowns"]) == {"kind", "pillar", "hook", "cta", "time_of_day"}
    overview = (await client.get(f"{_BASE}/analytics/overview", params={"days": 7}, headers=auth_headers)).json()
    assert overview["period"]["days"] == 7 and overview["snapshots"]["followers_count"]["latest"] == 1200 and overview["notes"]
    assert (await client.get(f"{_BASE}/analytics/overview", params={"days": 90}, headers=auth_headers)).status_code == 422, "only the days ERPX can hold figures for"


async def test_a_report_and_an_experiment_round_trip_through_the_api(client, auth_headers, db_session, organization, superuser):
    start, _ = await _week_with_data(db_session, organization)
    made = await client.post(f"{_BASE}/reports", json={"kind": "weekly", "period_start": start.isoformat()}, headers=auth_headers)
    assert made.status_code == 200, made.text
    report = made.json()
    assert report["kind"] == "weekly" and report["automatic"] is False and report["generated_by"] == superuser[0].full_name and report["data"]["findings"]
    assert (await client.get(f"{_BASE}/reports/{report['id']}", headers=auth_headers)).json()["id"] == report["id"]
    assert [r["id"] for r in (await client.get(f"{_BASE}/reports", params={"kind": "weekly"}, headers=auth_headers)).json()] == [report["id"]]
    assert (await client.get(f"{_BASE}/reports", params={"kind": "yearly"}, headers=auth_headers)).status_code == 422
    unfinished = await client.post(f"{_BASE}/reports", json={"kind": "weekly", "period_start": (NOW.date() - timedelta(days=NOW.date().weekday())).isoformat()}, headers=auth_headers)
    assert unfinished.status_code == 422 and "isn't over yet" in unfinished.text

    a, b = await _publish_pair(db_session, organization, "ea", 10), await _publish_pair(db_session, organization, "eb", 20)
    body = {"name": "Q vs S", "hypothesis": "h", "variable": "hook", "metric": "reach", "variants": [{"label": "A", "post_ids": [str(a.id)]}, {"label": "B", "post_ids": [str(b.id)]}]}
    created = (await client.post(f"{_BASE}/experiments", json=body, headers=auth_headers)).json()
    detail = (await client.get(f"{_BASE}/experiments/{created['id']}", headers=auth_headers)).json()
    assert "Not enough yet" in detail["results"]["reading"] and detail["experiment"]["status"] == "planned"
    moved = await client.patch(f"{_BASE}/experiments/{created['id']}", json={"status": "running"}, headers=auth_headers)
    assert moved.json()["status"] == "running" and moved.json()["started_on"]
    assert (await client.delete(f"{_BASE}/experiments/{created['id']}", headers=auth_headers)).status_code == 204
    assert (await client.get(f"{_BASE}/experiments/{created['id']}", headers=auth_headers)).status_code == 404


async def test_insights_count_as_verified_only_after_a_real_figure_was_stored(client, auth_headers, db_session, organization, ig):
    await connected_account(db_session, organization)

    async def verified():
        data = (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()
        return next(c for c in data["capabilities"] if c["key"] == "insights")["verified_live"]

    assert await verified() is False
    await client.post(f"{_BASE}/analytics/sync", headers=auth_headers)
    assert await verified() is True


async def test_the_overview_mentions_a_fresh_weekly_report(client, auth_headers, db_session, organization, ig):
    await connected_account(db_session, organization)
    await ReportService(db_session).ensure_latest(organization.id, "weekly", datetime.now(timezone.utc))
    briefing = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()["briefing"]
    assert any("weekly report" in b["message"] and b["link"] == "reports" for b in briefing)


# ---------------- the schedule and the guarantees ----------------


def test_the_daily_read_and_report_tasks_are_scheduled_after_each_other():
    from app.core.celery_app import celery_app
    from modules.social_media import tasks  # noqa: F401  (registers the tasks)

    celery_app.loader.import_default_modules()
    schedule = celery_app.conf.beat_schedule
    assert schedule["social-sync-insights"]["task"] == "social.sync_insights" and schedule["social-make-reports"]["task"] == "social.make_reports"
    assert schedule["social-sync-insights"]["schedule"].hour == {2} and schedule["social-make-reports"]["schedule"].hour == {3}
    assert {"social.sync_insights", "social.make_reports"} <= set(celery_app.tasks)


MODULE = Path(__file__).resolve().parents[2] / "modules" / "social_media"


def test_nothing_in_analytics_uses_an_ai_or_can_post_anything():
    for name in ("analytics.py", "reports.py", "experiments.py", "metrics.py", "analytics_routes.py"):
        source = (MODULE / name).read_text(encoding="utf-8")
        assert "get_ai_client" not in source and "packages.ai" not in source, f"{name} must stay rule-based: reports describe stored figures only"
        assert not re.search(r"\.(reply_to_comment|send_message|publish|create_image_container)\(", source), f"{name} must only read from Instagram"
    client_source = (MODULE / "instagram.py").read_text(encoding="utf-8")
    for method in ("profile_counts", "account_totals", "media_insights"):
        body = client_source.split(f"async def {method}")[1].split("async def ")[0]
        assert '"GET"' in body and '"POST"' not in body, f"{method} is read only"
