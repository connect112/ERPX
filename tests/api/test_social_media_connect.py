"""
Social Media phase 4a: connecting Instagram, keeping the token alive, and the webhook Meta calls.

Meta and Instagram are scripted fakes. These tests prove what ERPX does with each kind of answer (a spent link, a personal
account, a refused permission, a bad signature, a retried notification), not that Meta's real servers accept these calls.
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from sqlalchemy import select

from modules.social_media import connection, instagram, oauth
from modules.social_media.connect_routes import extract_events
from modules.social_media.connection import ConnectionService, computed_status
from modules.social_media.instagram import InstagramError
from modules.social_media.models import SocialAccount, SocialSettings, WebhookEvent
from modules.social_media.oauth import OAuthError
from modules.social_media.token_crypto import decrypt_token, encrypt_token
from tests._fixtures import _make_user

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
NOW = datetime.now(timezone.utc).replace(microsecond=0)
ALL_SCOPES = [f"instagram_business_{s}" for s in ("basic", "content_publish", "manage_comments", "manage_messages", "manage_insights")]


# ---------------- fakes ----------------


class FakeIG:
    def __init__(self):
        self.errors: dict[str, list] = {}
        self.calls: list[str] = []
        self.profile = {"user_id": "17841400000000000", "username": "pentrix", "account_type": "BUSINESS"}

    def _go(self, name):
        self.calls.append(name)
        queue = self.errors.get(name)
        if queue:
            error = queue.pop(0)
            if error:
                raise error

    async def me(self):
        self._go("me")
        return self.profile

    async def publishing_limit(self):
        self._go("publishing_limit")
        return instagram.PublishLimit(0, 100)

    async def recent_media(self, limit=20):
        self._go("recent_media")
        return []

    async def list_conversations(self, limit=1):
        self._go("list_conversations")
        return []

    async def subscribe_webhooks(self, fields):
        self._go("subscribe_webhooks")
        self.subscribed = list(fields)
        return True

    async def unsubscribe_webhooks(self):
        self._go("unsubscribe_webhooks")
        return True


@pytest.fixture
def app_config(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "INSTAGRAM_APP_ID", "app-id-123")
    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "app-secret-xyz")
    monkeypatch.setattr(settings, "INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "verify-me-please")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://erp.example.com")
    monkeypatch.setattr(settings, "INSTAGRAM_REDIRECT_URI", "")
    return settings


@pytest.fixture
def ig(monkeypatch):
    fake = FakeIG()
    monkeypatch.setattr(instagram, "get_instagram_client", lambda ig_user_id, token: fake)
    return fake


@pytest.fixture
def meta(monkeypatch):
    """What Meta's token endpoints answer."""
    state = {"granted": list(ALL_SCOPES), "expires_in": 5183944, "error": None, "calls": []}

    async def exchange(code):
        state["calls"].append(("exchange", code))
        if state["error"]:
            raise state["error"]
        return "short-token", "17841400000000000", state["granted"]

    async def long_lived(short):
        state["calls"].append(("long_lived", short))
        return "long-token", state["expires_in"]

    monkeypatch.setattr(oauth, "exchange_code", exchange)
    monkeypatch.setattr(oauth, "long_lived", long_lived)
    return state


@pytest.fixture
def notified(monkeypatch):
    sent = []
    monkeypatch.setattr(connection, "notify_account_problem", lambda account, problem, detail: sent.append((problem, detail)))
    return sent


async def _account(db_session, organization, **kw):
    values = dict(
        organization_id=organization.id, external_account_id="17841400000000000", username="pentrix", account_type="BUSINESS",
        status="connected", token_encrypted=encrypt_token("old-token"), token_expires_at=NOW + timedelta(days=60), connected_at=NOW - timedelta(days=30),
        scopes=ALL_SCOPES, capabilities={},
    )
    values.update(kw)
    account = SocialAccount(**values)
    db_session.add(account)
    await db_session.flush()
    return account


async def _start(client, headers):
    response = await client.post(f"{_BASE}/connect/start", headers=headers)
    assert response.status_code == 200, response.text
    url = response.json()["url"]
    return url, parse_qs(urlparse(url).query)["state"][0]


async def _callback(client, state, code="the-code#_", **extra):
    params = {"state": state, **({"code": code} if code else {}), **extra}
    return await client.get(f"{_BASE}/connect/callback", params=params, follow_redirects=False)


def _where(response):
    location = response.headers["location"]
    return urlparse(location).path, {k: v[0] for k, v in parse_qs(urlparse(location).query).items()}


# ---------------- OAuth mechanics ----------------


def test_the_authorize_address_asks_for_exactly_what_the_docs_describe(app_config):
    url = oauth.authorize_url("STATE123")
    parsed = urlparse(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://www.instagram.com/oauth/authorize"
    assert query["client_id"] == "app-id-123" and query["response_type"] == "code" and query["state"] == "STATE123"
    assert query["redirect_uri"] == "https://erp.example.com/api/v1/social-media/connect/callback" and query["force_reauth"] == "true"
    assert query["scope"].split(",") == ALL_SCOPES
    assert "app-secret-xyz" not in url


def test_the_redirect_address_can_be_overridden_and_the_app_must_be_configured(app_config, monkeypatch):
    monkeypatch.setattr(app_config, "INSTAGRAM_REDIRECT_URI", "https://custom.example.com/cb")
    assert oauth.redirect_uri() == "https://custom.example.com/cb"
    monkeypatch.setattr(app_config, "INSTAGRAM_APP_SECRET", "")
    assert oauth.configured() is False


def test_the_code_loses_the_trailing_marker_instagram_adds():
    assert oauth.clean_code("AQBx123#_") == "AQBx123"
    assert oauth.clean_code("  AQBx123  ") == "AQBx123"


def test_the_state_is_signed_expires_and_cannot_be_altered(app_config):
    state = oauth.make_state("org-1", "user-1", "nonce-1")
    claims = oauth.read_state(state)
    assert (claims["org"], claims["user"], claims["nonce"]) == ("org-1", "user-1", "nonce-1")
    with pytest.raises(OAuthError) as tampered:
        oauth.read_state(state[:-3] + ("AAA" if not state.endswith("AAA") else "BBB"))
    assert tampered.value.code == "state"
    with pytest.raises(OAuthError):
        oauth.read_state(oauth.make_state("o", "u", "n", now=datetime.now(timezone.utc) - timedelta(minutes=30)))
    with pytest.raises(OAuthError):
        oauth.read_state("not a token")
    assert oauth.new_nonce() != oauth.new_nonce()


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _http(monkeypatch, answer):
    seen = {}

    class Http:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def request(self, method, url, data=None, params=None, headers=None):
            seen.update(method=method, url=url, data=data, params=params)
            result = answer()
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(oauth.httpx, "AsyncClient", Http)
    return seen


async def test_the_code_is_exchanged_with_the_secret_in_the_body_and_both_answer_shapes_are_read(app_config, monkeypatch):
    seen = _http(monkeypatch, lambda: _Resp(200, {"data": [{"access_token": "SHORT", "user_id": 99, "permissions": "instagram_business_basic,instagram_business_manage_messages"}]}))
    token, user_id, perms = await oauth.exchange_code("CODE#_")
    assert (token, user_id, perms) == ("SHORT", "99", ["instagram_business_basic", "instagram_business_manage_messages"])
    assert seen["method"] == "POST" and seen["url"] == "https://api.instagram.com/oauth/access_token"
    assert seen["data"] == {"client_id": "app-id-123", "client_secret": "app-secret-xyz", "grant_type": "authorization_code", "redirect_uri": oauth.redirect_uri(), "code": "CODE"}
    assert seen["params"] is None, "the secret is never put in a URL here"
    _http(monkeypatch, lambda: _Resp(200, {"access_token": "FLAT", "user_id": "7", "permissions": ["instagram_business_basic"]}))
    assert await oauth.exchange_code("c") == ("FLAT", "7", ["instagram_business_basic"])


async def test_the_long_lived_and_refresh_calls_parse_the_expiry(app_config, monkeypatch):
    seen = _http(monkeypatch, lambda: _Resp(200, {"access_token": "LONG", "token_type": "bearer", "expires_in": 5183944}))
    assert await oauth.long_lived("SHORT") == ("LONG", 5183944)
    assert seen["method"] == "GET" and seen["url"].endswith("/access_token")
    assert seen["params"] == {"grant_type": "ig_exchange_token", "client_secret": "app-secret-xyz", "access_token": "SHORT"}
    assert await oauth.refresh("LONG") == ("LONG", 5183944)
    assert seen["url"].endswith("/refresh_access_token") and seen["params"] == {"grant_type": "ig_refresh_token", "access_token": "LONG"}


@pytest.mark.parametrize(
    "answer, code",
    [
        (lambda: httpx.ConnectError("down"), "network"),
        (lambda: _Resp(400, {"error": {"message": "Invalid code app-secret-xyz access_token=SECRETTOKEN"}}), "exchange"),
        (lambda: _Resp(200, {"data": []}), "exchange"),
        (lambda: _Resp(200, ["not", "a", "dict"]), "exchange"),
    ],
)
async def test_code_exchange_failures_are_named_and_never_echo_secrets(app_config, monkeypatch, answer, code):
    _http(monkeypatch, answer)
    with pytest.raises(OAuthError) as exc:
        await oauth.exchange_code("c")
    assert exc.value.code == code
    assert "SECRETTOKEN" not in exc.value.message


async def test_a_token_answer_without_a_usable_expiry_is_refused(app_config, monkeypatch):
    _http(monkeypatch, lambda: _Resp(200, {"access_token": "x", "expires_in": "soon"}))
    for call in (oauth.long_lived, oauth.refresh):
        with pytest.raises(OAuthError) as exc:
            await call("t")
        assert exc.value.code == "exchange"


def test_the_http_clients_request_log_has_tokens_and_secrets_removed():
    flt = next(f for f in logging.getLogger("httpx").filters if f.__class__.__name__ == "_Redact")
    record = logging.LogRecord("httpx", logging.INFO, "x", 1, 'HTTP Request: %s %s "%s %d %s"', ("GET", httpx.URL("https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=TOPSECRET&access_token=SECRETTOKEN"), "HTTP/1.1", 200, "OK"), None)
    flt.filter(record)
    rendered = record.getMessage()
    assert "TOPSECRET" not in rendered and "SECRETTOKEN" not in rendered and "client_secret=[redacted]" in rendered and "grant_type=ig_exchange_token" in rendered


# ---------------- starting a connection ----------------


async def test_starting_needs_the_connect_permission_and_a_configured_app(client, auth_headers, staff_headers, rbac_seeded, app_config, monkeypatch):
    assert (await client.post(f"{_BASE}/connect/start", headers=staff_headers)).status_code == 403
    monkeypatch.setattr(app_config, "INSTAGRAM_APP_ID", "")
    refused = await client.post(f"{_BASE}/connect/start", headers=auth_headers)
    assert refused.status_code == 422 and "isn't set up on this server" in refused.text and "INSTAGRAM_APP_ID" in refused.text
    monkeypatch.setattr(app_config, "INSTAGRAM_APP_ID", "app-id-123")
    url, state = await _start(client, auth_headers)
    assert url.startswith("https://www.instagram.com/oauth/authorize?") and state


async def test_a_plain_manager_without_the_connect_permission_cannot_start_or_disconnect(client, db_session, organization, rbac_seeded, app_config):
    from modules.authorization.service import AuthorizationService

    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"m-{uuid.uuid4().hex[:6]}@erpx.example.com")
    service = AuthorizationService(db_session)
    role = await service.create_role(organization.id, "Social", f"s-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, ["social_media.view", "social_media.manage", "social_media.approve", "social_media.publish"])
    await service.assign_role(user.id, role.id, organization.id, None)
    headers = {"Authorization": f"Bearer {token}"}
    for path in ("connect/start", "connect/disconnect", "connect/recheck", "connect/refresh-token"):
        assert (await client.post(f"{_BASE}/{path}", headers=headers)).status_code == 403, path


# ---------------- completing it ----------------


async def test_a_connection_stores_the_token_encrypted_and_records_what_the_account_can_do(client, auth_headers, db_session, organization, app_config, ig, meta):
    _, state = await _start(client, auth_headers)
    response = await _callback(client, state)
    assert response.status_code == 303 and _where(response) == ("/social-media", {"tab": "settings", "connect": "ok"})
    assert meta["calls"] == [("exchange", "the-code#_"), ("long_lived", "short-token")]
    row = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    assert row.external_account_id == "17841400000000000" and row.username == "pentrix" and row.account_type == "BUSINESS" and row.status == "connected"
    assert row.token_encrypted and "long-token" not in row.token_encrypted and decrypt_token(row.token_encrypted) == "long-token"
    assert abs((row.token_expires_at - (datetime.now(timezone.utc) + timedelta(seconds=5183944))).total_seconds()) < 60
    assert row.scopes == sorted(ALL_SCOPES) and row.last_error is None
    assert row.capabilities == {"publish": "available", "comments": "available", "messages": "available", "insights": "available", "webhooks": "subscribed"}
    assert sorted(ig.subscribed) == ["comments", "messages"]
    settings_row = (await db_session.execute(select(SocialSettings).where(SocialSettings.organization_id == organization.id))).scalar_one()
    assert settings_row.connect_state == {}, "the one-use link is spent"


async def test_the_status_screen_never_shows_the_token_and_marks_what_has_and_has_not_been_proven(client, auth_headers, db_session, organization, app_config, ig, meta):
    _, state = await _start(client, auth_headers)
    await _callback(client, state)
    data = (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()
    assert data["connected"] is True and data["account"]["username"] == "pentrix" and data["account"]["status"] == "connected"
    assert 58 <= data["account"]["token_days_left"] <= 60
    assert "long-token" not in json.dumps(data) and "token_encrypted" not in json.dumps(data)
    assert data["app_configured"] is True and data["redirect_uri"] == "https://erp.example.com/api/v1/social-media/connect/callback"
    assert data["webhook_url"] == "https://erp.example.com/api/v1/social-media/webhooks/instagram" and data["webhook_verify_token_set"] is True
    by_key = {c["key"]: c for c in data["capabilities"]}
    assert by_key["connect"]["live_check"] == "passed" and by_key["connect"]["verified_live"] is True
    assert by_key["publish_image"]["live_check"] == "passed" and by_key["publish_image"]["verified_live"] is False, "a permission check is not a published post"
    assert by_key["dm_read"]["live_check"] == "passed" and by_key["dm_read"]["verified_live"] is False
    assert by_key["webhooks"]["live_check"] == "passed" and by_key["webhooks"]["verified_live"] is False
    assert by_key["save_share_identities"]["live_check"] == "not_run"
    overview = (await client.get(f"{_BASE}/overview", headers=auth_headers)).json()
    assert overview["connected"] is True


async def test_a_link_works_once(client, auth_headers, db_session, organization, app_config, ig, meta):
    _, state = await _start(client, auth_headers)
    assert _where(await _callback(client, state))[1]["connect"] == "ok"
    again = await _callback(client, state)
    assert _where(again)[1] == {"tab": "settings", "connect": "error", "reason": "state"}
    assert meta["calls"].count(("exchange", "the-code#_")) == 1, "the second use never reached Meta"


@pytest.mark.parametrize("break_it, reason", [("tamper", "state"), ("expire", "state"), ("missing", "state")])
async def test_a_bad_or_old_link_is_refused_before_anything_is_exchanged(client, auth_headers, db_session, organization, app_config, ig, meta, break_it, reason):
    _, state = await _start(client, auth_headers)
    if break_it == "tamper":
        state = state[:-4] + "AAAA"
    elif break_it == "expire":
        row = (await db_session.execute(select(SocialSettings).where(SocialSettings.organization_id == organization.id))).scalar_one()
        row.connect_state = {**row.connect_state, "expires": (NOW - timedelta(minutes=1)).isoformat()}
        await db_session.flush()
    elif break_it == "missing":
        state = ""
    response = await _callback(client, state) if state else await client.get(f"{_BASE}/connect/callback", params={"code": "x"}, follow_redirects=False)
    assert _where(response)[1]["reason"] == reason and meta["calls"] == []


async def test_a_link_for_another_person_or_organisation_cannot_be_used(client, auth_headers, db_session, organization, app_config, ig, meta):
    org_id = organization.id
    _, state = await _start(client, auth_headers)
    forged = oauth.make_state(str(org_id), str(uuid.uuid4()), oauth.read_state(state)["nonce"])  # right nonce, wrong person
    assert _where(await _callback(client, forged))[1]["reason"] == "state"
    other = oauth.make_state(str(uuid.uuid4()), str(uuid.uuid4()), "whatever")
    assert _where(await _callback(client, other))[1]["reason"] == "state"
    assert meta["calls"] == []


async def test_cancelling_on_instagram_connects_nothing(client, auth_headers, db_session, organization, app_config, ig, meta):
    org_id = organization.id
    _, state = await _start(client, auth_headers)
    response = await _callback(client, state, code=None, error="access_denied")
    assert _where(response)[1] == {"tab": "settings", "connect": "error", "reason": "denied"} and meta["calls"] == []
    assert (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == org_id))).first() is None


async def test_someone_who_lost_the_connect_permission_meanwhile_cannot_finish_it(client, db_session, organization, rbac_seeded, app_config, ig, meta):
    from modules.authorization.service import AuthorizationService

    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"c-{uuid.uuid4().hex[:6]}@erpx.example.com")
    service = AuthorizationService(db_session)
    role = await service.create_role(organization.id, "Connector", f"c-{uuid.uuid4().hex[:6]}", None)
    await service.set_role_permissions(role.id, organization.id, ["social_media.view", "social_media.connect"])
    await service.assign_role(user.id, role.id, organization.id, None)
    headers = {"Authorization": f"Bearer {token}"}
    _, state = await _start(client, headers)
    await service.set_role_permissions(role.id, organization.id, ["social_media.view"])  # taken away before the redirect came back
    response = await _callback(client, state)
    assert _where(response)[1]["reason"] == "permission" and meta["calls"] == []


async def test_a_personal_account_is_refused_and_nothing_is_stored(client, auth_headers, db_session, organization, app_config, ig, meta):
    org_id = organization.id
    ig.profile = {"user_id": "17841400000000000", "username": "someone", "account_type": "PERSONAL"}
    _, state = await _start(client, auth_headers)
    response = await _callback(client, state)
    assert _where(response)[1]["reason"] == "account_type"
    assert (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == org_id))).first() is None


async def test_a_refusal_by_meta_is_reported_without_provider_text_and_stores_nothing(client, auth_headers, db_session, organization, app_config, ig, meta):
    org_id = organization.id
    meta["error"] = OAuthError("exchange", "Instagram refused the request: Invalid redirect_uri")
    _, state = await _start(client, auth_headers)
    response = await _callback(client, state)
    assert _where(response)[1] == {"tab": "settings", "connect": "error", "reason": "exchange"}
    assert "Invalid" not in response.headers["location"]
    assert (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == org_id))).first() is None


async def test_missing_permissions_and_ones_needing_meta_review_are_recorded_honestly(client, auth_headers, db_session, organization, app_config, ig, meta):
    meta["granted"] = ["instagram_business_basic", "instagram_business_manage_messages"]
    ig.errors["list_conversations"] = [InstagramError("permanent", "(#3) Application does not have the capability to make this API call.", code=3, http_status=403)]
    _, state = await _start(client, auth_headers)
    await _callback(client, state)
    row = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    assert row.capabilities == {"publish": "unavailable", "comments": "unavailable", "messages": "needs_app_review", "insights": "unavailable", "webhooks": "subscribed"}
    assert ig.subscribed == ["messages"], "only what was granted is subscribed to"
    data = (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()
    by_key = {c["key"]: c for c in data["capabilities"]}
    assert by_key["dm_read"]["live_check"] == "needs_app_review" and by_key["publish_image"]["live_check"] == "failed"


async def test_a_token_rejected_while_checking_the_account_connects_nothing(client, auth_headers, db_session, organization, app_config, ig, meta):
    org_id = organization.id
    ig.errors["publishing_limit"] = [InstagramError("token", "Instagram says the access token is no longer valid. Reconnect the account.", code=190, http_status=401)]
    _, state = await _start(client, auth_headers)
    assert _where(await _callback(client, state))[1]["reason"] == "token"
    assert (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == org_id))).first() is None


async def test_a_temporary_problem_during_the_checks_leaves_that_feature_unknown_not_failed(client, auth_headers, db_session, organization, app_config, ig, meta):
    ig.errors["recent_media"] = [InstagramError("transient", "busy", http_status=503)]
    ig.errors["subscribe_webhooks"] = [InstagramError("permanent", "app not live", code=100, http_status=400)]
    _, state = await _start(client, auth_headers)
    await _callback(client, state)
    row = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    assert row.capabilities["comments"] == "unknown" and row.capabilities["webhooks"] == "error" and row.capabilities["publish"] == "available"


async def test_connecting_a_different_account_replaces_the_old_one_and_forgets_what_was_read_from_it(client, auth_headers, db_session, organization, app_config, ig, meta):
    await _account(db_session, organization, external_account_id="111", sync_state={"comments": {"count": 4}})
    _, state = await _start(client, auth_headers)
    await _callback(client, state)
    rows = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalars().all()
    assert len(rows) == 1 and rows[0].external_account_id == "17841400000000000" and "comments" not in rows[0].sync_state


# ---------------- state of the connection ----------------


def test_the_status_follows_the_tokens_expiry():
    def acct(**kw):
        return SocialAccount(external_account_id="1", token_encrypted="x", status="connected", **kw)

    assert computed_status(None, NOW) == "not_connected"
    assert computed_status(SocialAccount(external_account_id="1", status="connected"), NOW) == "not_connected"
    assert computed_status(acct(token_expires_at=NOW + timedelta(days=40)), NOW) == "connected"
    assert computed_status(acct(token_expires_at=NOW + timedelta(days=10)), NOW) == "expiring"
    assert computed_status(acct(token_expires_at=NOW - timedelta(minutes=1)), NOW) == "expired"
    assert computed_status(SocialAccount(external_account_id="1", token_encrypted="x", status="revoked", token_expires_at=NOW + timedelta(days=40)), NOW) == "revoked"


async def test_disconnecting_deletes_the_token_stops_the_webhook_and_keeps_the_history(client, auth_headers, db_session, organization, ig):
    await _account(db_session, organization)
    assert (await client.post(f"{_BASE}/connect/disconnect", headers=auth_headers)).status_code == 200
    row = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    await db_session.refresh(row)
    assert row.token_encrypted is None and row.status == "not_connected" and row.capabilities == {} and "unsubscribe_webhooks" in ig.calls
    assert (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()["connected"] is False
    assert (await client.post(f"{_BASE}/connect/disconnect", headers=auth_headers)).status_code == 409


async def test_disconnecting_still_works_when_instagram_cannot_be_reached(client, auth_headers, db_session, organization, ig):
    await _account(db_session, organization)
    ig.errors["unsubscribe_webhooks"] = [InstagramError("transient", "down", http_status=503)]
    assert (await client.post(f"{_BASE}/connect/disconnect", headers=auth_headers)).status_code == 200
    row = (await db_session.execute(select(SocialAccount).where(SocialAccount.organization_id == organization.id))).scalar_one()
    assert row.token_encrypted is None, "the token is deleted whatever Instagram says"


async def test_rechecking_updates_what_the_account_can_do_and_flags_a_dead_token(client, auth_headers, db_session, organization, app_config, ig):
    account = await _account(db_session, organization, capabilities={"messages": "needs_app_review"})
    ok = await client.post(f"{_BASE}/connect/recheck", headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["capabilities"]["messages"] == "available"
    ig.errors["publishing_limit"] = [InstagramError("token", "Instagram says the access token is no longer valid. Reconnect the account.", code=190, http_status=401)]
    bad = await client.post(f"{_BASE}/connect/recheck", headers=auth_headers)
    assert bad.status_code == 422
    await db_session.refresh(account)
    assert account.status == "revoked" and "Reconnect" in account.last_error


# ---------------- keeping the token alive ----------------


@pytest.fixture
def refreshing(monkeypatch):
    state = {"result": ("new-token", 5183944), "calls": 0}

    async def refresh(token):
        state["calls"] += 1
        if isinstance(state["result"], Exception):
            raise state["result"]
        return state["result"]

    monkeypatch.setattr(oauth, "refresh", refresh)
    return state


async def test_a_token_near_its_end_is_swapped_for_a_fresh_one(db_session, organization, refreshing, notified):
    account = await _account(db_session, organization, token_expires_at=NOW + timedelta(days=10), connected_at=NOW - timedelta(days=50), status="expiring")
    result = await ConnectionService(db_session).refresh_due(NOW)
    assert result == {"refreshed": 1, "failed": 0, "skipped": 0}
    assert decrypt_token(account.token_encrypted) == "new-token" and account.status == "connected"
    assert account.token_expires_at == NOW + timedelta(seconds=5183944) and account.sync_state["token"]["refreshed_at"] == NOW.isoformat()
    assert notified == []


async def test_tokens_far_from_expiry_or_too_new_to_refresh_are_left_alone(db_session, organization, refreshing):
    far = await _account(db_session, organization, token_expires_at=NOW + timedelta(days=45))
    assert await ConnectionService(db_session).refresh_due(NOW) == {"refreshed": 0, "failed": 0, "skipped": 0}
    far.token_expires_at, far.connected_at = NOW + timedelta(days=5), NOW - timedelta(hours=3)  # near its end, but only 3 hours old
    await db_session.flush()
    assert await ConnectionService(db_session).refresh_due(NOW) == {"refreshed": 0, "failed": 0, "skipped": 1}
    assert refreshing["calls"] == 0


async def test_a_refusal_to_refresh_marks_the_account_and_warns_when_time_is_short(db_session, organization, refreshing, notified):
    account = await _account(db_session, organization, token_expires_at=NOW + timedelta(days=5), connected_at=NOW - timedelta(days=55))
    refreshing["result"] = OAuthError("exchange", "Instagram refused the request: token revoked")
    result = await ConnectionService(db_session).refresh_due(NOW)
    assert result["failed"] == 1 and account.status == "revoked" and "refused" in account.last_error
    assert notified and notified[0][0] == "The Instagram connection needs attention" and "Reconnect" in notified[0][1]


async def test_a_network_problem_while_refreshing_changes_nothing_but_the_note(db_session, organization, refreshing, notified):
    account = await _account(db_session, organization, token_expires_at=NOW + timedelta(days=15), connected_at=NOW - timedelta(days=45))
    refreshing["result"] = OAuthError("network", "Instagram couldn't be reached. Try again in a moment.")
    result = await ConnectionService(db_session).refresh_due(NOW)
    assert result["failed"] == 1 and account.status == "connected" and "couldn't be reached" in account.last_error
    assert notified == [], "15 days left: tomorrow's run tries again, no alarm yet"
    account.token_expires_at = NOW + timedelta(days=4)
    await ConnectionService(db_session).refresh_due(NOW)
    assert len(notified) == 1, "with under a week left, it says so"


async def test_an_unreadable_stored_token_is_a_reconnect_problem(db_session, organization, refreshing, notified):
    account = await _account(db_session, organization, token_encrypted="garbage", token_expires_at=NOW + timedelta(days=5), connected_at=NOW - timedelta(days=55))
    assert (await ConnectionService(db_session).refresh_due(NOW))["failed"] == 1 and account.status == "revoked"
    assert refreshing["calls"] == 0


async def test_the_refresh_button_works_and_reports_failure(client, auth_headers, db_session, organization, refreshing):
    account = await _account(db_session, organization)
    assert (await client.post(f"{_BASE}/connect/refresh-token", headers=auth_headers)).status_code == 200
    refreshing["result"] = OAuthError("exchange", "Instagram refused the request.")
    refused = await client.post(f"{_BASE}/connect/refresh-token", headers=auth_headers)
    assert refused.status_code == 422 and "refused" in refused.text
    await db_session.refresh(account)
    assert account.status == "revoked"


def test_the_refresh_job_is_registered_and_scheduled():
    from app.core.celery_app import celery_app

    celery_app.loader.import_default_modules()
    assert {"social.refresh_tokens", "social.send_account_problem_email"} <= set(celery_app.tasks)
    assert "social.refresh_tokens" in {e["task"] for e in celery_app.conf.beat_schedule.values()}


# ---------------- webhooks ----------------


def _signed(payload: dict | bytes, secret="app-secret-xyz"):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return raw, {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), "Content-Type": "application/json"}


COMMENT_EVENT = {"object": "instagram", "entry": [{"id": "17841400000000000", "time": 1700000000, "changes": [{"field": "comments", "value": {"id": "c1", "text": "How much is the course?", "from": {"id": "9", "username": "asha"}, "media": {"id": "m1"}}}]}]}
MESSAGE_EVENT = {"object": "instagram", "entry": [{"id": "17841400000000000", "time": 1700000001, "messaging": [{"sender": {"id": "9"}, "recipient": {"id": "17841400000000000"}, "timestamp": 1700000001000, "message": {"mid": "mid.1", "text": "Hi, is there a batch in November?"}}]}]}


async def test_the_verification_handshake_returns_the_challenge_only_for_the_right_token(client, app_config):
    ok = await client.get(f"{_BASE}/webhooks/instagram", params={"hub.mode": "subscribe", "hub.challenge": "1158201444", "hub.verify_token": "verify-me-please"})
    assert ok.status_code == 200 and ok.text == "1158201444"
    for params in (
        {"hub.mode": "subscribe", "hub.challenge": "1", "hub.verify_token": "wrong"},
        {"hub.mode": "unsubscribe", "hub.challenge": "1", "hub.verify_token": "verify-me-please"},
        {"hub.mode": "subscribe", "hub.challenge": "1"},
        {},
    ):
        assert (await client.get(f"{_BASE}/webhooks/instagram", params=params)).status_code == 403


async def test_the_handshake_is_refused_when_no_verify_token_is_configured(client, app_config, monkeypatch):
    monkeypatch.setattr(app_config, "INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "")
    assert (await client.get(f"{_BASE}/webhooks/instagram", params={"hub.mode": "subscribe", "hub.challenge": "1", "hub.verify_token": ""})).status_code == 403


async def test_a_notification_without_a_valid_signature_is_refused_before_it_is_read(client, db_session, app_config):
    raw, headers = _signed(COMMENT_EVENT)
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw)).status_code == 403
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers={"X-Hub-Signature-256": "sha256=" + "0" * 64})).status_code == 403
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers={"X-Hub-Signature-256": headers["X-Hub-Signature-256"].replace("sha256=", "")})).status_code == 403
    _, wrong_secret = _signed(COMMENT_EVENT, secret="not-the-secret")
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=wrong_secret)).status_code == 403
    tampered = raw.replace(b"c1", b"c2")
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=tampered, headers=headers)).status_code == 403
    assert (await db_session.execute(select(WebhookEvent))).first() is None


async def test_notifications_are_refused_when_the_app_secret_is_not_configured(client, app_config, monkeypatch):
    monkeypatch.setattr(app_config, "INSTAGRAM_APP_SECRET", "")
    raw, headers = _signed(COMMENT_EVENT)
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)).status_code == 503


async def test_a_signed_notification_is_recorded_by_ids_only_and_a_retry_is_ignored(client, db_session, organization, app_config):
    await _account(db_session, organization)
    raw, headers = _signed(COMMENT_EVENT)
    first = await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)
    assert first.status_code == 200 and first.json() == {"received": 1, "new": 1}
    retry = await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)
    assert retry.status_code == 200 and retry.json() == {"received": 1, "new": 0}, "Meta retries; each notification is handled once"
    rows = (await db_session.execute(select(WebhookEvent).where(WebhookEvent.organization_id == organization.id))).scalars().all()
    assert len(rows) == 1 and (rows[0].entry_id, rows[0].field, rows[0].object_id) == ("17841400000000000", "comments", "c1")
    stored = " ".join(str(getattr(rows[0], c.name)) for c in WebhookEvent.__table__.columns)
    assert "How much" not in stored and "asha" not in stored, "no message text or names are kept"


async def test_messages_and_changed_field_notifications_are_understood(client, db_session, organization, app_config):
    await _account(db_session, organization)
    for payload in (MESSAGE_EVENT, {"object": "instagram", "entry": [{"id": "17841400000000000", "time": 5, "changed_fields": ["comments"]}]}):
        raw, headers = _signed(payload)
        assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)).json()["new"] == 1
    kinds = {r.field: r.object_id for r in (await db_session.execute(select(WebhookEvent))).scalars()}
    assert kinds == {"messages": "mid.1", "comments": None}


async def test_a_batch_is_split_and_unknown_accounts_are_kept_apart(client, db_session, organization, app_config):
    await _account(db_session, organization)
    batch = {"object": "instagram", "entry": [COMMENT_EVENT["entry"][0], {"id": "999", "time": 1, "changes": [{"field": "comments", "value": {"id": "x9"}}]}]}
    raw, headers = _signed(batch)
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)).json() == {"received": 2, "new": 2}
    owned = {r.entry_id: r.organization_id for r in (await db_session.execute(select(WebhookEvent))).scalars()}
    assert owned == {"17841400000000000": organization.id, "999": None}


@pytest.mark.parametrize("payload", [{}, {"entry": "x"}, {"entry": [None, 5, {"changes": "x"}]}, {"entry": [{"id": 1, "changes": [{"nofield": 1}]}]}, []])
async def test_odd_payloads_are_acknowledged_and_ignored(client, app_config, payload):
    raw, headers = _signed(payload if isinstance(payload, dict) else json.dumps(payload).encode())
    response = await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)
    assert response.status_code == 200 and response.json()["new"] == 0


async def test_unparseable_and_oversized_bodies_are_refused(client, app_config):
    raw, headers = _signed(b"this is not json")
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)).status_code == 400
    big = b"{" + b" " * 1_100_000 + b"}"
    raw, headers = _signed(big)
    assert (await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)).status_code == 413


async def test_a_received_notification_counts_as_proof_the_webhook_works(client, auth_headers, db_session, organization, app_config):
    await _account(db_session, organization, capabilities={"webhooks": "subscribed"})
    before = {c["key"]: c for c in (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()["capabilities"]}
    assert before["webhooks"]["verified_live"] is False
    raw, headers = _signed(COMMENT_EVENT)
    await client.post(f"{_BASE}/webhooks/instagram", content=raw, headers=headers)
    after = {c["key"]: c for c in (await client.get(f"{_BASE}/integration", headers=auth_headers)).json()["capabilities"]}
    assert after["webhooks"]["verified_live"] is True


def test_event_extraction_ignores_what_it_does_not_recognise():
    assert extract_events("nope") == [] and extract_events({"entry": [{"changes": [{"field": "x"}]}]}) == []
    events = extract_events(COMMENT_EVENT)
    assert len(events) == 1 and events[0][:3] == ("17841400000000000", "comments", "c1")
