"""
What every number on the analytics screens means.

Rules the rest of the module follows:
- a value Instagram didn't give is absent (None), never zero
- every metric says where it comes from, which period it covers, and whether it was observed (Instagram's own figure) or
  calculated (ERPX combined observed figures)
- rates are only calculated from figures covering the same posts and period, and say what they were divided by; two rates with
  different denominators are never merged into one
- nothing here claims to know who saved or shared a post: Instagram doesn't give that
"""

from dataclasses import dataclass
from statistics import median

OBSERVED = "observed"
CALCULATED = "calculated"

DATA_DELAY_NOTE = "Instagram says figures can be delayed by up to 48 hours, so the most recent days may still change."


@dataclass(frozen=True)
class MetricInfo:
    key: str
    label: str
    scope: str  # account | post
    kind: str  # observed | calculated
    source: str
    period: str
    definition: str
    limitation: str | None = None


def _account(key: str, label: str, definition: str, limitation: str | None = None, source: str | None = None) -> MetricInfo:
    return MetricInfo(key, label, "account", OBSERVED, source or f"Instagram account insights: {key}", "per day (Instagram's own day boundary)", definition, limitation)


def _post(key: str, label: str, definition: str, limitation: str | None = None) -> MetricInfo:
    return MetricInfo(key, label, "post", OBSERVED, f"Instagram media insights: {key}", "lifetime of the post, as of the last read", definition, limitation)


ACCOUNT_METRICS = {
    m.key: m
    for m in (
        MetricInfo("followers_count", "Followers", "account", OBSERVED, "Instagram profile: followers_count", "snapshot when ERPX read it", "How many accounts follow the profile at the moment it was read.", "ERPX only has snapshots from the day it started reading, so earlier history isn't available."),
        MetricInfo("follows_count", "Following", "account", OBSERVED, "Instagram profile: follows_count", "snapshot when ERPX read it", "How many accounts the profile follows."),
        MetricInfo("media_count", "Posts on the profile", "account", OBSERVED, "Instagram profile: media_count", "snapshot when ERPX read it", "How many posts the profile has."),
        _account("reach", "Accounts reached", "The number of different accounts that saw any of the profile's content that day.", "Estimated by Instagram. Days can't be added together to give a period reach, because the same account may be counted on several days."),
        _account("views", "Views", "How many times content was played or displayed. Repeat views by the same account are counted.", "Instagram marks this metric as still in development."),
        _account("accounts_engaged", "Accounts engaged", "Accounts that interacted with the content (likes, saves, comments, shares, replies).", "Estimated by Instagram."),
        _account("total_interactions", "Interactions", "Instagram's own total of interactions on the profile's content.", "Instagram's page doesn't spell out exactly which kinds of interaction are included."),
        _account("likes", "Likes", "Likes on the profile's content."),
        _account("comments", "Comments", "Comments on the profile's content."),
        _account("saves", "Saves", "How many times content was saved. Instagram does not say who saved it."),
        _account("shares", "Shares", "How many times content was shared. Instagram does not say who shared it."),
        _account("replies", "Story replies", "Replies to stories.", "Instagram returns 0 for people in Europe and Japan, so a zero here isn't proof of no replies."),
        _account("reposts", "Reposts", "How many times content was reposted."),
        _account("profile_links_taps", "Profile link taps", "Taps on the profile's contact buttons and link.", "Not broken down by link."),
        MetricInfo("follower_change", "Follower change", "account", CALCULATED, "ERPX: last snapshot minus first snapshot in the period", "the chosen period", "Followers at the end minus followers at the start, from ERPX's own snapshots.", "Only shown when there are snapshots near both ends. A net figure: it can't separate new followers from unfollows."),
    )
}

# What Instagram offers per kind of post, in the order shown. Stories vanish after 24 hours and are not tracked here.
FEED_METRICS = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions", "follows", "profile_visits"]
REEL_METRICS = ["views", "reach", "likes", "comments", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]

POST_METRICS = {
    m.key: m
    for m in (
        _post("views", "Views", "How many times the post was played or displayed, repeats included.", "Instagram marks this metric as still in development."),
        _post("reach", "Accounts reached", "The number of different accounts that saw the post.", "Estimated by Instagram."),
        _post("likes", "Likes", "Likes on the post."),
        _post("comments", "Comments", "Comments on the post."),
        _post("saved", "Saves", "How many times the post was saved. Instagram does not say who saved it."),
        _post("shares", "Shares", "How many times the post was shared. Instagram does not say who shared it."),
        _post("total_interactions", "Interactions (Instagram's figure)", "Instagram's own total of interactions on the post.", "Instagram marks this as in development. ERPX's own sum (likes + comments + saves + shares) is used for rates so the parts are known."),
        _post("follows", "Follows from the post", "Accounts that followed the profile from this post.", "Not available for reels."),
        _post("profile_visits", "Profile visits from the post", "Visits to the profile from this post.", "Not available for reels."),
        _post("ig_reels_avg_watch_time", "Average watch time (reels)", "Average time people watched the reel, in milliseconds.", "Reels only."),
        _post("ig_reels_video_view_total_time", "Total watch time (reels)", "Total time people spent watching the reel, in milliseconds.", "Reels only. Instagram marks this as in development."),
        MetricInfo("interactions", "Interactions (likes + comments + saves + shares)", "post", CALCULATED, "ERPX: likes + comments + saved + shares", "lifetime of the post", "The four interaction counts added together.", "Missing unless all four were available. Reposts are not included."),
        MetricInfo("er_reach", "Engagement rate by reach", "post", CALCULATED, "ERPX: interactions ÷ reach", "lifetime of the post", "Interactions divided by the accounts reached by that post.", "Reach is estimated. Only shown when reach is above zero. Not comparable with a rate divided by followers."),
        MetricInfo("er_followers", "Engagement rate by followers", "post", CALCULATED, "ERPX: interactions ÷ followers on the nearest snapshot day", "lifetime of the post", "Interactions divided by the follower count ERPX recorded on the day nearest the post (within three days).", "Only shown when such a snapshot exists. Followers who saw nothing still count, so this is lower than the rate by reach."),
    )
}

# Plain-language rules for how a rate over several posts is formed, so it is never an unexplained average.
POOLED_NOTE = "Over several posts the rate is the total interactions divided by the total reach of those same posts (not an average of percentages), counting only posts where both figures exist."


def interactions(values: dict[str, float | None]) -> float | None:
    parts = [values.get(k) for k in ("likes", "comments", "saved", "shares")]
    return None if any(p is None for p in parts) else float(sum(parts))  # type: ignore[arg-type]


def er_reach(values: dict[str, float | None]) -> float | None:
    total, reach = interactions(values), values.get("reach")
    return None if total is None or not reach else total / reach


def er_followers(values: dict[str, float | None], followers: float | None) -> float | None:
    total = interactions(values)
    return None if total is None or not followers else total / followers


def pooled_er_reach(rows: list[dict[str, float | None]]) -> tuple[float | None, int]:
    """(rate, number of posts used): total interactions ÷ total reach over the posts that have both."""
    usable = [(interactions(r), r.get("reach")) for r in rows]
    usable = [(i, r) for i, r in usable if i is not None and r]
    if not usable:
        return None, 0
    return sum(i for i, _ in usable) / sum(r for _, r in usable), len(usable)


def typical(values: list[float | None]) -> tuple[float | None, int]:
    """(median, count of posts that have a value). A median is used because one viral post would drag an average."""
    present = [v for v in values if v is not None]
    return (float(median(present)) if present else None), len(present)


def describe(metric: str, scope: str) -> MetricInfo | None:
    return (ACCOUNT_METRICS if scope == "account" else POST_METRICS).get(metric)
