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
        remote=kw.pop("remote", True),
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
        ("Security Analyst", [], "internship", (True, True)),
        ("Senior DevOps Engineer", [], None, (True, False)),  # kept (every wanted role is), not marked fresher friendly
        ("Lead Cybersecurity Architect", [], None, (True, False)),
        ("Cloud Engineer", [], None, (True, False)),
        ("Marketing Intern", [], None, (False, False)),  # fresher, but not a wanted role
        ("Junior Accountant", [], None, (False, False)),
        ("Junior React Developer", ["aws", "cloud"], None, (False, False)),  # a wanted word only in the tags is not enough
    ],
)
def test_every_wanted_role_is_kept_and_fresher_friendly_ones_are_marked(title, tags, job_type, expected):
    pattern = keyword_pattern(DEFAULT_KEYWORDS)
    item = _item(title=title, tags=tags, job_type=job_type)
    assert wanted(item, pattern) == expected


def test_the_fresher_marking_ignores_senior_titles():
    assert is_fresher_friendly(_item(title="Graduate Cyber Analyst"))
    assert not is_fresher_friendly(_item(title="Senior Graduate Programme Lead"))


def test_a_keyword_must_be_a_word_not_part_of_one():
    pattern = keyword_pattern(["sre", "aws"])
    assert pattern.search("SRE Intern") and pattern.search("AWS Cloud")
    assert not pattern.search("Laundromat Assistant") and not pattern.search("Presrestore")


def test_guards_and_officers_are_not_it_jobs_even_though_the_word_security_matches():
    pattern = keyword_pattern(DEFAULT_KEYWORDS)
    assert wanted(_item(title="Security Guard"), pattern) == (False, False)
    assert wanted(_item(title="Security Officer - Night Shift"), pattern) == (False, False)
    assert wanted(_item(title="Product Security Engineer"), pattern)[0] is True
    assert wanted(_item(title="Linux System Administrator"), pattern)[0] is True


@pytest.mark.parametrize(
    "location, remote, source, expected",
    [
        ("Bengaluru, India", False, "greenhouse", True),
        ("Hyderabad", False, "lever", True),
        ("Remote - India", True, "greenhouse", True),
        ("Worldwide", True, "remotive", True),
        ("Anywhere", True, "remotive", True),
        (None, True, "remotive", True),
        ("USA Only", True, "remotive", False),
        ("Berlin", False, "arbeitnow", False),
        ("Remote (Homeoffice)", True, "arbeitnow", False),
        ("San Francisco, CA", False, "greenhouse", False),
        ("Pune", False, "greenhouse", True),
        ("Mumbai, Maharashtra", False, "adzuna", True),
        ("Somewhere unlisted", False, "adzuna", True),  # their searches are already limited to India
    ],
)
def test_only_jobs_in_india_or_remote_and_open_to_india_pass_the_india_filter(location, remote, source, expected):
    assert job_feed.in_india_or_open(_item(location=location, remote=remote, source=source)) is expected


def test_company_board_names_are_validated_and_tidied():
    assert job_feed.clean_boards({"greenhouse": [" Okta ", "okta", "Data-Dog"], "lever": ["cred"]}) == {"greenhouse": ["okta", "data-dog"], "lever": ["cred"]}
    for bad in ({"workday": ["x"]}, {"greenhouse": ["has space"]}, {"greenhouse": ["a"]}, {"greenhouse": ["../etc"]}, {"lever": [f"c{i:03d}" for i in range(121)]}):
        with pytest.raises(job_feed.ValidationError):
            job_feed.clean_boards(bad)


# ---------------- years of experience ----------------


@pytest.mark.parametrize(
    "title, summary, job_type, expected",
    [
        ("Cloud Engineer", "We need 3-5 years of experience in AWS", None, (3, 5, False)),
        ("Cloud Engineer", "Experience: 2 to 4 yrs with Kubernetes", None, (2, 4, False)),
        ("Security Engineer", "5+ years of hands-on experience", None, (5, None, False)),
        ("SOC Analyst", "Minimum 2 years experience in a SOC", None, (2, None, False)),
        ("DevOps Engineer", "At least 4 years' relevant experience", None, (4, None, False)),
        ("Cloud Engineer", "1 year of experience", None, (1, None, False)),
        ("DevOps Trainee", "0-2 years experience, freshers welcome", None, (0, 2, False)),
        ("Security Analyst", "Freshers can apply", None, (0, 1, False)),
        ("Security Analyst", "Entry level role", None, (0, 1, False)),
        ("Analyst", "A company founded 25+ years ago with 10 years of growth", None, (None, None, False)),  # not experience
        ("Cloud Engineer", "Great place to work", None, (None, None, False)),
        ("Cloud Engineer", "3-5 years", None, (None, None, False)),  # a bare range with no mention of experience
        ("Senior DevOps Engineer", None, None, (5, None, True)),
        ("Sr. Cloud Engineer", "", None, (5, None, True)),
        ("Principal Security Architect", None, None, (8, None, True)),
        ("Engineering Manager, Security", None, None, (8, None, True)),
        ("Junior SOC Analyst", None, None, (0, 2, True)),
        ("Cyber Security Intern", None, None, (0, 1, True)),
        ("Security Analyst", None, "internship", (0, 1, True)),
        ("Senior Cloud Engineer", "Requires 8-10 years of experience", None, (8, 10, False)),  # the text beats the title
        ("Cloud Engineer", "Experience: 99 years", None, (None, None, False)),
    ],
)
def test_years_of_experience_are_read_from_the_text_then_guessed_from_the_title(title, summary, job_type, expected):
    from modules.placements.experience import extract_experience

    assert extract_experience(title, summary, job_type) == expected


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
    items = await sources.fetch_remotive(_client(lambda request: httpx.Response(200, json=payload)), {})
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

    items = await sources.fetch_arbeitnow(_client(handler), {})
    assert calls == [1, 2] and [i.external_id for i in items] == ["job-1", "job-2"]
    assert items[0].remote is True and items[0].job_type == "full_time" and items[0].posted_at.year == 2026


async def test_adzuna_and_jooble_read_their_search_results_and_dedupe(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "id")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "key")
    monkeypatch.setattr(settings, "JOOBLE_API_KEY", "jk")
    monkeypatch.setattr(sources, "REQUEST_GAP_SECONDS", 0)
    monkeypatch.setattr(sources, "ADZUNA_PAGES", 1)
    adzuna = {"results": [{"id": "55", "title": "<strong>SOC</strong> Analyst Fresher", "company": {"display_name": "Infy"},
                           "location": {"display_name": "Hyderabad, Telangana"}, "redirect_url": "https://www.adzuna.in/land/ad/55",
                           "created": "2026-10-08T10:00:00Z", "salary_min": 300000, "salary_max": 500000, "contract_time": "full_time",
                           "description": "Entry level role"}]}
    seen = []

    def adzuna_handler(request):
        seen.append(request.url.params["what"])
        return httpx.Response(200, json=adzuna)

    items = await sources.fetch_adzuna(_client(adzuna_handler), {})
    assert len(seen) == len(sources.SEARCH_QUERIES) and len(items) == 1  # same job from every search counts once
    assert items[0].title == "SOC Analyst Fresher" and items[0].salary_text == "INR 300,000 - 500,000"
    assert items[0].location == "Hyderabad, Telangana" and items[0].url == "https://www.adzuna.in/land/ad/55"

    jooble = {"jobs": [{"id": 9001, "title": "DevOps Intern", "company": "Zeta", "location": "Pune", "snippet": "Learn <b>CI/CD</b>",
                        "link": "https://in.jooble.org/desc/9001", "updated": "2026-10-08T00:00:00.0000000", "type": "Internship", "salary": ""}]}
    items = await sources.fetch_jooble(_client(lambda request: httpx.Response(200, json=jooble)), {})
    assert len(items) == 1 and items[0].summary == "Learn CI/CD" and items[0].job_type == "Internship"


async def test_adzuna_follows_pages_for_each_search_until_a_short_page(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADZUNA_APP_ID", "id")
    monkeypatch.setattr(settings, "ADZUNA_APP_KEY", "key")
    monkeypatch.setattr(sources, "REQUEST_GAP_SECONDS", 0)
    monkeypatch.setattr(sources, "SEARCH_QUERIES", ["devops engineer", "soc analyst"])
    monkeypatch.setattr(sources, "ADZUNA_PAGES", 3)
    requested = []

    def handler(request):
        page = int(str(request.url.path).rsplit("/", 1)[1])
        what = request.url.params["what"]
        requested.append((what, page))
        count = 50 if page < 2 else 10  # the second page is the last
        rows = [{"id": f"{what}-{page}-{n}", "title": f"DevOps Engineer {n}", "company": {"display_name": "Acme"}, "location": {"display_name": "Pune"},
                 "redirect_url": f"https://www.adzuna.in/land/{what}-{page}-{n}", "created": "2026-10-08T10:00:00Z"} for n in range(count)]
        return httpx.Response(200, json={"results": rows})

    items = await sources.fetch_adzuna(_client(handler), {})
    assert requested == [("devops engineer", 1), ("devops engineer", 2), ("soc analyst", 1), ("soc analyst", 2)]
    assert len(items) == 120 and {i.location for i in items} == {"Pune"}


async def test_company_career_pages_are_read_from_greenhouse_and_lever_and_a_missing_page_is_skipped():
    def handler(request):
        url = str(request.url)
        if "greenhouse.io/v1/boards/okta/jobs" in url:
            return httpx.Response(200, json={"jobs": [
                {"id": 11, "title": "Cloud Security Engineer", "absolute_url": "https://boards.greenhouse.io/okta/jobs/11",
                 "location": {"name": "Bengaluru, India"}, "updated_at": "2026-10-05T10:00:00-04:00"},
                {"id": 12, "title": "Bad link", "absolute_url": "javascript:x", "location": {"name": "Pune"}},
            ]})
        if "greenhouse.io/v1/boards/ghost/jobs" in url:
            return httpx.Response(404)
        if "api.lever.co/v0/postings/cred" in url:
            return httpx.Response(200, json=[{"id": "abc", "text": "DevOps Intern", "hostedUrl": "https://jobs.lever.co/cred/abc",
                                              "categories": {"location": "Bangalore", "team": "Platform", "commitment": "Intern"},
                                              "workplaceType": "hybrid", "createdAt": 1791511488000, "descriptionPlain": "Learn CI/CD"}])
        return httpx.Response(404)

    greenhouse = await sources.fetch_greenhouse(_client(handler), {"greenhouse": ["okta", "ghost"]})
    assert [(j.external_id, j.title, j.location, j.company) for j in greenhouse] == [("okta:11", "Cloud Security Engineer", "Bengaluru, India", "Okta")]
    assert greenhouse[0].url == "https://boards.greenhouse.io/okta/jobs/11" and greenhouse[0].posted_at.year == 2026
    lever = await sources.fetch_lever(_client(handler), {"lever": ["cred"]})
    assert lever[0].external_id == "cred:abc" and lever[0].job_type == "intern" and lever[0].summary == "Learn CI/CD" and lever[0].tags == ["Platform"]
    assert lever[0].posted_at.year == 2026 and lever[0].remote is False

    with pytest.raises(SourceError, match="none of the company career pages"):
        await sources.fetch_greenhouse(_client(handler), {"greenhouse": ["ghost", "ghost2"]})
    assert await sources.fetch_lever(_client(handler), {}) == []  # nothing listed


async def test_a_source_that_fails_says_so_plainly():
    with pytest.raises(SourceError, match="status 503"):
        await sources.fetch_remotive(_client(lambda request: httpx.Response(503)), {})
    with pytest.raises(SourceError, match="unreadable"):
        await sources.fetch_remotive(_client(lambda request: httpx.Response(200, text="<html>not json</html>")), {})


# ---------------- through the API ----------------


@pytest.fixture
def feed(monkeypatch):
    """Replace every source's real fetching with fixed jobs; returns the list "remotive" serves."""

    class Jobs(list):
        calls = {"remotive": 0}
        queued: list = []

    jobs = Jobs()
    calls = jobs.calls
    jobs.queued = []

    async def remotive(client, options):
        calls["remotive"] += 1
        return list(jobs)

    async def nothing(client, options):
        return []

    for name in job_feed.FETCHERS:
        monkeypatch.setitem(job_feed.FETCHERS, name, remotive if name == "remotive" else nothing)
    from modules.placements import routes

    monkeypatch.setattr(routes, "enqueue_job_feed_refresh", lambda organization_id: jobs.queued.append(organization_id) or True)
    return jobs


async def _refresh(client, auth_headers, db_session, organization, force=False):
    """Press Refresh now, then do what the background worker does."""
    started = await client.post(f"{_FEED}/refresh", headers=auth_headers)
    assert started.status_code == 200, started.text
    return await job_feed.JobFeedService(db_session).run_refresh(organization.id, force=force)


async def test_refresh_now_starts_a_background_run_and_a_second_press_does_not_start_another(client, auth_headers, db_session, organization, feed):
    first = await client.post(f"{_FEED}/refresh", headers=auth_headers)
    assert first.status_code == 200 and "Checking the job sites" in first.json()["message"] and feed.queued == [organization.id]
    assert (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()["refreshing"] is True
    second = await client.post(f"{_FEED}/refresh", headers=auth_headers)
    assert "already being checked" in second.json()["message"] and feed.queued == [organization.id]
    await job_feed.JobFeedService(db_session).run_refresh(organization.id)  # the worker finishes
    assert (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()["refreshing"] is False
    assert (await client.post(f"{_FEED}/refresh", headers=auth_headers)).status_code == 200 and len(feed.queued) == 2


async def test_a_refresh_that_could_not_be_queued_says_so_and_is_not_left_marked_as_running(client, auth_headers, feed, monkeypatch):
    from modules.placements import routes

    monkeypatch.setattr(routes, "enqueue_job_feed_refresh", lambda organization_id: False)
    failed = await client.post(f"{_FEED}/refresh", headers=auth_headers)
    assert failed.status_code == 503
    assert (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()["refreshing"] is False


async def test_the_feed_keeps_every_wanted_job_in_india_for_admins_and_students(client, auth_headers, db_session, organization, feed):
    feed.extend([
        _item("DevSecOps Intern", ext="a", url="https://remotive.com/remote-jobs/devsecops-intern"),
        _item("Senior Cloud Architect", ext="b"),
        _item("Pastry Chef Trainee", ext="c"),
        _item("SOC Analyst Fresher", ext="d", location="Hyderabad", remote=False),
        _item("Cloud Engineer", ext="e", location="USA Only"),  # not open to India
        _item("Security Guard", ext="f"),
    ])
    student, student_headers = await _create_student_with_login(client, db_session, organization)

    assert (await client.get(f"{_FEED}/me", headers=student_headers)).json()["total"] == 0  # nothing read yet
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert summary["remotive"] == {"fetched": 6, "matched": 3, "new": 3}

    admin_view = (await client.get(_FEED, headers=auth_headers)).json()
    assert sorted(j["title"] for j in admin_view["items"]) == ["DevSecOps Intern", "SOC Analyst Fresher", "Senior Cloud Architect"]
    mine = (await client.get(f"{_FEED}/me", headers=student_headers)).json()
    assert mine["total"] == 3
    top = next(j for j in mine["items"] if j["title"] == "DevSecOps Intern")
    assert top["url"] == "https://remotive.com/remote-jobs/devsecops-intern" and top["source"] == "remotive" and top["fresher_friendly"] is True
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", params={"q": "hyderabad"}, headers=student_headers)).json()["items"]] == ["SOC Analyst Fresher"]
    assert (await client.get(f"{_FEED}/me", params={"source": "jooble"}, headers=student_headers)).json()["total"] == 0


async def test_switching_off_the_india_filter_keeps_jobs_from_anywhere(client, auth_headers, db_session, organization, feed):
    feed.extend([_item("Cloud Engineer", ext="u", location="USA Only"), _item("Cloud Intern", ext="i")])
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert summary["remotive"]["matched"] == 1  # only the one open to India
    await client.put(f"{_FEED}/settings", json={"india_only": False}, headers=auth_headers)
    summary = await _refresh(client, auth_headers, db_session, organization, force=True)
    assert summary["remotive"]["matched"] == 2


async def test_jobs_are_listed_newest_posting_first_and_undated_ones_last(client, auth_headers, db_session, organization, feed):
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    feed.extend([
        _item("Cloud Engineer Old", ext="old", posted_at=now - timedelta(days=20)),
        _item("Cloud Engineer Undated", ext="none"),
        _item("Cloud Engineer New", ext="new", posted_at=now - timedelta(hours=2)),
        _item("Cloud Engineer Mid", ext="mid", posted_at=now - timedelta(days=3)),
    ])
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    await _refresh(client, auth_headers, db_session, organization)
    order = ["Cloud Engineer New", "Cloud Engineer Mid", "Cloud Engineer Old", "Cloud Engineer Undated"]
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", headers=student_headers)).json()["items"]] == order
    assert [j["title"] for j in (await client.get(_FEED, headers=auth_headers)).json()["items"]] == order


async def test_jobs_carry_their_experience_and_can_be_filtered_by_range(client, auth_headers, db_session, organization, feed):
    feed.extend([
        _item("Cloud Engineer Fresher", ext="a", summary="0-2 years experience"),
        _item("Cloud Engineer Mid", ext="b", summary="3-5 years of experience"),
        _item("Cloud Engineer Senior", ext="c", summary="7+ years of experience"),
        _item("Cloud Engineer Open", ext="d", summary="5+ years of experience"),
        _item("Cloud Engineer Plain", ext="e", summary="Nice team"),
        _item("Senior Cloud Engineer Guess", ext="f"),
    ])
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    await _refresh(client, auth_headers, db_session, organization)

    def titles(response):
        return sorted(j["title"] for j in response.json()["items"])

    everything = {j["title"]: j for j in (await client.get(_FEED, headers=auth_headers)).json()["items"]}
    assert (everything["Cloud Engineer Mid"]["experience_min"], everything["Cloud Engineer Mid"]["experience_max"], everything["Cloud Engineer Mid"]["experience_estimated"]) == (3, 5, False)
    assert (everything["Cloud Engineer Open"]["experience_min"], everything["Cloud Engineer Open"]["experience_max"]) == (5, None)
    assert everything["Cloud Engineer Plain"]["experience_min"] is None and everything["Senior Cloud Engineer Guess"]["experience_estimated"] is True

    async def filtered(value, headers=auth_headers, path=_FEED):
        return titles(await client.get(path, params={"experience": value}, headers=headers))

    assert await filtered("0-3") == ["Cloud Engineer Fresher", "Cloud Engineer Mid"]
    assert await filtered("1-5") == ["Cloud Engineer Fresher", "Cloud Engineer Mid", "Cloud Engineer Open", "Senior Cloud Engineer Guess"]
    assert await filtered("3-7") == ["Cloud Engineer Mid", "Cloud Engineer Open", "Cloud Engineer Senior", "Senior Cloud Engineer Guess"]
    assert await filtered("7+") == ["Cloud Engineer Open", "Cloud Engineer Senior", "Senior Cloud Engineer Guess"]
    assert await filtered("unknown") == ["Cloud Engineer Plain"]
    # Students can filter the same way.
    assert await filtered("0-3", student_headers, f"{_FEED}/me") == ["Cloud Engineer Fresher", "Cloud Engineer Mid"]
    assert (await client.get(_FEED, params={"experience": "banana"}, headers=auth_headers)).status_code == 422


async def test_jobs_saved_before_experience_was_tracked_are_read_by_the_next_refresh(client, auth_headers, db_session, organization, feed):
    from sqlalchemy import update

    from modules.placements.models import ExternalJob

    feed.append(_item("Cloud Engineer Mid", ext="b", summary="3-5 years of experience"))
    await _refresh(client, auth_headers, db_session, organization)
    await db_session.execute(update(ExternalJob).values(experience_min=None, experience_max=None, experience_parsed=False))
    await db_session.flush()
    assert (await client.get(_FEED, headers=auth_headers)).json()["items"][0]["experience_min"] is None
    assert await job_feed.JobFeedService(db_session).backfill_experience(organization.id) == 1
    job = (await client.get(_FEED, headers=auth_headers)).json()["items"][0]
    assert (job["experience_min"], job["experience_max"]) == (3, 5)
    assert await job_feed.JobFeedService(db_session).backfill_experience(organization.id) == 0  # nothing left to read


async def test_hiding_a_job_removes_it_for_students_but_not_for_admins_and_it_stays_hidden(client, auth_headers, db_session, organization, feed):
    feed.append(_item("DevOps Intern", ext="keep"))
    feed.append(_item("Cloud Trainee", ext="hide"))
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    await _refresh(client, auth_headers, db_session, organization)
    jobs = {j["title"]: j for j in (await client.get(_FEED, headers=auth_headers)).json()["items"]}

    hidden = await client.post(f"{_FEED}/{jobs['Cloud Trainee']['id']}/hidden", json={"hidden": True}, headers=auth_headers)
    assert hidden.status_code == 200 and hidden.json()["hidden"] is True
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", headers=student_headers)).json()["items"]] == ["DevOps Intern"]
    assert len((await client.get(_FEED, headers=auth_headers)).json()["items"]) == 2
    assert [j["title"] for j in (await client.get(_FEED, params={"include_hidden": "false"}, headers=auth_headers)).json()["items"]] == ["DevOps Intern"]

    # A later refresh finding the same job doesn't un-hide it.
    await job_feed.JobFeedService(db_session).refresh(organization.id, force=True)
    assert [j["title"] for j in (await client.get(f"{_FEED}/me", headers=student_headers)).json()["items"]] == ["DevOps Intern"]
    shown = await client.post(f"{_FEED}/{jobs['Cloud Trainee']['id']}/hidden", json={"hidden": False}, headers=auth_headers)
    assert shown.json()["hidden"] is False
    assert (await client.post(f"{_FEED}/{uuid.uuid4()}/hidden", json={"hidden": True}, headers=auth_headers)).status_code == 404


async def test_a_source_is_not_read_again_too_soon_and_jobs_that_leave_the_feed_disappear(client, auth_headers, db_session, organization, feed):
    feed.extend([_item("DevOps Intern", ext="1"), _item("Cloud Trainee", ext="2")])
    await _refresh(client, auth_headers, db_session, organization)
    again = await _refresh(client, auth_headers, db_session, organization)
    assert again["remotive"] == {"skipped": "read recently"} and feed.calls["remotive"] == 1

    feed.pop()  # "Cloud Trainee" left the source's feed
    summary = await job_feed.JobFeedService(db_session).refresh(organization.id, force=True)
    assert summary["remotive"]["matched"] == 1 and feed.calls["remotive"] == 2
    assert [j["title"] for j in (await client.get(_FEED, headers=auth_headers)).json()["items"]] == ["DevOps Intern"]


async def test_an_employer_listing_hundreds_of_places_does_not_break_the_refresh(client, auth_headers, db_session, organization, feed, monkeypatch):
    places = "; ".join([f"City{i}, USA, Remote" for i in range(120)] + ["Bengaluru, India"])
    assert len(places) > 1000
    long_job = _item("Product Security Engineer", source="greenhouse", ext="datadog:1", location=places, remote=False, job_type="x" * 80, salary_text="y" * 300)

    async def greenhouse(client, options):
        return [long_job]

    monkeypatch.setitem(job_feed.FETCHERS, "greenhouse", greenhouse)
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert summary["greenhouse"]["new"] == 1
    stored = (await client.get(_FEED, params={"source": "greenhouse"}, headers=auth_headers)).json()["items"][0]
    assert stored["location"] == "Bengaluru, India" and len(stored["job_type"]) == 30 and len(stored["salary_text"]) == 120


def test_a_very_long_place_list_is_shortened_to_what_fits():
    assert job_feed.tidy_location(None) is None and job_feed.tidy_location("  Pune   India ") == "Pune India"
    no_india = "; ".join(f"Somewhere {i}, Country" for i in range(100))
    shown = job_feed.tidy_location(no_india)
    assert len(shown) <= 255 and shown.endswith("...")


async def test_a_source_whose_jobs_cannot_be_saved_does_not_stop_the_others_or_leave_the_refresh_running(client, auth_headers, db_session, organization, feed, monkeypatch):
    original = job_feed.JobFeedService._store

    async def failing_store(self, organization_id, source, *args, **kwargs):
        if source == "greenhouse":
            raise RuntimeError("database says no")
        return await original(self, organization_id, source, *args, **kwargs)

    async def greenhouse(client, options):
        return [_item("Cloud Engineer", source="greenhouse", ext="x:1")]

    monkeypatch.setattr(job_feed.JobFeedService, "_store", failing_store)
    monkeypatch.setitem(job_feed.FETCHERS, "greenhouse", greenhouse)
    feed.append(_item("DevOps Intern", ext="ok"))
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert summary["greenhouse"] == {"error": "its jobs could not be saved"} and summary["remotive"]["new"] == 1
    status = (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()
    assert status["refreshing"] is False
    assert {s["name"]: s["last_error"] for s in status["sources"]}["greenhouse"] == "its jobs could not be saved"


async def test_a_failing_source_is_reported_and_the_others_still_load(client, auth_headers, db_session, organization, feed, monkeypatch):
    async def broken(client, options):
        raise SourceError("the site answered with status 503")

    await client.put(f"{_FEED}/settings", json={"sources": {"arbeitnow": True}}, headers=auth_headers)
    monkeypatch.setitem(job_feed.FETCHERS, "arbeitnow", broken)
    feed.append(_item("Cloud Intern", ext="z"))
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert summary["arbeitnow"] == {"error": "the site answered with status 503"} and summary["remotive"]["new"] == 1
    status = {s["name"]: s for s in (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()["sources"]}
    assert status["arbeitnow"]["last_error"] == "the site answered with status 503" and status["remotive"]["last_error"] is None


async def test_the_company_career_pages_are_passed_to_their_connectors(client, auth_headers, db_session, organization, feed, monkeypatch):
    seen = {}

    async def greenhouse(client, options):
        seen.update(options)
        return [_item("Cloud Security Engineer", source="greenhouse", ext="okta:1", location="Bengaluru, India", remote=False)]

    monkeypatch.setitem(job_feed.FETCHERS, "greenhouse", greenhouse)
    saved = await client.put(f"{_FEED}/settings", json={"boards": {"greenhouse": ["Okta", "datadog"], "lever": ["cred"]}}, headers=auth_headers)
    assert saved.status_code == 200 and saved.json()["boards"] == {"greenhouse": ["okta", "datadog"], "lever": ["cred"]}
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert seen["greenhouse"] == ["okta", "datadog"] and summary["greenhouse"]["new"] == 1
    mine = (await client.get(_FEED, params={"source": "greenhouse"}, headers=auth_headers)).json()["items"]
    assert [j["title"] for j in mine] == ["Cloud Security Engineer"]
    assert (await client.put(f"{_FEED}/settings", json={"boards": {"workday": ["x"]}}, headers=auth_headers)).status_code == 422
    assert (await client.put(f"{_FEED}/settings", json={"boards": {"greenhouse": ["bad name!"]}}, headers=auth_headers)).status_code == 422


async def test_settings_show_defaults_which_sources_need_a_key_and_validate_changes(client, auth_headers, feed):
    settings_ = (await client.get(f"{_FEED}/settings", headers=auth_headers)).json()
    assert "fresher_only" not in settings_ and settings_["india_only"] is True and settings_["refreshing"] is False
    assert "devsecops" in settings_["keywords"] and "security" in settings_["keywords"]
    assert "okta" in settings_["boards"]["greenhouse"] and "meesho" in settings_["boards"]["lever"]
    by_name = {s["name"]: s for s in settings_["sources"]}
    assert [n for n, s in by_name.items() if s["enabled"]] == ["greenhouse", "lever", "remotive"]
    assert by_name["remotive"]["configured"]
    assert by_name["adzuna"]["configured"] is False and by_name["adzuna"]["enabled"] is False  # no API key on the server

    ok = await client.put(f"{_FEED}/settings", json={"keywords": ["  DevSecOps ", "devsecops", "Pen Testing"], "sources": {"remotive": False}}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["keywords"] == ["devsecops", "pen testing"]
    assert {s["name"]: s["enabled"] for s in ok.json()["sources"]}["remotive"] is False
    assert (await client.put(f"{_FEED}/settings", json={"sources": {"linkedin": True}}, headers=auth_headers)).status_code == 422
    assert (await client.put(f"{_FEED}/settings", json={"keywords": ["  ", ""]}, headers=auth_headers)).status_code == 422


async def test_a_source_switched_off_is_not_read(client, auth_headers, db_session, organization, feed):
    await client.put(f"{_FEED}/settings", json={"sources": {"remotive": False}}, headers=auth_headers)
    feed.append(_item("DevSecOps Intern"))
    summary = await _refresh(client, auth_headers, db_session, organization)
    assert "remotive" not in summary and feed.calls["remotive"] == 0


async def test_who_can_do_what(client, auth_headers, db_session, organization, staff_headers, feed):
    student, student_headers = await _create_student_with_login(client, db_session, organization)
    for method, path in (("get", _FEED), ("get", f"{_FEED}/settings"), ("post", f"{_FEED}/refresh"), ("put", f"{_FEED}/settings")):
        assert (await getattr(client, method)(path, headers=student_headers)).status_code == 403, path
        assert (await getattr(client, method)(path, headers=staff_headers)).status_code == 403, path
        assert (await getattr(client, method)(path)).status_code in (401, 403), path
    assert (await client.get(f"{_FEED}/me", headers=auth_headers)).status_code in (403, 404, 422)  # not a student (an account with no student record)
    assert (await client.get(f"{_FEED}/me")).status_code in (401, 403)
