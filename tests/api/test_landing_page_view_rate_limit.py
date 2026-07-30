"""
Abuse-mitigation test for the anonymous landing-page view beacon
(`POST /marketing/landing-pages/{page_id}/views`).

The beacon is unauthenticated and writes a `LandingPageView` row per call,
so without a limit it can be flooded to inflate view analytics and bloat
storage. This app wires rate limiting only via per-route `@limiter.limit`
decorators (there is no global SlowAPI middleware), so the fix adds a
per-IP cap (`settings.RATE_LIMIT_PUBLIC_VIEW`) to this route. These tests
exhaust that cap from a clean slate (the `client` fixture calls
`limiter.reset()` before each test) and prove the (N+1)th call is rejected
with 429, while a normal single view still succeeds.
"""

import uuid

import pytest

from app.core.config import settings
from modules.marketing.landing_pages.models import LandingPageStatus
from modules.marketing.landing_pages.repository import LandingPageRepository

pytestmark = pytest.mark.api

_LIMIT = int(settings.RATE_LIMIT_PUBLIC_VIEW.split("/")[0])


async def _published_page(db_session, organization):
    page = await LandingPageRepository(db_session).create(
        organization_id=organization.id,
        slug=f"lp-{uuid.uuid4().hex[:8]}",
        title="Promo",
        content="<h1>Promo</h1>",
        status=LandingPageStatus.PUBLISHED,
    )
    await db_session.flush()
    return page


async def test_single_view_is_recorded_for_anonymous_visitor(client, db_session, organization):
    page = await _published_page(db_session, organization)

    response = await client.post(f"/api/v1/marketing/landing-pages/{page.id}/views", json={})

    assert response.status_code == 201, response.text
    assert response.json()["landing_page_id"] == str(page.id)


async def test_view_beacon_is_rate_limited_per_ip(client, db_session, organization):
    page = await _published_page(db_session, organization)
    url = f"/api/v1/marketing/landing-pages/{page.id}/views"

    # Up to the configured budget: all accepted (201).
    for _ in range(_LIMIT):
        ok = await client.post(url, json={})
        assert ok.status_code != 429, ok.text

    # One more from the same IP is throttled.
    throttled = await client.post(url, json={})
    assert throttled.status_code == 429
