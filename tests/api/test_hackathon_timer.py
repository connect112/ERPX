"""
The hackathon timer: organisers set when the event starts and ends, and the presentation page counts
down to it (display only). Covers saving and clearing, validation, and the public page's data.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.api

_HACK = "/api/v1/hackathons"


def _dates():
    today = date.today()
    return {
        "registration_deadline": (today + timedelta(days=7)).isoformat(),
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=12)).isoformat(),
    }


async def _hackathon(client, auth_headers):
    r = await client.post(_HACK, json={"code": f"H-{uuid.uuid4().hex[:8]}", "title": "DevSecStorm", **_dates()}, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()


def _at(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


async def test_a_new_hackathon_has_no_timer_and_one_can_be_set_and_cleared(client, auth_headers):
    hackathon = await _hackathon(client, auth_headers)
    assert hackathon["timer_starts_at"] is None and hackathon["timer_ends_at"] is None
    url = f"{_HACK}/{hackathon['id']}"

    ends, starts = _at(30), _at(2)
    saved = await client.patch(url, json={"timer_starts_at": starts, "timer_ends_at": ends}, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert datetime.fromisoformat(body["timer_ends_at"].replace("Z", "+00:00")) == datetime.fromisoformat(ends.replace("Z", "+00:00"))
    assert body["timer_starts_at"] is not None

    # Just the end can be moved; the start stays.
    later = _at(40)
    moved = await client.patch(url, json={"timer_ends_at": later}, headers=auth_headers)
    assert moved.status_code == 200 and moved.json()["timer_starts_at"] == body["timer_starts_at"]

    # Each time can be cleared on its own.
    cleared = await client.patch(url, json={"timer_starts_at": None}, headers=auth_headers)
    assert cleared.status_code == 200 and cleared.json()["timer_starts_at"] is None and cleared.json()["timer_ends_at"] is not None
    gone = await client.patch(url, json={"timer_ends_at": None}, headers=auth_headers)
    assert gone.json()["timer_ends_at"] is None
    # Other edits leave the timer alone.
    await client.patch(url, json={"timer_ends_at": ends}, headers=auth_headers)
    renamed = await client.patch(url, json={"title": "DevSecStorm 2026"}, headers=auth_headers)
    assert renamed.json()["timer_ends_at"] is not None


async def test_a_timer_must_end_after_it_starts_and_carry_a_timezone(client, auth_headers):
    hackathon = await _hackathon(client, auth_headers)
    url = f"{_HACK}/{hackathon['id']}"

    both = await client.patch(url, json={"timer_starts_at": _at(10), "timer_ends_at": _at(5)}, headers=auth_headers)
    assert both.status_code == 422
    # Against a saved start, moving only the end earlier than it is also refused (and nothing is saved).
    await client.patch(url, json={"timer_starts_at": _at(10), "timer_ends_at": _at(20)}, headers=auth_headers)
    early = await client.patch(url, json={"timer_ends_at": _at(3)}, headers=auth_headers)
    assert early.status_code == 422 and "after it starts" in early.text
    assert (await client.get(url, headers=auth_headers)).json()["timer_ends_at"] is not None
    late_start = await client.patch(url, json={"timer_starts_at": _at(50)}, headers=auth_headers)
    assert late_start.status_code == 422
    # A time with no timezone would mean different moments on different screens.
    naive = await client.patch(url, json={"timer_ends_at": "2030-01-01T10:00:00"}, headers=auth_headers)
    assert naive.status_code == 422


async def test_the_public_page_carries_the_timer_and_the_servers_clock(client, auth_headers):
    from modules.hackathons import routes

    routes._PUBLIC_CACHE_SECONDS = 0
    routes._public_cache.clear()
    try:
        hackathon = await _hackathon(client, auth_headers)
        url = f"{_HACK}/{hackathon['id']}"
        shared = await client.patch(url, json={"leaderboard_share_enabled": True, "timer_ends_at": _at(5)}, headers=auth_headers)
        slug = shared.json()["leaderboard_slug"]

        page = (await client.get(f"{_HACK}/public/leaderboard/{slug}")).json()  # no login
        assert page["timer_ends_at"] is not None and page["timer_starts_at"] is None
        before = datetime.fromisoformat(page["server_time"].replace("Z", "+00:00"))
        assert abs((datetime.now(timezone.utc) - before).total_seconds()) < 30  # the server's own clock, for screens to sync to

        # Changing the timer shows up straight away.
        await client.patch(url, json={"timer_starts_at": _at(1), "timer_ends_at": _at(9)}, headers=auth_headers)
        again = (await client.get(f"{_HACK}/public/leaderboard/{slug}")).json()
        assert again["timer_starts_at"] is not None and again["timer_ends_at"] != page["timer_ends_at"]
    finally:
        routes._PUBLIC_CACHE_SECONDS = 3
        routes._public_cache.clear()
