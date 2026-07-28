"""
API tests for the Notifications module: a generic in-app inbox any other
module can push into. Coverage: reading your own notifications, marking
one/all read, unread-count accuracy, and staff broadcast fanning out to
every user in the organization (RBAC-gated since it's a sensitive
one-to-many action, unlike reading your own tray which needs no
permission at all).
"""

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from modules.authentication.models import User, UserStatus
from modules.authentication.repository import AuthRepository
from modules.notifications.models import Notification, NotificationType
from modules.notifications.service import NotificationService
from modules.users.repository import UserProfileRepository

pytestmark = pytest.mark.api


async def _make_user(client, db_session, organization, full_name="Extra User"):
    unique = uuid.uuid4().hex[:8]
    auth_repo = AuthRepository(db_session)
    user = await auth_repo.create_user(
        email=f"notif.{unique}@erpx.example.com",
        hashed_password=hash_password("Test1234!"),
        full_name=full_name,
    )
    user.status = UserStatus.ACTIVE
    user.is_email_verified = True
    await db_session.flush()

    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)
    await db_session.flush()

    token = create_access_token(str(user.id))
    return user, {"Authorization": f"Bearer {token}"}


async def test_list_own_notifications_and_unread_count(client, db_session, organization, superuser):
    user, _token = superuser
    service = NotificationService(db_session)
    await service.create_notification(
        organization.id, user.id, "Welcome", body="Thanks for joining.", notification_type=NotificationType.INFO
    )
    await service.create_notification(
        organization.id, user.id, "Action needed", notification_type=NotificationType.ACTION_REQUIRED
    )
    await db_session.flush()

    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

    list_response = await client.get("/api/v1/notifications/me", headers=headers)
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["total"] == 2

    unread_response = await client.get("/api/v1/notifications/me/unread-count", headers=headers)
    assert unread_response.status_code == 200
    assert unread_response.json()["unread_count"] == 2


async def test_mark_read_and_mark_all_read(client, db_session, organization, superuser):
    user, _token = superuser
    service = NotificationService(db_session)
    n1 = await service.create_notification(organization.id, user.id, "One")
    await service.create_notification(organization.id, user.id, "Two")
    await db_session.flush()

    headers = {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

    read_response = await client.post(f"/api/v1/notifications/me/{n1.id}/read", headers=headers)
    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True

    unread_response = await client.get("/api/v1/notifications/me/unread-count", headers=headers)
    assert unread_response.json()["unread_count"] == 1

    mark_all_response = await client.post("/api/v1/notifications/me/read-all", headers=headers)
    assert mark_all_response.status_code == 200

    final_unread_response = await client.get("/api/v1/notifications/me/unread-count", headers=headers)
    assert final_unread_response.json()["unread_count"] == 0


async def test_notifications_are_isolated_per_user(client, db_session, organization, superuser):
    user_a, _ = superuser
    user_b, headers_b = await _make_user(client, db_session, organization, "User B")

    service = NotificationService(db_session)
    await service.create_notification(organization.id, user_a.id, "For A only")
    await db_session.flush()

    list_response = await client.get("/api/v1/notifications/me", headers=headers_b)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0


async def test_staff_without_permission_cannot_broadcast(client, staff_headers):
    response = await client.post(
        "/api/v1/notifications/broadcast", json={"title": "Hello everyone"}, headers=staff_headers
    )
    assert response.status_code == 403


async def test_broadcast_reaches_every_org_member(client, db_session, organization, auth_headers):
    _user_b, headers_b = await _make_user(client, db_session, organization, "User B")
    _user_c, headers_c = await _make_user(client, db_session, organization, "User C")

    broadcast_response = await client.post(
        "/api/v1/notifications/broadcast",
        json={"title": "Platform maintenance", "body": "Downtime at midnight.", "notification_type": "warning"},
        headers=auth_headers,
    )
    assert broadcast_response.status_code == 200
    # superuser + user_b + user_c
    assert broadcast_response.json()["notified_count"] >= 3

    for headers in (headers_b, headers_c):
        list_response = await client.get("/api/v1/notifications/me", headers=headers)
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        assert any(n["title"] == "Platform maintenance" and n["notification_type"] == "warning" for n in items)
