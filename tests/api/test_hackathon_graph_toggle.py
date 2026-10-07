"""The leaderboard's bar graph can be switched off per hackathon; every place the leaderboard is served says so."""

import uuid
from datetime import date, timedelta

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


async def test_the_bar_graph_is_on_by_default_and_can_be_switched_off_and_on(client, auth_headers):
    from modules.hackathons import routes

    routes._PUBLIC_CACHE_SECONDS = 0
    routes._public_cache.clear()
    try:
        created = await client.post(
            _HACK, json={"code": f"H-{uuid.uuid4().hex[:8]}", "title": "DevSecStorm", **_dates()}, headers=auth_headers
        )
        hackathon = created.json()
        assert hackathon["leaderboard_show_graph"] is True
        url = f"{_HACK}/{hackathon['id']}"
        slug = (await client.patch(url, json={"leaderboard_share_enabled": True}, headers=auth_headers)).json()["leaderboard_slug"]
        assert (await client.get(f"{_HACK}/public/leaderboard/{slug}")).json()["show_graph"] is True
        assert (await client.get(f"{url}/leaderboard", headers=auth_headers)).json()["show_graph"] is True

        off = await client.patch(url, json={"leaderboard_show_graph": False}, headers=auth_headers)
        assert off.status_code == 200 and off.json()["leaderboard_show_graph"] is False
        assert (await client.get(f"{_HACK}/public/leaderboard/{slug}")).json()["show_graph"] is False  # the public page
        assert (await client.get(f"{url}/leaderboard", headers=auth_headers)).json()["show_graph"] is False  # admin view
        # Other edits leave the choice alone; switching back on works.
        assert (await client.patch(url, json={"title": "DevSecStorm 2026"}, headers=auth_headers)).json()["leaderboard_show_graph"] is False
        on = await client.patch(url, json={"leaderboard_show_graph": True}, headers=auth_headers)
        assert on.json()["leaderboard_show_graph"] is True
    finally:
        routes._PUBLIC_CACHE_SECONDS = 3
        routes._public_cache.clear()
