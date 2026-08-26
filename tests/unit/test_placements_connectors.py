"""
Unit tests for the job-board connectors — pure request/response-mapping
logic, no database (budget-check DB calls are mocked out via
`unittest.mock.patch`, matching `tests/api/test_provisioning.py`'s style).
Network calls are intercepted with `httpx.MockTransport`, the same pattern
`tests/unit/test_notifications.py` uses for the SMS/WhatsApp clients.
"""

from unittest.mock import patch

import httpx
import pytest

from modules.placements.connectors import adzuna, arbeitnow, jooble, reed

pytestmark = pytest.mark.unit


def _patch_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    class _FakeAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


# ---- Adzuna ----


async def test_adzuna_skips_cleanly_without_credentials(monkeypatch):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"results": []})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_ID", "")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_KEY", "")

    result = await adzuna.fetch_postings(["security engineer"], db=None)

    assert result.status == "skipped_no_credentials"
    assert result.postings == []
    assert calls["count"] == 0


async def test_adzuna_normalizes_sample_response(monkeypatch):
    sample_job = {
        "id": 12345,
        "title": "SOC Analyst",
        "company": {"display_name": "Acme Security"},
        "location": {"display_name": "Bengaluru, India"},
        "salary_min": 800000,
        "salary_max": 1200000,
        "description": "Monitor and respond to security incidents.",
        "redirect_url": "https://www.adzuna.in/land/ad/12345",
        "created": "2026-08-01T10:00:00Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [sample_job]})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_ID", "test-id")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_KEY", "test-key")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_DAILY_CALL_BUDGET", 240)

    with patch(
        "modules.placements.connectors.adzuna.AggregationRunSourceRepository.sum_request_count",
        return_value=0,
    ):
        result = await adzuna.fetch_postings(["soc analyst"], db=None)

    assert result.status == "success"
    assert result.request_count == 1
    assert len(result.postings) == 1
    posting = result.postings[0]
    assert posting.source == "adzuna"
    assert posting.external_id == "12345"
    assert posting.title == "SOC Analyst"
    assert posting.company == "Acme Security"
    assert posting.location == "Bengaluru, India"
    assert posting.salary_min == 800000
    assert posting.source_url == "https://www.adzuna.in/land/ad/12345"


async def test_adzuna_skips_when_daily_budget_exhausted(monkeypatch):
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_ID", "test-id")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_KEY", "test-key")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_DAILY_CALL_BUDGET", 240)

    with patch(
        "modules.placements.connectors.adzuna.AggregationRunSourceRepository.sum_request_count",
        return_value=240,
    ):
        result = await adzuna.fetch_postings(["soc analyst"], db=None)

    assert result.status == "skipped_budget"
    assert result.postings == []


async def test_adzuna_mocked_500_does_not_raise(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_ID", "test-id")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_APP_KEY", "test-key")
    monkeypatch.setattr(adzuna.settings, "ADZUNA_DAILY_CALL_BUDGET", 240)

    with patch(
        "modules.placements.connectors.adzuna.AggregationRunSourceRepository.sum_request_count",
        return_value=0,
    ):
        result = await adzuna.fetch_postings(["soc analyst"], db=None)

    # A 5xx must not raise — the connector logs it, moves on, and the run
    # (or the other connectors in it) is unaffected.
    assert result.postings == []
    assert result.request_count == 1


# ---- Jooble ----


async def test_jooble_skips_cleanly_without_credentials(monkeypatch):
    monkeypatch.setattr(jooble.settings, "JOOBLE_API_KEY", "")

    result = await jooble.fetch_postings(["soc analyst"], db=None)

    assert result.status == "skipped_no_credentials"
    assert result.postings == []


async def test_jooble_normalizes_sample_response(monkeypatch):
    sample_response = {
        "totalCount": 1,
        "jobs": [
            {
                "id": 987,
                "title": "Penetration Tester",
                "location": "Mumbai",
                "snippet": "Perform authorized penetration tests.",
                "salary": "₹15,00,000 a year",
                "source": "example.com",
                "type": "Full-time",
                "link": "https://jooble.org/jdp/987",
                "company": "Beta InfoSec",
                "updated": "2026-08-01T00:00:00",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample_response)

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(jooble.settings, "JOOBLE_API_KEY", "test-key")
    monkeypatch.setattr(jooble.settings, "JOOBLE_LIFETIME_CALL_BUDGET", 450)

    with patch(
        "modules.placements.connectors.jooble.AggregationRunSourceRepository.sum_request_count",
        return_value=0,
    ):
        result = await jooble.fetch_postings(["penetration tester"], db=None)

    assert result.status == "success"
    assert result.request_count == 1
    assert len(result.postings) == 1
    posting = result.postings[0]
    assert posting.source == "jooble"
    assert posting.external_id == "987"
    assert posting.title == "Penetration Tester"
    assert posting.company == "Beta InfoSec"
    assert posting.source_url == "https://jooble.org/jdp/987"


async def test_jooble_skips_when_lifetime_budget_exhausted(monkeypatch):
    monkeypatch.setattr(jooble.settings, "JOOBLE_API_KEY", "test-key")
    monkeypatch.setattr(jooble.settings, "JOOBLE_LIFETIME_CALL_BUDGET", 450)

    with patch(
        "modules.placements.connectors.jooble.AggregationRunSourceRepository.sum_request_count",
        return_value=450,
    ):
        result = await jooble.fetch_postings(["penetration tester"], db=None)

    assert result.status == "skipped_budget"
    assert result.postings == []


async def test_jooble_mocked_timeout_does_not_raise(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(jooble.settings, "JOOBLE_API_KEY", "test-key")
    monkeypatch.setattr(jooble.settings, "JOOBLE_LIFETIME_CALL_BUDGET", 450)

    with patch(
        "modules.placements.connectors.jooble.AggregationRunSourceRepository.sum_request_count",
        return_value=0,
    ):
        result = await jooble.fetch_postings(["penetration tester"], db=None)

    assert result.status == "error"
    assert result.postings == []


# ---- Reed ----


async def test_reed_skips_cleanly_without_credentials(monkeypatch):
    monkeypatch.setattr(reed.settings, "REED_API_KEY", "")

    result = await reed.fetch_postings(["soc analyst"], db=None)

    assert result.status == "skipped_no_credentials"
    assert result.postings == []


async def test_reed_normalizes_sample_response(monkeypatch):
    sample_job = {
        "jobId": 555,
        "jobTitle": "Cloud Security Engineer",
        "employerName": "Gamma Corp",
        "locationName": "London",
        "minimumSalary": 60000,
        "maximumSalary": 80000,
        "jobDescription": "Secure our cloud infrastructure.",
        "date": "01/08/2026",
        "jobUrl": "https://www.reed.co.uk/jobs/555",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [sample_job]})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(reed.settings, "REED_API_KEY", "test-key")

    result = await reed.fetch_postings(["cloud security"], db=None)

    assert result.status == "success"
    assert len(result.postings) == 1
    posting = result.postings[0]
    assert posting.source == "reed"
    assert posting.external_id == "555"
    assert posting.title == "Cloud Security Engineer"
    assert posting.company == "Gamma Corp"
    assert posting.salary_min == 60000
    assert posting.source_url == "https://www.reed.co.uk/jobs/555"


async def test_reed_mocked_500_does_not_raise(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    _patch_transport(monkeypatch, handler)
    monkeypatch.setattr(reed.settings, "REED_API_KEY", "test-key")

    result = await reed.fetch_postings(["cloud security"], db=None)

    assert result.postings == []


# ---- Arbeitnow ----


async def test_arbeitnow_requires_no_credentials_and_normalizes_sample_response(monkeypatch):
    # Real Arbeitnow `description` values are HTML-ENTITY-ENCODED HTML —
    # confirmed against the live API, not assumed — i.e. the raw JSON
    # string is literally "&lt;p&gt;...&lt;/p&gt;", not "<p>...</p>". A
    # fixture using already-literal HTML here previously masked a real
    # unescape/strip ordering bug in `_strip_html` (it happened to work on
    # literal HTML regardless of order, but silently no-op'd on entity-
    # encoded HTML, leaving raw tags in stored descriptions) — this
    # fixture matches the real wire format specifically so that bug class
    # cannot pass silently again. It also includes "&amp;nbsp;" (a real
    # HTML entity belonging to the underlying content, doubly-encoded
    # alongside the outer tag encoding — confirmed against a real live
    # posting) to catch the follow-up bug where a single unescape pass
    # left "&nbsp;" literally in the stored description.
    sample_job = {
        "slug": "security-engineer-acme-1234",
        "company_name": "Acme GmbH",
        "title": "Security Engineer",
        "description": "&lt;p&gt;Join our&amp;nbsp;&lt;b&gt;security&lt;/b&gt; team.&lt;/p&gt;",
        "remote": True,
        "url": "https://www.arbeitnow.com/view/security-engineer-acme-1234",
        "tags": ["Security", "Engineering"],
        "job_types": ["Full-time"],
        "location": "Berlin",
        "created_at": 1754000000,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [sample_job], "links": {"next": None}})

    _patch_transport(monkeypatch, handler)

    result = await arbeitnow.fetch_postings(["security"], db=None)

    assert result.status == "success"
    assert len(result.postings) == 1
    posting = result.postings[0]
    assert posting.source == "arbeitnow"
    assert posting.external_id == "security-engineer-acme-1234"
    assert posting.remote is True
    assert "security" in posting.description.lower()
    assert "<b>" not in posting.description
    assert "&lt;" not in posting.description  # entities were unescaped, not just left encoded
    assert "&nbsp;" not in posting.description  # second unescape pass resolved the inner entity too
    assert posting.description.strip() == "Join our security team."
    assert posting.source_url == "https://www.arbeitnow.com/view/security-engineer-acme-1234"


async def test_arbeitnow_filters_out_non_matching_keywords(monkeypatch):
    sample_job = {
        "slug": "barista-cafe-5678",
        "company_name": "Cafe Co",
        "title": "Barista",
        "description": "Make coffee.",
        "remote": False,
        "url": "https://www.arbeitnow.com/view/barista-cafe-5678",
        "tags": ["Hospitality"],
        "job_types": [],
        "location": "Munich",
        "created_at": 1754000000,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [sample_job], "links": {"next": None}})

    _patch_transport(monkeypatch, handler)

    result = await arbeitnow.fetch_postings(["cybersecurity", "SOC analyst"], db=None)

    assert result.status == "success"
    assert result.postings == []


async def test_arbeitnow_mocked_timeout_does_not_raise(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    _patch_transport(monkeypatch, handler)

    result = await arbeitnow.fetch_postings(["security"], db=None)

    assert result.postings == []
