"""
Placements job feed: jobs found on outside job sites (through their feeds / APIs), filtered to the kind of job the
organisation wants, shown to admins and students, with students applying on the original page.
"""

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from modules.placements import job_feed
from modules.placements.connectors import sources
from modules.placements.connectors.sources import JobItem, SourceError, plain_text
from modules.placements.job_feed import DEFAULT_KEYWORDS, is_fresher_friendly, keyword_pattern, wanted
from tests.api.test_placements import _create_student_with_login

pytestmark = pytest.mark.api

_FEED = "/api/v1/placements/external"


def _item(title="DevSecOps Intern", source="remotive", ext=None, **kw):
    return JobItem(
        source=source,
        external_id=ext or uuid.uuid4().hex[:10],
        title=title,
        company=kw.pop("company", "Acme"),
        url=kw.pop("url", "https://example.com/jobs/1"),
        **kw,
    )


# ---------------- reading job text ----------------


def test_job_text_is_turned_from_html_into_a_short_readable_summary():
    text = plain_text('<p class="x">Join <b>our</b> team &amp; grow.</p><script>alert(1)</script><ul><li>AWS</li><li>Linux</li></ul>')
    assert text == "Join our team & grow.\nAWS\nLinux"
    assert plain_text("") is None and plain_text("<p> </p>") is None
    long = plain_text("word " * 400)
    assert len(long) <= sources.MAX_SUMMARY_CHARS + 3 and long.endswith("...")


# ---------------- which jobs are kept ----------------


@pytest.mark.parametrize(
    "title, tags, job_type, expected",
    [
        ("DevSecOps Intern", [], None, (True, True)),
        ("Junior Cloud Engineer", ["aws"], "full_time", (True, True)),
        ("SOC Analyst (Entry level)", [], None, (True, True)),
        ("Cybersecurity Trainee", [], None, (True, True)),
        ("Cloud Security Engineer", ["internship"], None, (True, True)),  # fresher wording in the tags
        ("Junior React Developer", ["aws", "cloud"], None, (False, False)),  # a wanted word only in the tags is not enough
        ("Security Analyst", [], "internship", (True, True)),
        ("Senior DevOps Engineer", [], None, (False, False)),  # right role, but senior
        ("Lead Cybersecurity Architect", [], None, (False, False)),
        ("Marketing Intern", [], None, (False, False)),  # fresher, but not a wanted role
        ("Cloud Engineer", [], None, (False, False)),  # wanted role, nothing says fresher
        ("Junior Accountant", [], None, (False, False)),
    ],
)
def test_only_wanted_roles_that_suit_freshers_are_kept(title, tags, job_type, expected):
    pattern = keyword_pattern(DEFAULT_KEYWORDS)
    item = _item(title=title, tags=tags, job_type=job_type)
    keep, fresher = wanted(item, pattern, fresher_only=True)
    assert (keep, fresher) == expected


def test_switching_fresher_only_off_keeps_every_wanted_role():
    pattern = keyword_pattern(DEFAULT_KEYWORDS)
    assert wanted(_item(title="Cloud Engineer"), pattern, fresher_only=False) == (True, False)
    assert wanted(_item(title="Senior DevOps Engineer"), pattern, fresher_only=False) == (True, False)
    assert is_fresher_friendly(_item(title="Graduate Cyber Analyst"))


def test_a_keyword_must_be_a_word_not_part_of_one():
    pattern = keyword_pattern(["sre", "aws"])
    assert pattern.search("SRE Intern") and pattern.search("AWS Cloud")
    assert not pattern.search("Laundromat Assistant") and not pattern.search("Presrestore")


# ---------------- reading the real feeds (their documented shapes) ----------------


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_remotive_jobs_are_read_with_their_link_back():
    payload = {"jobs": [
        {"id": 7, "url": "https://remotive.com/remote-jobs/x/7", "title": "DevOps Intern", "company_name": "Unio",
         "category": "DevOps", "tags": ["aws", "linux"], "job_type": "internship", "publication_date": "2026-10-07T01:11:09",
         "candidate_required_location": "Worldwide", "salary": "", "description": "<p>Great <b>role</b></p>"},
        {"id": 8, "url": "javascript:alert(1)", "title": "Bad link", "company_name": "X"},
        {"id": 9, "url": "https://remotive.com/9", "title": ""},
    ]}
    items = await sources.fetch_remotive(_client(lambda request: httpx.Response(200, json=payload)))
    assert len(items) == 1
    job = items[0]
    assert (job.source, job.external_id, job.remote, job.job_type) == ("remotive", "7", True, "internship")
    assert job.url.startswith("https://remotive.com/") and job.summary == "Great role" and "aws" in job.tags
    assert job.posted_at == datetime(2026, 10, 7, 1, 11, 9, tzinfo=timezone.utc) and job.salary_text is None


async def test_arbeitnow_pages_are_followed_until_the_last():
    calls = []

    def handler(request):
        page = int(request.url.params["page"])
        calls.append(page)
        row = {"slug": f"job-{page}", "title": "Cloud Intern", "company_name": "Netlight", "url": f"https://www.arbeitnow.com/jobs/{page}",
               "remote": True, "tags": ["Berlin"], "job_types": ["Full time"], "location": "Berlin", "created_at": 1791511488,
               "description": "<div>x</div>"}
        return httpx.Response(200, json={"data": [row], "links": {"next": "x" if page < 2 else None}})

    items = await sources.fetch_arbeitnow(_client(handler))
    assert calls == [1, 2] and [i.external_id for i in items] == ["job-1", "job-2"]
    assert items[0].remote is True and items[0].job_type == "full_time" and items[0].posted_at.year == 2026


async def test_adzuna_and_jooble_read_their_search_results_and_dedupe(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "id")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "key")
    monkeypatch.setattr(settings, "JOOBLE_API_KEY", "jk")
    adzuna = {"results": [{"id": "55", "title": "<strong>SOC</strong> Analyst Fresher", "company": {"display_name": "Infy"},
                           "location": {"display_name": "Hyderabad, Telangana"}, "redirect_url": "https://www.adzuna.in/land/ad/55",
                           "created": "2026-10-08T10:00:00Z", "salary_min": 300000, "salary_max": 500000, "contract_time": "full_time",
                           "description": "Entry level role"}]}
    seen = []

    def adzuna_handler(request):
        seen.append(request.url.params["what"])
        return httpx.Response(200, json=adzuna)

    items = await sources.fetch_adzuna(_client(adzuna_handler))
    assert len(seen) == len(sources.SEARCH_QUERIES) and len(items) == 1  # same job from every search counts once
    assert items[0].title == "SOC Analyst Fresher" and items[0].salary_text == "INR 300,000 - 500,000"
    assert items[0].location == "Hyderabad, Telangana" and items[0].url == "https://www.adzuna.in/land/ad/55"

    jooble = {"jobs": [{"id": 9001, "title": "DevOps Intern", "company": "Zeta", "location": "Pune", "snippet": "Learn <b>CI/CD</b>",
                        "link": "https://in.jooble.org/desc/9001", "updated": "2026-10-08T00:00:00.0000000", "type": "Internship", "salary": ""}]}
    items = await sources.fetch_jooble(_client(lambda request: httpx.Response(200, json=jooble)))
    assert len(items) == 1 and items[0].summary == "Learn CI/CD" and items[0].job_type == "Internship"


async def test_a_source_that_fails_says_so_plainly():
    with pytest.raises(SourceError, match="status 503"):
        await sources.fetch_remotive(_client(lambda request: httpx.Response(503)))
    with pytest.raises(SourceError, match="unreadable"):
        await sources.fetch_remotive(_client(lambda request: httpx.Response(200, text="<html>not json</html>")))


# ---------------- through the API ----------------


@pytest.fixture
def feed(monkeypatch):
    """Replace the sources' real fetching with fixed jobs; returns the list to change between refreshes."""
    class Jobs(list):
        calls = {"remotive": 0}

    jobs = Jobs()
    calls = jobs.calls

    async def remotive(client):
        calls["remotive"] += 1
        return list(jobs)

    async def arbeitnow(client):
        return []

    monkeypatch.setitem(job_feed.FETCHERS, "remotive", remotive)
    monkeypatch.setitem(job_feed.FETCHERS, "arbeitnow", arbeitnow)
    return jobs


async def test_the_feed_keeps_wanted_jobs_and_both_admins_and_students_can_open_them(client, auth_headers, db_session, organization, feed):
    feed.extend([
        _item("DevSecOps Intern", ext="a", url="https://remotive.com/remote-jobs/devsecops-intern"),
        _item("Senior Cloud Architect", ext="b"),
        _item("Pastry Chef Trainee", ext="c"),
        _item("SOC Analyst Fresher", ext="d", location="Hyderabad"),
    ])
    student, student_headers = await _create_student_with_login(client, db_session, organization)

    assert (await client.get(f"{_FEED}/me", headers=student_headers)).json()["total"] == 0  # nothing read yet
    refreshed = await client.post(f"{_FEED}/refresh", headers=auth_headers)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["sources"]["remotive"] == {"fetched": 4, "matched": 2, "new": 2}
    assert "2 new jobs" in refreshed.json()["message"]

    admin_view = (await client.get(_FEED, headers=auth_headers)).json()
    assert sorted(j["title"] for j in admin_view["items"]) == ["DevSecOps Intern", "SOC Analyst Fresher"]
    mine = (await client.get(f"{_FEED}/me", headers=student_headers)).json()
    assert mine["total"] == 2
    top = next(j for j in mine["items"] if j["title"] == "DevSecOps Intern")
    assert top["url"] == "https://remotive.com/remote-jobs/devsecops-intern" and top["source"] == "remotive" and top["fresher_friendly"] is True
    # Search and source filters.
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", params={"q": "hyderabad"}, headers=student_headers)).json()["items"]] == ["SOC Analyst Fresher"]
    assert (await client.get(f"{_FEED}/me", params={"source": "jooble"}, headers=student_headers)).json()["total"] == 0


async def test_hiding_a_job_removes_it_for_students_but_not_for_admins_and_it_stays_hidden(client, auth_headers, db_session, organization, feed):
    feed.append(_item("DevOps Intern", ext="keep"))
    feed.append(_item("Cloud Trainee", ext="hide"))
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    await client.post(f"{_FEED}/refresh", headers=auth_headers)
    jobs = {j["title"]: j for j in (await client.get(_FEED, headers=auth_headers)).json()["items"]}

    hidden = await client.post(f"{_FEED}/{jobs['Cloud Trainee']['id']}/hidden", json={"hidden": True}, headers=auth_headers)
    assert hidden.status_code == 200 and hidden.json()["hidden"] is True
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", headers=student_headers)).json()["items"]] == ["DevOps Intern"]
    assert len((await client.get(_FEED, headers=auth_headers)).json()["items"]) == 2
    assert [j["title"] for j in (await client.get(_FEED, params={"include_hidden": "false"}, headers=auth_headers)).json()["items"]] == ["DevOps Intern"]

    # A later refresh finding the same job doesn't un-hide it.
    from modules.placements.job_feed import JobFeedService

    await JobFeedService(db_session).refresh(organization.id, force=True)
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", headers=student_headers)).json()["items"]] == ["DevOps Intern"]
    shown = await client.post(f"{_FEED}/{jobs['Cloud Trainee']['id']}/hidden", json={"hidden": False}, headers=auth_headers)
    assert shown.json()["hidden"] is False
    assert (await client.post(f"{_FEED}/{uuid.uuid4()}/hidden", json={"hidden": True}, headers=auth_headers)).status_code == 404


async def test_a_source_is_not_read_again_too_soon_and_jobs_that_leave_the_feed_disappear(client, auth_headers, db_session, organization, feed):
    from modules.placements.job_feed import JobFeedService

    feed.extend([_item("DevOps Intern", ext="1"), _item("Cloud Trainee", ext="2")])
    await client.post(f"{_FEED}/refresh", headers=auth_headers)
    again = await client.post(f"{_FEED}/refresh", headers=auth_headers)
    assert again.json()["sources"]["remotive"] == {"skipped": "read recently"} and feed.calls["remotive"] == 1

    feed.pop()  # "Cloud Trainee" left the source's feed
    summary = await JobFeedService(db_session).refresh(organization.id, force=True)
    assert summary["remotive"]["matched"] == 1 and feed.calls["remotive"] == 2
    assert [j["title"] for j in (await client.get(_FEED, headers=auth_headers)).json()["items"]] == ["DevOps Intern"]


async def test_a_failing_source_is_reported_and_the_others_still_load(client, auth_headers, feed, monkeypatch):
    async def broken(client):
        raise SourceError("the site answered with status 503")

    monkeypatch.setitem(job_feed.FETCHERS, "arbeitnow", broken)
    feed.append(_item("Cloud Intern", ext="z"))
    summary = (await client.post(f"{_FEED}/refresh", headers=auth_headers)).json()["sources"]
    assert summary["arbeitnow"] == {"error": "the site answered with status 503"} and summary["remotive"]["new"] == 1
    status = {s["name"]: s for s in (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()["sources"]}
    assert status["arbeitnow"]["last_error"] == "the site answered with status 503" and status["remotive"]["last_error"] is None


async def test_settings_show_which_sources_need_a_key_and_validate_changes(client, auth_headers, feed):
    settings_ = (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()
    assert settings_["fresher_only"] is True and "devsecops" in settings_["keywords"]
    by_name = {s["name"]: s for s in settings_["sources"]}
    assert by_name["remotive"]["enabled"] and by_name["remotive"]["configured"]
    assert by_name["adzuna"]["configured"] is False and by_name["adzuna"]["enabled"] is False  # no API key on the server

    ok = await client.put(f"{_FEED}/settings", json={"keywords": ["  DevSecOps ", "devsecops", "Pen Testing"], "fresher_only": False, "sources": {"remotive": False}}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["keywords"] == ["devsecops", "pen testing"] and ok.json()["fresher_only"] is False
    assert {s["name"]: s["enabled"] for s in ok.json()["sources"]}["remotive"] is False
    assert (await client.put(f"{_FEED}/settings", json={"sources": {"linkedin": True}}, headers=auth_headers)).status_code == 422
    assert (await client.put(f"{_FEED}/settings", json={"keywords": ["  ", ""]}, headers=auth_headers)).status_code == 422

    # With remotive switched off nothing is read from it.
    feed.append(_item("DevSecOps Intern"))
    refreshed = (await client.post(f"{_FEED}/refresh", headers=auth_headers)).json()["sources"]
    assert "remotive" not in refreshed and feed.calls["remotive"] == 0


async def test_who_can_do_what(client, auth_headers, db_session, organization, staff_headers, feed):
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    for method, path in (("get", _FEED), ("get", f"{_FEED}/settings"), ("post", f"{_FEED}/refresh"), ("put", f"{_FEED}/settings")):
        assert (await getattr(client, method)(path, headers=student_headers)).status_code == 403, path
        assert (await getattr(client, method)(path, headers=staff_headers)).status_code == 403, path
        assert (await getattr(client, method)(path)).status_code in (401, 403), path
    assert (await client.get(f"{_FEED}/me", headers=auth_headers)).status_code in (403, 404, 422)  # not a student (an account with no student record)
    assert (await client.get(f"{_FEED}/me")).status_code in (401, 403)
