"""
A small client for Instagram's content-publishing API ("Instagram API with Instagram Login", graph.instagram.com).

Written from Meta's published documentation and NOT yet exercised against a live account: every response shape is
handled defensively, and anything unexpected is reported as an error rather than assumed to have worked.

Publishing is two steps: create a media "container" (Instagram downloads the image from a public address), then publish
the container. The first step can be repeated safely (an unused container just expires). The second creates the post and
must never be repeated blindly, so errors are sorted into four kinds the publisher treats differently:

- transient  : try again later (rate limit, server error, timeout while only creating or reading)
- permanent  : retrying won't help (the image was rejected, a permission is missing); needs a person
- token      : the access token is expired or revoked; the account must be reconnected
- ambiguous  : the request may or may not have reached Instagram (a timeout while publishing); must be checked, never retried

The access token is sent in an Authorization header, never in a URL, so it can't appear in logs.
"""

from dataclasses import dataclass
from datetime import datetime

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

TIMEOUT = 30.0
# Graph API error codes: https://developers.facebook.com/docs/graph-api/guides/error-handling
TOKEN_CODES = {190}
TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 368, 613}
PERMISSION_CODES = {10, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219}
STATUS_FINISHED = "FINISHED"
STATUS_PUBLISHED = "PUBLISHED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_FAILED = {"ERROR", "EXPIRED"}


class InstagramError(Exception):
    def __init__(self, kind: str, message: str, code: int | None = None, subcode: int | None = None, http_status: int | None = None):
        super().__init__(message)
        self.kind = kind  # transient | permanent | token | ambiguous
        self.message = message
        self.code = code
        self.subcode = subcode
        self.http_status = http_status


@dataclass
class PublishLimit:
    used: int | None
    total: int | None

    @property
    def exhausted(self) -> bool:
        return self.used is not None and self.total is not None and self.used >= self.total


def _scrub(text: str, token: str) -> str:
    return text.replace(token, "[token]")[:300] if token else text[:300]


def classify(http_status: int, body: dict | None) -> tuple[str, str, int | None, int | None]:
    """(kind, a message safe to show, code, subcode) for an error answer."""
    error = (body or {}).get("error") if isinstance(body, dict) else None
    error = error if isinstance(error, dict) else {}
    code, subcode = error.get("code"), error.get("error_subcode")
    message = str(error.get("error_user_msg") or error.get("message") or f"Instagram answered with status {http_status}.")
    if code in TOKEN_CODES or http_status == 401:
        return "token", "Instagram says the access token is no longer valid. Reconnect the account.", code, subcode
    if http_status == 429 or http_status >= 500 or error.get("is_transient") is True or code in TRANSIENT_CODES:
        return "transient", message, code, subcode
    if code in PERMISSION_CODES or http_status == 403:
        return "permanent", f"Instagram refused for lack of permission: {message}", code, subcode
    return "permanent", message, code, subcode


class InstagramClient:
    def __init__(self, ig_user_id: str, token: str):
        self.ig_user_id = ig_user_id
        self._token = token
        self.base = f"{settings.INSTAGRAM_GRAPH_BASE_URL.rstrip('/')}/{settings.INSTAGRAM_GRAPH_VERSION}"

    async def _request(self, method: str, path: str, data: dict | None = None, params: dict | None = None, publishing: bool = False, json_body: dict | None = None) -> dict:
        """One call. `publishing=True` marks the call that creates the post: a timeout there is "ambiguous", not "transient"."""
        headers = {"Authorization": f"Bearer {self._token}"}
        extra = {"json": json_body} if json_body is not None else {}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.request(method, f"{self.base}/{path.lstrip('/')}", data=data, params=params, headers=headers, **extra)
        except httpx.TimeoutException:
            if publishing:
                raise InstagramError("ambiguous", "Instagram didn't answer in time, so it isn't known whether the post was created.") from None
            raise InstagramError("transient", "Instagram didn't answer in time.") from None
        except httpx.HTTPError as exc:
            if publishing:
                # A connection that broke after the request was sent could still have created the post.
                raise InstagramError("ambiguous", f"The connection to Instagram broke ({type(exc).__name__}), so it isn't known whether the post was created.") from None
            raise InstagramError("transient", f"Instagram couldn't be reached ({type(exc).__name__}).") from None
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            kind, message, code, subcode = classify(response.status_code, body)
            if publishing and kind == "transient" and response.status_code >= 500:
                # A server error from the publishing call doesn't prove nothing was created.
                kind = "ambiguous"
                message = "Instagram answered with a server error while publishing, so it isn't known whether the post was created."
            raise InstagramError(kind, _scrub(message, self._token), code, subcode, response.status_code)
        if not isinstance(body, dict):
            raise InstagramError("ambiguous" if publishing else "transient", "Instagram's answer couldn't be read.", http_status=response.status_code)
        return body

    # ---------------- containers (safe to repeat) ----------------

    async def create_image_container(self, image_url: str, caption: str | None = None, alt_text: str | None = None, story: bool = False, carousel_item: bool = False) -> str:
        data: dict = {"image_url": image_url}
        if story:
            data["media_type"] = "STORIES"
        if carousel_item:
            data["is_carousel_item"] = "true"
        elif caption:
            data["caption"] = caption
        if alt_text and not story:
            data["alt_text"] = alt_text
        result = await self._request("POST", f"{self.ig_user_id}/media", data=data)
        return self._id(result)

    async def create_carousel_container(self, children: list[str], caption: str) -> str:
        data = {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}
        return self._id(await self._request("POST", f"{self.ig_user_id}/media", data=data))

    async def container_status(self, container_id: str) -> str:
        result = await self._request("GET", container_id, params={"fields": "status_code"})
        return str(result.get("status_code") or "")

    # ---------------- publishing (never repeated blindly) ----------------

    async def publish(self, creation_id: str) -> str:
        result = await self._request("POST", f"{self.ig_user_id}/media_publish", data={"creation_id": creation_id}, publishing=True)
        return self._id(result, publishing=True)

    # ---------------- the account ----------------

    async def me(self) -> dict:
        """The connected account: its id, username and account type (BUSINESS / MEDIA_CREATOR)."""
        return await self._request("GET", "me", params={"fields": "user_id,username,account_type"})

    async def list_conversations(self, limit: int = 1) -> list[dict]:
        result = await self._request("GET", f"{self.ig_user_id}/conversations", params={"platform": "instagram", "limit": limit})
        items = result.get("data")
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []

    async def subscribe_webhooks(self, fields: list[str]) -> bool:
        """Ask Instagram to send this account's notifications (comments, messages) to the app's webhook."""
        result = await self._request("POST", f"{self.ig_user_id}/subscribed_apps", data={"subscribed_fields": ",".join(fields)})
        return result.get("success") is True

    async def unsubscribe_webhooks(self) -> bool:
        result = await self._request("DELETE", f"{self.ig_user_id}/subscribed_apps")
        return result.get("success") is True

    # ---------------- reading the profile: media, comments, conversations ----------------

    @staticmethod
    def _page(result: dict) -> tuple[list[dict], str | None]:
        items = result.get("data")
        rows = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
        paging = result.get("paging") if isinstance(result.get("paging"), dict) else {}
        cursors = paging.get("cursors") if isinstance(paging.get("cursors"), dict) else {}
        after = cursors.get("after") if paging.get("next") else None  # a cursor with no "next" page is the end
        return rows, str(after) if after else None

    async def media_page(self, limit: int = 25, after: str | None = None) -> tuple[list[dict], str | None]:
        params = {"fields": "id,caption,media_type,media_product_type,permalink,thumbnail_url,media_url,timestamp,comments_count", "limit": limit}
        if after:
            params["after"] = after
        return self._page(await self._request("GET", f"{self.ig_user_id}/media", params=params))

    async def list_comments(self, media_id: str, after: str | None = None, limit: int = 50) -> tuple[list[dict], str | None]:
        """Top-level comments on a post (with their replies where Instagram allows expanding them). The fuller field list
        is tried first; Instagram's documentation only guarantees id, text and timestamp, so if the fuller list is
        refused the plain one is used and whatever is missing (who wrote it) is simply shown as not provided."""
        rich = "id,text,timestamp,username,from,like_count,hidden,replies{id,text,timestamp,username,from}"
        for fields in (rich, "id,text,timestamp"):
            params = {"fields": fields, "limit": limit}
            if after:
                params["after"] = after
            try:
                return self._page(await self._request("GET", f"{media_id}/comments", params=params))
            except InstagramError as exc:
                if fields != rich or exc.kind != "permanent" or exc.code not in (100, 12, None):
                    raise
        return [], None

    async def list_replies(self, comment_id: str) -> list[dict]:
        try:
            rows, _ = self._page(await self._request("GET", f"{comment_id}/replies", params={"fields": "id,text,timestamp,username,from"}))
        except InstagramError as exc:
            if exc.kind != "permanent" or exc.code not in (100, 12, None):
                raise
            rows, _ = self._page(await self._request("GET", f"{comment_id}/replies", params={"fields": "id,text,timestamp"}))
        return rows

    async def conversations_page(self, limit: int = 25, after: str | None = None) -> tuple[list[dict], str | None]:
        params = {"platform": "instagram", "limit": limit}
        if after:
            params["after"] = after
        return self._page(await self._request("GET", f"{self.ig_user_id}/conversations", params=params))

    async def conversation_message_ids(self, conversation_id: str) -> list[dict]:
        """The ids (and times) of a conversation's messages, newest first."""
        result = await self._request("GET", conversation_id, params={"fields": "messages"})
        messages = result.get("messages") if isinstance(result.get("messages"), dict) else {}
        rows = messages.get("data")
        return [m for m in rows if isinstance(m, dict) and m.get("id")] if isinstance(rows, list) else []

    async def get_message(self, message_id: str) -> dict:
        """One message. Instagram only returns the 20 most recent per conversation; an older one answers with an error."""
        return await self._request("GET", message_id, params={"fields": "id,created_time,from,to,message"})

    # ---------------- sending: only ever called after a person pressed Send (see replies.py) ----------------

    async def reply_to_comment(self, comment_id: str, message: str) -> str:
        """Post a public reply to a comment. A timeout here is "ambiguous": it may have been posted."""
        result = await self._request("POST", f"{comment_id}/replies", data={"message": message}, publishing=True)
        return self._id(result, publishing=True)

    async def send_message(self, recipient_id: str, text: str) -> str:
        """Send a direct message (only possible within 24 hours of the person's last message). Ambiguous on timeout."""
        result = await self._request(
            "POST", f"{self.ig_user_id}/messages", json_body={"recipient": {"id": recipient_id}, "message": {"text": text}}, publishing=True
        )
        value = result.get("message_id") or result.get("id")
        if not value:
            raise InstagramError("ambiguous", "Instagram's answer had no message id, so it isn't known whether the message was sent.")
        return str(value)

    # ---------------- reading ----------------

    # ---------------- insights (read only; a missing value is never turned into zero) ----------------

    async def profile_counts(self) -> dict[str, int]:
        """followers_count, follows_count and media_count as Instagram reports them right now (only the ones it returned)."""
        result = await self._request("GET", "me", params={"fields": "followers_count,follows_count,media_count"})
        return {k: int(result[k]) for k in ("followers_count", "follows_count", "media_count") if isinstance(result.get(k), (int, float)) and not isinstance(result.get(k), bool)}

    async def account_totals(self, metrics: list[str], since: datetime, until: datetime) -> dict[str, float]:
        """One total per metric over the range (Instagram's `total_value`). A metric Instagram leaves out is left out here."""
        result = await self._request(
            "GET", f"{self.ig_user_id}/insights",
            params={"metric": ",".join(metrics), "metric_type": "total_value", "period": "day", "since": int(since.timestamp()), "until": int(until.timestamp())},
        )
        out: dict[str, float] = {}
        for metric in result.get("data") or []:
            total = metric.get("total_value") if isinstance(metric, dict) else None
            if isinstance(total, dict) and isinstance(total.get("value"), (int, float)) and not isinstance(total.get("value"), bool) and metric.get("name"):
                out[str(metric["name"])] = float(total["value"])
        return out

    async def media_insights(self, media_id: str, metrics: list[str]) -> dict[str, float]:
        """Lifetime figures for one post. Metrics Instagram doesn't return are absent (unavailable), never 0."""
        result = await self._request("GET", f"{media_id}/insights", params={"metric": ",".join(metrics)})
        out: dict[str, float] = {}
        for metric in result.get("data") or []:
            if not isinstance(metric, dict) or not metric.get("name"):
                continue
            values = metric.get("values") or []
            value = values[0].get("value") if values and isinstance(values[0], dict) else (metric.get("total_value") or {}).get("value")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[str(metric["name"])] = float(value)
        return out

    async def media_permalink(self, media_id: str) -> str | None:
        result = await self._request("GET", media_id, params={"fields": "permalink"})
        link = result.get("permalink")
        return str(link) if link else None

    async def recent_media(self, limit: int = 20) -> list[dict]:
        result = await self._request("GET", f"{self.ig_user_id}/media", params={"fields": "id,caption,permalink,timestamp,media_product_type", "limit": limit})
        items = result.get("data")
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []

    async def publishing_limit(self) -> PublishLimit:
        result = await self._request("GET", f"{self.ig_user_id}/content_publishing_limit", params={"fields": "quota_usage,config"})
        entry = (result.get("data") or [{}])[0] if isinstance(result.get("data"), list) else {}
        config = entry.get("config") or {}
        used, total = entry.get("quota_usage"), config.get("quota_total")
        return PublishLimit(used if isinstance(used, int) else None, total if isinstance(total, int) else None)

    @staticmethod
    def _id(result: dict, publishing: bool = False) -> str:
        value = result.get("id")
        if not value:
            raise InstagramError("ambiguous" if publishing else "transient", "Instagram's answer had no id.")
        return str(value)


def get_instagram_client(ig_user_id: str, token: str) -> InstagramClient:
    """The one place a client is made, so tests can replace it."""
    return InstagramClient(ig_user_id, token)
