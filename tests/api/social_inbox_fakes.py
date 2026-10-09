"""A scripted Instagram for the inbox and reply tests, plus helpers that build connected accounts and inbox rows."""

import uuid
from datetime import datetime, timedelta, timezone

from modules.social_media import instagram
from modules.social_media.instagram import InstagramError
from modules.social_media.models import IgComment, IgConversation, IgMedia, IgMessage, SocialAccount
from modules.social_media.token_crypto import encrypt_token

OWN_ID = "17841400000000000"
OWN_NAME = "pentrix"
NOW = datetime.now(timezone.utc).replace(microsecond=0)


def iso(at: datetime) -> str:
    return at.strftime("%Y-%m-%dT%H:%M:%S+0000")


class FakeInbox:
    """`errors[method]` is a list consumed in order (None = succeed). Anything not scripted answers with empty data."""

    def __init__(self):
        self.media: list[dict] = []
        self.comment_pages: dict[str, list[list[dict]]] = {}
        self.replies: dict[str, list[dict]] = {}
        self.conversations: list[dict] = []
        self.message_ids: dict[str, list[dict]] = {}
        self.messages: dict[str, dict] = {}
        self.errors: dict[str, list] = {}
        self.calls: list[tuple[str, tuple]] = []
        self.sent_comment_replies: list[tuple[str, str]] = []
        self.sent_messages: list[tuple[str, str]] = []
        self.on_send = None  # called with ("comment"|"dm", text) just before a send answers (to look at the database)
        self.counter = 0

    def count(self, name: str) -> int:
        return sum(1 for method, _ in self.calls if method == name)

    def _go(self, name: str, *args):
        self.calls.append((name, args))
        queue = self.errors.get(name)
        if queue:
            error = queue.pop(0)
            if error:
                raise error

    # ---- reading ----
    async def media_page(self, limit=25, after=None):
        self._go("media_page")
        return self.media, None

    async def list_comments(self, media_id, after=None, limit=50):
        self._go("list_comments", media_id, after)
        pages = self.comment_pages.get(media_id) or [[]]
        index = int(after or 0)
        return pages[index], (str(index + 1) if index + 1 < len(pages) else None)

    async def list_replies(self, comment_id):
        self._go("list_replies", comment_id)
        return self.replies.get(comment_id, [])

    async def conversations_page(self, limit=25, after=None):
        self._go("conversations_page")
        return self.conversations, None

    async def conversation_message_ids(self, conversation_id):
        self._go("conversation_message_ids", conversation_id)
        return self.message_ids.get(conversation_id, [])

    async def get_message(self, message_id):
        self._go("get_message", message_id)
        if message_id not in self.messages:
            raise InstagramError("permanent", "This message has been deleted.", code=100, http_status=400)
        return self.messages[message_id]

    # ---- sending (only ever reached through replies.py) ----
    async def reply_to_comment(self, comment_id, message):
        if self.on_send:
            await self.on_send("comment", message)
        self._go("reply_to_comment", comment_id, message)
        self.sent_comment_replies.append((comment_id, message))
        self.counter += 1
        return f"reply-{self.counter}"

    async def send_message(self, recipient_id, text):
        if self.on_send:
            await self.on_send("dm", text)
        self._go("send_message", recipient_id, text)
        self.sent_messages.append((recipient_id, text))
        self.counter += 1
        return f"mid-sent-{self.counter}"


def install(monkeypatch) -> FakeInbox:
    fake = FakeInbox()
    monkeypatch.setattr(instagram, "get_instagram_client", lambda ig_user_id, token: fake)
    return fake


# ---------------- builders ----------------


def media_item(ident="m1", caption="What is a SIEM?", comments=2, at=None, **kw):
    return {"id": ident, "caption": caption, "media_type": "IMAGE", "media_product_type": "FEED", "permalink": f"https://www.instagram.com/p/{ident}/",
            "thumbnail_url": f"https://cdn.example/{ident}.jpg", "timestamp": iso(at or NOW - timedelta(days=1)), "comments_count": comments, **kw}


def comment_item(ident, text, username="asha", author_id="900", at=None, replies=None, **kw):
    item = {"id": ident, "text": text, "username": username, "from": {"id": author_id, "username": username}, "timestamp": iso(at or NOW - timedelta(hours=2)), **kw}
    if replies is not None:
        item["replies"] = {"data": replies}
    return item


def message_detail(ident, text, sender_id="900", sender="asha", at=None):
    return {"id": ident, "created_time": iso(at or NOW - timedelta(hours=1)), "from": {"id": sender_id, "username": sender}, "to": {"data": [{"id": OWN_ID if sender_id != OWN_ID else "900", "username": OWN_NAME}]}, "message": text}


async def connected_account(db_session, organization, **kw) -> SocialAccount:
    values = dict(
        organization_id=organization.id, external_account_id=OWN_ID, username=OWN_NAME, account_type="BUSINESS", status="connected",
        token_encrypted=encrypt_token("tok"), token_expires_at=NOW + timedelta(days=50), connected_at=NOW - timedelta(days=5),
        scopes=[], capabilities={"publish": "available", "comments": "available", "messages": "available", "insights": "available", "webhooks": "subscribed"},
    )
    values.update(kw)
    account = SocialAccount(**values)
    db_session.add(account)
    await db_session.flush()
    return account


async def add_comment(db_session, organization, text="How much is the course fee?", ident=None, **kw) -> IgComment:
    values = dict(
        organization_id=organization.id, external_id=ident or f"c-{uuid.uuid4().hex[:8]}", media_external_id="m1", text=text, author_username="asha",
        author_id="900", posted_at=NOW - timedelta(hours=2), status="new", category="enquiry", priority="medium",
    )
    values.update(kw)
    row = IgComment(**values)
    db_session.add(row)
    await db_session.flush()
    return row


async def add_media(db_session, organization, ident="m1", **kw) -> IgMedia:
    row = IgMedia(organization_id=organization.id, external_id=ident, caption="What is a SIEM?", permalink=f"https://www.instagram.com/p/{ident}/", posted_at=NOW - timedelta(days=1), **kw)
    db_session.add(row)
    await db_session.flush()
    return row


async def add_conversation(db_session, organization, text="Hi, is there a batch in November?", user_ago=timedelta(hours=1), **kw) -> IgConversation:
    values = dict(
        organization_id=organization.id, external_id=f"conv-{uuid.uuid4().hex[:8]}", participant_id="900", participant_username="asha",
        remote_updated_at=NOW - user_ago, last_message_at=NOW - user_ago, last_user_message_at=NOW - user_ago, last_message_from_us=False,
        status="open", category="enquiry", priority="medium",
    )
    values.update(kw)
    conversation = IgConversation(**values)
    db_session.add(conversation)
    await db_session.flush()
    db_session.add(IgMessage(organization_id=organization.id, conversation_id=conversation.id, external_id=f"mid-{uuid.uuid4().hex[:8]}", direction="in", text=text, sent_at=NOW - user_ago))
    await db_session.flush()
    return conversation
