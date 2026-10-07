"""
Editable email templates: the safe markup, the defaults, organisation and per-hackathon edits, preview,
test sending, and that a template can never break or inject into an email.
"""

import uuid
from datetime import date, timedelta

import pytest

from modules.authentication.repository import AuthRepository
from modules.email_templates.render import render_default, render_email
from modules.users.repository import UserProfileRepository
from packages.email.markup import render_body, render_subject
from packages.email.registry import TEMPLATES, sample_values

pytestmark = pytest.mark.api

_T = "/api/v1/email-templates"
_HACK = "/api/v1/hackathons"


# ---------------- the markup (no database) ----------------


def test_markup_renders_headings_buttons_notes_bold_and_links():
    html, text = render_body(
        "# Hello {{name}}\n\nPlease **confirm** at [our site](https://example.com/a?x=1&y=2).\n\n"
        "[Open it]({{url}})\n\n> Small print here.",
        {"name": "Asha", "url": "https://example.com/go"},
    )
    assert "<h2>Hello Asha</h2>" in html
    assert "<strong>confirm</strong>" in html and 'href="https://example.com/a?x=1&amp;y=2"' in html
    assert 'href="https://example.com/go"' in html and "background:#2563eb" in html  # a button
    assert 'color:#6b7280;font-size:13px">Small print here.' in html
    assert text == (
        "Hello Asha\n\nPlease confirm at our site (https://example.com/a?x=1&y=2).\n\n"
        "Open it: https://example.com/go\n\nSmall print here."
    )


def test_values_and_template_text_cannot_inject_markup_or_unsafe_links():
    html, text = render_body(
        "Hi {{name}}\n\n[Click]({{url}})\n\n[bad](javascript:alert(1))",
        {"name": '<script>alert("x")</script>', "url": "javascript:alert(1)"},
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert 'href="javascript' not in html and 'href="#"' in html
    # A value that looks like formatting is shown as typed, not interpreted.
    html2, _ = render_body("{{v}}", {"v": "**not bold** [x](https://evil.example)"})
    assert "<strong>" not in html2 and "<a " not in html2
    # Template text is escaped too.
    html3, _ = render_body("1 < 2 & <b>bold</b>", {})
    assert "&lt;b&gt;" in html3 and "<b>" not in html3


def test_multiline_values_keep_their_line_breaks_and_unknown_placeholders_are_blank():
    html, text = render_body("{{body}}\n\nTail {{nope}}.", {"body": "line one\nline two"})
    assert "line one<br>line two" in html and "Tail ." in html
    assert render_subject("Hello {{a}}\n{{b}}", {"a": "x", "b": "y"}) == "Hello x y"


def test_every_default_renders_with_its_sample_values_and_uses_only_its_own_placeholders():
    from packages.email.markup import variables_in

    assert {t.key for t in TEMPLATES} == {
        "verification",
        "password_reset",
        "account_invite",
        "hackathon_participant_welcome",
        "workshop_exam_invite",
        "workshop_certificate",
        "announcement",
        "payroll_draft_ready",
        "payslip_ready",
    }
    for template in TEMPLATES:
        allowed = {v.name for v in template.variables}
        assert variables_in(template.subject, template.body) <= allowed, template.key
        assert set(template.required) <= variables_in(template.body), template.key
        subject, text, html = render_default(template.key, sample_values(template))
        assert subject and text and "{{" not in subject + text + html, template.key
    # The wording that was sent before templates became editable is the default.
    subject, text, html = render_default(
        "hackathon_participant_welcome",
        {"full_name": "Asha", "hackathon_title": "DevSecStorm", "set_password_url": "https://l/r?t=1", "login_url": "https://l/login"},
    )
    assert subject == "Your login for DevSecStorm" and "Set my password" in html and "https://l/login" in html
    assert "Choose your password" in text


# ---------------- the API ----------------


async def test_every_template_is_listed_as_default_and_can_be_read(client, auth_headers):
    listed = (await client.get(_T, headers=auth_headers)).json()
    assert len(listed) == len(TEMPLATES) and all(t["customised"] is False for t in listed)
    assert {t["category"] for t in listed} >= {"Account", "Hackathons", "Workshops & exams", "Payroll", "Announcements"}
    detail = (await client.get(f"{_T}/password_reset", headers=auth_headers)).json()
    assert detail["subject"] == detail["default_subject"] == "Reset your ERPX password"
    assert detail["body"] == detail["default_body"] and detail["required"] == ["reset_url"]
    assert {v["name"] for v in detail["variables"]} == {"full_name", "reset_url"}
    assert (await client.get(f"{_T}/no_such_template", headers=auth_headers)).status_code == 404


async def test_a_template_can_be_edited_validated_and_reset(client, auth_headers, db_session, organization):
    url = f"{_T}/password_reset"
    ok = await client.put(
        url,
        json={"subject": "  Choose a new password, {{full_name}}  ", "body": "# New password\n\nHi {{full_name}}!\n\n[Go]({{reset_url}})"},
        headers=auth_headers,
    )
    assert ok.status_code == 200, ok.text
    saved = ok.json()
    assert saved["customised"] is True and saved["subject"] == "Choose a new password, {{full_name}}"
    assert saved["updated_by_name"] and saved["updated_at"]
    assert saved["default_subject"] == "Reset your ERPX password"  # the default is still there to go back to
    assert [t["customised"] for t in (await client.get(_T, headers=auth_headers)).json() if t["key"] == "password_reset"] == [True]

    # What gets sent now is the edited wording; other templates are untouched.
    subject, text, html = await render_email(
        db_session, "password_reset", {"full_name": "Asha", "reset_url": "https://x.io/r"}, organization_id=organization.id
    )
    assert subject == "Choose a new password, Asha" and "Hi Asha!" in html and 'href="https://x.io/r"' in html
    other = await render_email(db_session, "verification", {"full_name": "A", "verification_url": "https://x.io/v"}, organization_id=organization.id)
    assert other[0] == "Verify your ERPX account"

    # Placeholders that don't exist, or a link taken out, are refused with a message that says what to do.
    unknown = await client.put(url, json={"subject": "x", "body": "Hi {{nickname}} [Go]({{reset_url}})"}, headers=auth_headers)
    assert unknown.status_code == 422 and "nickname" in unknown.text and "reset_url" in unknown.text
    no_link = await client.put(url, json={"subject": "x", "body": "Just a hello"}, headers=auth_headers)
    assert no_link.status_code == 422 and "must keep {{reset_url}}" in no_link.text
    assert (await client.put(url, json={"subject": "  ", "body": "[Go]({{reset_url}})"}, headers=auth_headers)).status_code == 422
    assert (await client.get(url, headers=auth_headers)).json()["subject"] == "Choose a new password, {{full_name}}"  # unchanged

    # Resetting brings the default back.
    reset = await client.delete(url, headers=auth_headers)
    assert reset.status_code == 200 and reset.json()["customised"] is False and reset.json()["subject"] == "Reset your ERPX password"
    again = await render_email(db_session, "password_reset", {"full_name": "Asha", "reset_url": "https://x.io/r"}, organization_id=organization.id)
    assert again[0] == "Reset your ERPX password"


async def test_invites_and_resets_are_separate_templates(client, auth_headers, db_session, organization):
    await client.put(
        f"{_T}/account_invite",
        json={"subject": "Welcome aboard, {{full_name}}", "body": "# Welcome\n\n[Set your password]({{set_password_url}})"},
        headers=auth_headers,
    )
    invite = await render_email(db_session, "account_invite", {"full_name": "Ravi", "set_password_url": "https://x.io/s"}, organization_id=organization.id)
    reset = await render_email(db_session, "password_reset", {"full_name": "Ravi", "reset_url": "https://x.io/r"}, organization_id=organization.id)
    assert invite[0] == "Welcome aboard, Ravi" and reset[0] == "Reset your ERPX password"


async def test_the_preview_shows_sample_values_and_flags_problems_without_saving(client, auth_headers):
    ok = await client.post(
        f"{_T}/verification/preview", json={"subject": "Hi {{full_name}}", "body": "# Hey {{full_name}}\n\n[Verify]({{verification_url}})"}, headers=auth_headers
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["subject"] == "Hi Asha Rao" and "Hey Asha Rao" in body["html"] and body["errors"] == []
    bad = (await client.post(f"{_T}/verification/preview", json={"subject": "x", "body": "no link {{oops}}"}, headers=auth_headers)).json()
    assert len(bad["errors"]) == 2  # an unknown placeholder, and the missing required link
    assert (await client.get(_T, headers=auth_headers)).json()[0]["customised"] is False  # nothing was saved


async def test_a_test_email_goes_to_the_address_given_and_reports_whether_it_was_accepted(client, auth_headers, monkeypatch):
    from modules.email_templates import service as svc

    sent: list[tuple] = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append((to, subject, text, html))
        return True

    monkeypatch.setattr(svc.email_service, "send", fake_send)
    url = f"{_T}/hackathon_participant_welcome/test"

    # The saved wording, with sample values, clearly marked as a test.
    ok = await client.post(url, json={"to_email": "me@example.com"}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["sent"] is True and "me@example.com" in ok.json()["message"]
    to, subject, text, html = sent[0]
    assert to == "me@example.com" and subject == "[TEST] Your login for DevSecStorm"
    assert "Asha Rao" in text and "sample values" in text and "sample values" in html

    # The draft in the editor is what gets sent, before anything is saved.
    draft = await client.post(
        url,
        json={"to_email": "me@example.com", "subject": "Draft for {{hackathon_title}}", "body": "Hi {{full_name}} [Go]({{set_password_url}})"},
        headers=auth_headers,
    )
    assert draft.json()["sent"] is True and sent[1][1] == "[TEST] Draft for DevSecStorm"
    assert (await client.get(f"{_T}/hackathon_participant_welcome", headers=auth_headers)).json()["customised"] is False

    # A refused message is reported honestly, a bad address or draft is a 422.
    async def failing(*a, **k):
        return False

    monkeypatch.setattr(svc.email_service, "send", failing)
    refused = await client.post(url, json={"to_email": "me@example.com"}, headers=auth_headers)
    assert refused.status_code == 200 and refused.json()["sent"] is False and "SMTP" in refused.json()["message"]
    assert (await client.post(url, json={"to_email": "not-an-address"}, headers=auth_headers)).status_code == 422
    assert (await client.post(url, json={"to_email": "me@example.com", "subject": "x", "body": "no link"}, headers=auth_headers)).status_code == 422


async def test_test_emails_are_capped_per_person(client, auth_headers, monkeypatch):
    from modules.email_templates import service as svc

    async def fake_send(*a, **k):
        return True

    monkeypatch.setattr(svc.email_service, "send", fake_send)
    monkeypatch.setattr(svc, "TEST_SENDS_PER_HOUR", 3)
    svc._recent_tests.clear()
    url = f"{_T}/payslip_ready/test"
    for _ in range(3):
        assert (await client.post(url, json={"to_email": "me@example.com"}, headers=auth_headers)).status_code == 200
    assert (await client.post(url, json={"to_email": "me@example.com"}, headers=auth_headers)).status_code == 429


async def test_people_without_permission_cannot_see_or_change_templates(client, db_session, organization):
    email = f"plain.{uuid.uuid4().hex[:8]}@erpx.example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "PlainPass1!", "full_name": "Plain User"})
    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await auth_repo.mark_email_verified(user)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)
    await db_session.flush()
    token = (await client.post("/api/v1/auth/login", json={"email": email, "password": "PlainPass1!"})).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (await client.get(_T, headers=headers)).status_code == 403
    assert (await client.put(f"{_T}/password_reset", json={"subject": "x", "body": "[x]({{reset_url}})"}, headers=headers)).status_code == 403
    assert (await client.post(f"{_T}/password_reset/test", json={"to_email": "a@example.com"}, headers=headers)).status_code == 403


# ---------------- one hackathon's own wording ----------------


def _dates():
    today = date.today()
    return {
        "registration_deadline": (today + timedelta(days=7)).isoformat(),
        "start_date": (today + timedelta(days=10)).isoformat(),
        "end_date": (today + timedelta(days=12)).isoformat(),
    }


async def _hackathon(client, auth_headers, title="DevSecStorm"):
    r = await client.post(_HACK, json={"code": f"H-{uuid.uuid4().hex[:8]}", "title": title, **_dates()}, headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_a_hackathon_can_have_its_own_welcome_email_and_falls_back_to_the_organisations(client, auth_headers, db_session, organization):
    one, two = await _hackathon(client, auth_headers, "One"), await _hackathon(client, auth_headers, "Two")
    base = f"{_HACK}/{one['id']}/email-templates"

    # Only event emails are offered on the event page.
    listed = (await client.get(base, headers=auth_headers)).json()
    assert [t["key"] for t in listed] == ["hackathon_participant_welcome"] and listed[0]["inherited"] is True
    assert (await client.get(f"{base}/password_reset", headers=auth_headers)).status_code == 404

    values = {"full_name": "Asha", "hackathon_title": "One", "set_password_url": "https://x.io/s", "login_url": "https://x.io/l"}
    wording = {"subject": "Event one: {{hackathon_title}}", "body": "# Welcome to event one\n\n[Start]({{set_password_url}})"}

    # The organisation edits the general wording; every event without its own uses it.
    await client.put(f"{_T}/hackathon_participant_welcome", json={"subject": "Org wide {{hackathon_title}}", "body": "[Go]({{set_password_url}})"}, headers=auth_headers)
    one_view = (await client.get(f"{base}/hackathon_participant_welcome", headers=auth_headers)).json()
    assert one_view["inherited"] is True and one_view["subject"] == "Org wide {{hackathon_title}}"

    # Event one writes its own: it applies to event one only.
    saved = await client.put(f"{base}/hackathon_participant_welcome", json=wording, headers=auth_headers)
    assert saved.status_code == 200 and saved.json()["customised"] is True and saved.json()["inherited"] is False
    s1 = await render_email(db_session, "hackathon_participant_welcome", values, organization.id, uuid.UUID(one["id"]))
    s2 = await render_email(db_session, "hackathon_participant_welcome", {**values, "hackathon_title": "Two"}, organization.id, uuid.UUID(two["id"]))
    s_none = await render_email(db_session, "hackathon_participant_welcome", values, organization.id, None)
    assert s1[0] == "Event one: One" and s2[0] == "Org wide Two" and s_none[0] == "Org wide One"
    # Editing the event's wording never touched the organisation's.
    assert (await client.get(f"{_T}/hackathon_participant_welcome", headers=auth_headers)).json()["subject"] == "Org wide {{hackathon_title}}"

    # Resetting the event goes back to the organisation's wording.
    back = (await client.delete(f"{base}/hackathon_participant_welcome", headers=auth_headers)).json()
    assert back["customised"] is False and back["inherited"] is True and back["subject"] == "Org wide {{hackathon_title}}"
    # Previewing and testing from the event page work, and another organisation's hackathon is not reachable.
    assert (await client.post(f"{base}/hackathon_participant_welcome/preview", json=wording, headers=auth_headers)).json()["errors"] == []
    assert (await client.get(f"{_HACK}/{uuid.uuid4()}/email-templates", headers=auth_headers)).status_code == 404


async def test_a_recipients_organisation_is_found_from_their_email(client, db_session, organization, auth_headers):
    email = f"own.{uuid.uuid4().hex[:8]}@erpx.example.com"
    await client.post("/api/v1/auth/register", json={"email": email, "password": "OwnPass123!", "full_name": "Owner"})
    auth_repo = AuthRepository(db_session)
    user = await auth_repo.get_user_by_email(email)
    await UserProfileRepository(db_session).create(user_id=user.id, organization_id=organization.id)
    await db_session.flush()
    await client.put(f"{_T}/verification", json={"subject": "Confirm it's you", "body": "[Confirm]({{verification_url}})"}, headers=auth_headers)
    values = {"full_name": "Owner", "verification_url": "https://x.io/v"}
    # No organisation passed: it comes from who the email is going to.
    assert (await render_email(db_session, "verification", values, recipient_email=email.upper()))[0] == "Confirm it's you"
    assert (await render_email(db_session, "verification", values, recipient_email="stranger@nowhere.example"))[0] == "Verify your ERPX account"


def test_the_reset_task_renders_the_invite_template_for_invites_and_the_reset_template_otherwise(monkeypatch):
    import modules.authentication.tasks as tasks

    rendered: list[str] = []

    def fake_render(key, values, **kwargs):
        rendered.append(key)
        return ("subject", "text", "<p>html</p>")

    async def fake_send(*args, **kwargs):
        return True

    monkeypatch.setattr(tasks, "render_email_sync", fake_render)
    monkeypatch.setattr(tasks.email_service, "send", fake_send)
    tasks.send_password_reset_email_task("a@example.com", "Asha", "https://x.io/s")
    tasks.send_password_reset_email_task("a@example.com", "Asha", "https://x.io/s", "account_invite")
    assert rendered == ["password_reset", "account_invite"]
