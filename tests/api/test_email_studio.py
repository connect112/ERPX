"""
Email Studio: designed templates (visual editor, imported HTML, approved React Email components), drafts versus published
versions, restoring versions, using a template for an ERPX email without breaking the fallback, previews and test sends that start
nothing, brand profiles, signatures and images, the send history, and who is allowed to do what.
"""

import io
import uuid
from contextlib import asynccontextmanager

import pytest
from PIL import Image
from sqlalchemy import select

from modules.authorization.repository import AuthorizationRepository
from modules.authorization.service import AuthorizationService
from modules.email_studio import service as studio_service
from modules.email_studio.models import EmailSendRecord
from modules.email_templates.render import render_email
from packages.email import service as mail_service
from tests._fixtures import _make_user
from tests.api.test_internship_offers import _setup
from tests.api.test_offer_letters import configure

pytestmark = pytest.mark.api

_S = "/api/v1/email-studio"

DOC = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello {{full_name}}"}]}]}


def page(body: str) -> str:
    """What the visual editor's export looks like: a full document with the body inside."""
    return f'<!DOCTYPE html><html><head><style>x{{}}</style></head><body style="background-color:#ffffff">{body}</body></html>'


VERIFY_HTML = page('<h1>Welcome {{full_name}}</h1><p><a href="{{verification_url}}">Verify</a></p>')


def draft(**over):
    body = {"subject": "Verify your account", "editor_json": DOC, "html": VERIFY_HTML}
    body.update(over)
    return body


async def create(client, headers, name="Verify email", source="visual", **draft_over):
    payload = {"name": name, "source_type": source, "category": "Account Verification", **draft(**draft_over)}
    if source == "html":
        payload.pop("editor_json")
    r = await client.post(f"{_S}/templates", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def publish(client, headers, template):
    r = await client.post(f"{_S}/templates/{template['id']}/publish", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def assign(client, headers, key, template_id, expect=200):
    r = await client.put(f"{_S}/assignments/{key}", json={"template_id": template_id}, headers=headers)
    assert r.status_code == expect, r.text
    return r


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", (40, 20), (200, 30, 30, 255)).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def mailbox(monkeypatch, db_session):
    """Replaces the mail sending and the history's own database session, so nothing leaves the test."""
    sent: list[dict] = []

    class Box:
        ok = True
        sent: list[dict] = []

    box = Box()
    box.sent = sent

    async def send(to, subject, text, html=None, attachments=None):
        sent.append({"to": to, "subject": subject, "text": text, "html": html})
        return box.ok

    monkeypatch.setattr(studio_service.email_service, "send", send)
    studio_service._recent_tests.clear()
    return box


async def user_with(db_session, organization, permissions):
    user, token = await _make_user(db_session, organization, is_superuser=False, email=f"u-{uuid.uuid4().hex[:8]}@erpx.example.com")
    repo = AuthorizationRepository(db_session)
    role = await repo.create_role(f"Role {uuid.uuid4().hex[:6]}", f"role-{uuid.uuid4().hex[:8]}", "test")
    await db_session.flush()
    perms = [await repo.get_or_create_permission(code, code.split(".")[0], code) for code in permissions]
    await repo.set_role_permissions(role, perms)
    await AuthorizationService(db_session).assign_role(user.id, role.id, organization.id, assigned_by_user_id=None)
    await db_session.flush()
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------ library and creating


async def test_the_library_lists_built_in_emails_and_studio_templates_together(client, auth_headers):
    t = await create(client, auth_headers)
    items = (await client.get(f"{_S}/library", headers=auth_headers)).json()
    mine = next(i for i in items if i["id"] == t["id"])
    assert (mine["creation_method"], mine["status"], mine["is_system"], mine["has_draft"]) == ("Visual editor", "draft", False, True)
    system = {i["key"]: i for i in items if i["is_system"]}
    assert {"verification", "password_reset", "internship_offer_letter", "internship_welcome"} <= set(system)
    assert system["verification"]["creation_method"] == "Built-in" and system["verification"]["status"] == "active"
    assert system["internship_offer_letter"]["category"] == "Internship Offer Letters"
    cats = (await client.get(f"{_S}/categories", headers=auth_headers)).json()
    assert "Account Verification" in cats and "Custom Emails" in cats and "Pentrix Bookings" in cats and "Pentrix Marketing" in cats and len(cats) == 16


async def test_a_visual_design_is_saved_as_editor_json_and_sanitised_html_and_can_be_reopened(client, auth_headers):
    t = await create(client, auth_headers, html=page('<p onclick="x()">Hi {{full_name}}</p><script>alert(1)</script><a href="javascript:x">bad</a>'))
    current = t["current"]
    assert current["editor_json"] == DOC  # the design itself, not only its HTML
    assert "{{full_name}}" in current["body_html"]
    for bad in ("<script", "onclick", "javascript:"):
        assert bad not in current["body_html"].lower()
    again = (await client.get(f"{_S}/templates/{t['id']}", headers=auth_headers)).json()
    assert again["current"]["editor_json"] == DOC and again["status"] == "draft" and again["published_version_number"] is None


async def test_a_bad_subject_or_design_is_refused(client, auth_headers):
    r = await client.post(f"{_S}/templates", json={"name": "x", "source_type": "visual", **draft(subject="Hi\r\nBcc: evil@example.com")}, headers=auth_headers)
    assert r.status_code == 422
    evil = {"type": "doc", "content": [{"type": "button", "attrs": {"href": "javascript:alert(1)"}}]}
    r = await client.post(f"{_S}/templates", json={"name": "x", "source_type": "visual", **draft(editor_json=evil)}, headers=auth_headers)
    assert r.status_code == 422 and "unsafe link" in r.text
    r = await client.post(f"{_S}/templates", json={"name": "x", "source_type": "visual", "category": "Nonsense", **draft()}, headers=auth_headers)
    assert r.status_code == 422


# ------------------------------------------------------------ drafts, publishing, versions


async def test_a_draft_never_changes_the_published_version_until_it_is_published(client, auth_headers):
    t = await create(client, auth_headers)
    v1 = await publish(client, auth_headers, t)
    assert v1["status"] == "published" and v1["published_version_number"] == 1 and v1["has_draft"] is False
    saved = (await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(subject="Second subject", html=page("<p>Second {{full_name}}</p>")), headers=auth_headers)).json()
    assert saved["has_draft"] is True and saved["current"]["version_number"] == 2 and saved["published_version_number"] == 1
    versions = (await client.get(f"{_S}/templates/{t['id']}/versions", headers=auth_headers)).json()
    assert [(v["version_number"], v["state"]) for v in versions] == [(2, "draft"), (1, "published")]
    published = (await client.get(f"{_S}/templates/{t['id']}/versions/{versions[1]['id']}", headers=auth_headers)).json()
    assert published["subject"] == "Verify your account" and "Welcome" in published["body_html"]  # untouched by the draft
    v2 = await publish(client, auth_headers, t)
    assert v2["published_version_number"] == 2
    states = {v["version_number"]: v["state"] for v in (await client.get(f"{_S}/templates/{t['id']}/versions", headers=auth_headers)).json()}
    assert states == {1: "superseded", 2: "published"}
    assert (await client.post(f"{_S}/templates/{t['id']}/publish", headers=auth_headers)).status_code == 409  # nothing new


async def test_an_earlier_version_can_be_restored_as_a_draft_and_a_draft_can_be_discarded(client, auth_headers):
    t = await create(client, auth_headers)
    await publish(client, auth_headers, t)
    await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(subject="Changed", html=page("<p>Changed</p>")), headers=auth_headers)
    await publish(client, auth_headers, t)
    versions = (await client.get(f"{_S}/templates/{t['id']}/versions", headers=auth_headers)).json()
    first = next(v for v in versions if v["version_number"] == 1)
    restored = (await client.post(f"{_S}/templates/{t['id']}/versions/{first['id']}/restore", headers=auth_headers)).json()
    assert restored["has_draft"] and restored["current"]["subject"] == "Verify your account" and restored["published_version_number"] == 2
    gone = await client.delete(f"{_S}/templates/{t['id']}/draft", headers=auth_headers)
    assert gone.status_code == 200 and gone.json()["has_draft"] is False and gone.json()["current"]["subject"] == "Changed"


async def test_a_template_is_duplicated_and_archived_but_not_while_an_erpx_email_uses_it(client, auth_headers):
    t = await create(client, auth_headers)
    copy = (await client.post(f"{_S}/templates/{t['id']}/duplicate", headers=auth_headers)).json()
    assert copy["name"] == "Verify email (copy)" and copy["status"] == "draft" and copy["current"]["editor_json"] == DOC
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    busy = await client.post(f"{_S}/templates/{t['id']}/archive", headers=auth_headers)
    assert busy.status_code == 409 and "in use" in busy.text
    assert (await client.post(f"{_S}/templates/{copy['id']}/archive", headers=auth_headers)).json()["status"] == "archived"
    assert (await client.put(f"{_S}/templates/{copy['id']}/draft", json=draft(), headers=auth_headers)).status_code == 409
    assert (await client.post(f"{_S}/templates/{copy['id']}/unarchive", headers=auth_headers)).json()["status"] == "draft"


# ------------------------------------------------------------ using a template for an ERPX email


async def test_a_template_must_be_published_and_keep_what_the_email_needs_before_it_is_used(client, auth_headers):
    t = await create(client, auth_headers, html=page("<p>No link here {{full_name}}</p>"))
    assert "Publish the template" in (await assign(client, auth_headers, "verification", t["id"], 422)).text
    await publish(client, auth_headers, t)  # publishing alone is fine: it is not assigned to anything yet
    r = await assign(client, auth_headers, "verification", t["id"], 422)
    assert "{{verification_url}}" in r.text
    other = await create(client, auth_headers, name="Other", html=page('<a href="{{verification_url}}">go</a> {{student_name}} {{nonsense}}'))
    await publish(client, auth_headers, other)
    r = await assign(client, auth_headers, "verification", other["id"], 422)
    assert "{{student_name}}" in r.text and "{{nonsense}}" in r.text
    assert (await assign(client, auth_headers, "no_such_email", other["id"], 404)).status_code == 404


async def test_publishing_checks_a_template_that_is_already_in_use(client, auth_headers):
    t = await create(client, auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(html=page("<p>I removed the link {{full_name}}</p>")), headers=auth_headers)
    r = await client.post(f"{_S}/templates/{t['id']}/publish", headers=auth_headers)
    assert r.status_code == 422 and "{{verification_url}}" in r.text
    assert (await client.get(f"{_S}/templates/{t['id']}", headers=auth_headers)).json()["published_version_number"] == 1  # still the old one


async def test_the_real_email_uses_the_published_version_and_falls_back_safely(client, auth_headers, db_session, organization):
    values = {"full_name": "Asha <Rao>", "verification_url": "https://erp.example.com/verify?token=abc123"}
    default = await render_email(db_session, "verification", values, organization_id=organization.id)
    assert "Verify Email" in default[2]  # the built-in wording to begin with
    t = await create(client, auth_headers)
    await publish(client, auth_headers, t)
    # published but not assigned: nothing changes
    assert (await render_email(db_session, "verification", values, organization_id=organization.id))[2] == default[2]
    await assign(client, auth_headers, "verification", t["id"])
    subject, text, html = await render_email(db_session, "verification", values, organization_id=organization.id)
    assert subject == "Verify your account" and 'href="https://erp.example.com/verify?token=abc123"' in html
    assert "Welcome Asha &lt;Rao&gt;" in html and "<Rao>" not in html  # the value is escaped, never markup
    assert "https://erp.example.com/verify?token=abc123" in text
    # editing the draft does not touch what is sent; publishing does
    await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(subject="v2 {{full_name}}", html=page('<p>v2 <a href="{{verification_url}}">x</a></p>')), headers=auth_headers)
    assert (await render_email(db_session, "verification", values, organization_id=organization.id))[0] == "Verify your account"
    await publish(client, auth_headers, t)
    assert (await render_email(db_session, "verification", values, organization_id=organization.id))[0] == "v2 Asha <Rao>"
    # a value the template needs that the sender did not give must never stop the email: the built-in wording is used
    fallback = await render_email(db_session, "verification", {"full_name": "Asha"}, organization_id=organization.id)
    assert fallback[0] == "Verify your ERPX account"
    # going back to the previous wording
    assert (await client.delete(f"{_S}/assignments/verification", headers=auth_headers)).status_code == 200
    assert (await render_email(db_session, "verification", values, organization_id=organization.id))[2] == default[2]


async def test_an_archived_template_is_not_used(client, auth_headers, db_session, organization):
    t = await create(client, auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    await client.delete(f"{_S}/assignments/verification", headers=auth_headers)
    await client.post(f"{_S}/templates/{t['id']}/archive", headers=auth_headers)
    out = await render_email(db_session, "verification", {"full_name": "A", "verification_url": "https://x.example/v"}, organization_id=organization.id)
    assert out[0] == "Verify your ERPX account"


# ------------------------------------------------------------ imported HTML


async def test_imported_html_is_kept_as_written_but_only_the_safe_copy_is_sent(client, auth_headers):
    source = page('<table><tr><td style="color:#123456;position:absolute">Hi {{full_name}}</td></tr></table><script>alert(1)</script>')
    t = await create(client, auth_headers, name="Imported", source="html", html=source)
    cur = t["current"]
    assert cur["html_source"] == source and "<script" in cur["html_source"]  # the original, never sent
    assert "<script" not in cur["body_html"] and "position" not in cur["body_html"] and "color:#123456" in cur["body_html"]
    assert cur["editor_json"] is None and t["source_type"] == "html"


# ------------------------------------------------------------ approved React Email components


async def test_approved_components_are_listed_and_edited_only_through_their_declared_properties(client, auth_headers, db_session, organization):
    listed = (await client.get(f"{_S}/code-templates", headers=auth_headers)).json()
    keys = {c["key"] for c in listed}
    assert {"account_verification", "password_reset", "internship_offer", "internship_welcome", "certificate_distribution"} <= keys
    offer = next(c for c in listed if c["key"] == "internship_offer")
    assert offer["suggested_for"] == "internship_offer_letter" and any(p["name"] == "heading" and p["required"] for p in offer["props"])

    payload = {"name": "Verify (React Email)", "source_type": "code", "category": "Account Verification", "code_template_key": "account_verification",
               "code_props": {"heading": "Hello {{full_name}}", "button_text": "Confirm it", "primary_color": "#ff0000", "not_a_property": "ignored"}}
    t = (await client.post(f"{_S}/templates", json=payload, headers=auth_headers)).json()
    assert t["current"]["code_props"] == {"heading": "Hello {{full_name}}", "button_text": "Confirm it", "primary_color": "#ff0000"}
    assert t["current"]["subject"] == "Verify your {{company_name}} account"  # the component's own suggestion
    await client.put(f"{_S}/templates/{t['id']}/draft", json={"subject": "Confirm, {{full_name}}", "code_template_key": "account_verification", "code_props": t["current"]["code_props"]}, headers=auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    subject, text, html = await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": "https://erp.example.com/v?t=1"}, organization_id=organization.id)
    assert subject == "Confirm, Asha" and "Hello Asha" in html and "Confirm it" in html and "#ff0000" in html
    assert 'href="https://erp.example.com/v?t=1"' in html and "{{" not in html and "<script" not in html.lower()


async def test_component_properties_are_checked(client, auth_headers):
    base = {"name": "x", "source_type": "code", "code_template_key": "account_verification"}
    assert (await client.post(f"{_S}/templates", json={**base, "code_props": {"primary_color": "red"}}, headers=auth_headers)).status_code == 422
    assert (await client.post(f"{_S}/templates", json={**base, "code_props": {"heading": "two\nlines"}}, headers=auth_headers)).status_code == 422
    assert (await client.post(f"{_S}/templates", json={"name": "x", "source_type": "code", "code_template_key": "../etc"}, headers=auth_headers)).status_code == 422
    assert (await client.post(f"{_S}/templates", json={"name": "x", "source_type": "code"}, headers=auth_headers)).status_code == 422


# ------------------------------------------------------------ previews and tests


async def test_the_preview_shows_the_final_subject_and_html_and_reports_problems(client, auth_headers):
    body = {"source_type": "visual", "draft": draft(subject="Hi {{full_name}} {{oops}}", html=page("<p>{{full_name}} {{oops}} {{verification_url}}</p>")), "context": {"type": "sample", "key": "verification"}}
    r = (await client.post(f"{_S}/preview", json=body, headers=auth_headers)).json()
    assert r["subject"] == "Hi Asha Rao" and "Asha Rao" in r["html"] and "https://erp.example.com/verify?token=abc123" in r["text"]
    assert r["unsupported"] == ["oops"] and r["missing"] == ["oops"]


async def test_the_preview_can_use_a_real_selected_student_and_needs_permission_to_do_so(client, auth_headers, db_session, organization):
    internship, ids = await _setup(client, auth_headers)
    await configure(client, auth_headers, internship)
    body = {"source_type": "visual", "draft": draft(subject="Congratulations {{student_name}}", html=page("<p>{{student_name}} of {{institution_name}}: {{internship_position}} at {{company_name}}</p>")),
            "context": {"type": "internship", "key": "internship_offer_letter", "internship_id": internship["id"], "student_id": ids["meera@example.com"]}}
    r = (await client.post(f"{_S}/preview", json=body, headers=auth_headers)).json()
    assert r["subject"] == "Congratulations Meera Iyer" and "Meera Iyer of Sri Venkateswara College: Intern at GIR Technologies" in r["text"]
    assert r["unsupported"] == [] and r["missing"] == []
    viewer = await user_with(db_session, organization, ["email_templates.view"])
    refused = await client.post(f"{_S}/preview", json=body, headers=viewer)
    assert refused.status_code == 403 and "view internships" in refused.text
    body["context"] = {"type": "sample"}
    assert (await client.post(f"{_S}/preview", json=body, headers=viewer)).status_code == 200


async def test_a_test_email_is_marked_uses_sample_links_and_starts_nothing(client, auth_headers, mailbox):
    body = {"source_type": "visual", "draft": draft(), "context": {"type": "sample", "key": "verification"}, "to_email": "me@example.com"}
    r = (await client.post(f"{_S}/test", json=body, headers=auth_headers)).json()
    assert r["sent"] is True and "me@example.com" in r["message"]
    sent = mailbox.sent[0]
    assert sent["to"] == "me@example.com" and sent["subject"] == "[TEST] Verify your account"
    assert "This is a test email" in sent["text"] and "This is a test email" in sent["html"]
    assert "https://erp.example.com/verify?token=abc123" in sent["text"]  # the safe sample link, not a real token
    mailbox.ok = False
    r = (await client.post(f"{_S}/test", json=body, headers=auth_headers)).json()
    assert r["sent"] is False and "did not accept" in r["message"]
    bad = {**body, "draft": draft(html=page("<p>{{not_a_thing}}</p>"))}
    assert (await client.post(f"{_S}/test", json=bad, headers=auth_headers)).status_code == 422


async def test_test_emails_are_rate_limited(client, auth_headers, mailbox):
    body = {"source_type": "visual", "draft": draft(), "context": {"type": "sample", "key": "verification"}, "to_email": "me@example.com"}
    for _ in range(studio_service.TEST_SENDS_PER_HOUR):
        assert (await client.post(f"{_S}/test", json=body, headers=auth_headers)).status_code == 200
    assert (await client.post(f"{_S}/test", json=body, headers=auth_headers)).status_code == 429


# ------------------------------------------------------------ brand, signature, components, images


async def test_brand_profiles_have_one_default_and_validated_details(client, auth_headers):
    a = (await client.post(f"{_S}/brands", json={"name": "GIR", "company_name": "GIR Technologies", "primary_color": "#112233", "website": "https://girtechnologies.com", "contact_email": "info@girtechnologies.com", "from_name": "GIR Technologies", "reply_to": "hello@girtechnologies.com"}, headers=auth_headers)).json()
    assert a["is_default"] is True  # the first brand is the default
    b = (await client.post(f"{_S}/brands", json={"name": "Pentrix", "is_default": True}, headers=auth_headers)).json()
    brands = {x["name"]: x for x in (await client.get(f"{_S}/brands", headers=auth_headers)).json()}
    assert brands["Pentrix"]["is_default"] and not brands["GIR"]["is_default"] and b["is_default"]
    for bad in ({"primary_color": "blue"}, {"website": "javascript:x"}, {"contact_email": "not-an-email"}, {"reply_to": "a@b.com\r\nBcc: c@d.com"}):
        assert (await client.post(f"{_S}/brands", json={"name": "Bad", **bad}, headers=auth_headers)).status_code == 422, bad
    assert (await client.put(f"{_S}/brands/{a['id']}", json={"name": "GIR", "primary_color": "#abcdef"}, headers=auth_headers)).json()["primary_color"] == "#abcdef"


async def test_a_brand_supplies_values_blocks_and_colours_to_the_email(client, auth_headers, db_session, organization):
    logo = (await client.post(f"{_S}/assets?purpose=image", files={"file": ("logo.png", png(), "image/png")}, headers=auth_headers)).json()
    assert logo["url"].endswith(f"/api/v1/public/email-assets/{logo['token']}")
    brand = (await client.post(f"{_S}/brands", json={"name": "GIR", "company_name": "GIR Technologies", "logo_asset_id": logo["id"], "primary_color": "#0a5c36", "address": "Ameerpet, Hyderabad", "contact_email": "info@girtechnologies.com", "tagline": "Learn. Build."}, headers=auth_headers)).json()
    sig = (await client.post(f"{_S}/signatures", json={"name": "CEO", "person_name": "Atluri Srujan", "designation": "CEO", "company_name": "GIR Technologies", "email": "ceo@girtechnologies.com"}, headers=auth_headers)).json()
    html = page("<p>{{brand_header}}</p><p>Hello {{full_name}} from {{company_name}}</p><p>{{signature}}</p><p>{{brand_footer}}</p>")
    t = await create(client, auth_headers, subject="From {{company_name}}", html=html, brand_profile_id=brand["id"], signature_id=sig["id"])
    await publish(client, auth_headers, t)
    prev = (await client.post(f"{_S}/preview", json={"source_type": "visual", "draft": draft(subject="From {{company_name}}", html=html, brand_profile_id=brand["id"], signature_id=sig["id"]), "context": {"type": "sample"}}, headers=auth_headers)).json()
    assert prev["subject"] == "From GIR Technologies" and "Hello Asha Rao from GIR Technologies" in prev["text"]
    assert "Atluri Srujan" in prev["html"] and "CEO" in prev["html"] and "Ameerpet, Hyderabad" in prev["html"] and "#0a5c36" in prev["html"]
    assert logo["token"] in prev["html"] and prev["warnings"] == []
    # a block placeholder used twice is reported (no duplicate headers or signatures)
    twice = page("<p>{{signature}}</p><p>{{signature}}</p>")
    prev = (await client.post(f"{_S}/preview", json={"source_type": "visual", "draft": draft(html=twice, signature_id=sig["id"]), "context": {"type": "sample"}}, headers=auth_headers)).json()
    assert any("used 2 times" in w for w in prev["warnings"])
    assert (await client.post(f"{_S}/templates", json={"name": "t", "source_type": "visual", **draft(html=twice, signature_id=sig["id"])}, headers=auth_headers)).status_code == 201
    in_use = await client.delete(f"{_S}/brands/{brand['id']}", headers=auth_headers)
    assert in_use.status_code == 409


async def test_a_signature_image_is_only_used_after_it_is_approved(client, auth_headers):
    image = (await client.post(f"{_S}/assets?purpose=image", files={"file": ("sig.png", png(), "image/png")}, headers=auth_headers)).json()
    sig = (await client.post(f"{_S}/signatures", json={"name": "CEO", "person_name": "A B", "signature_asset_id": image["id"], "style": {"color": "#222222", "font_size": 15, "align": "center", "evil": "x"}}, headers=auth_headers)).json()
    assert sig["signature_approved"] is False and sig["style"] == {"color": "#222222", "font_size": 15, "align": "center"}
    body = {"source_type": "visual", "draft": draft(html=page("<p>{{signature}}</p>"), signature_id=sig["id"]), "context": {"type": "sample"}}
    before = (await client.post(f"{_S}/preview", json=body, headers=auth_headers)).json()["html"]
    assert image["token"] not in before
    ok = (await client.post(f"{_S}/signatures/{sig['id']}/approve", json={"approve": True}, headers=auth_headers)).json()
    assert ok["signature_approved"] is True
    assert image["token"] in (await client.post(f"{_S}/preview", json=body, headers=auth_headers)).json()["html"]
    other = (await client.post(f"{_S}/assets?purpose=image", files={"file": ("sig2.png", png(), "image/png")}, headers=auth_headers)).json()
    changed = (await client.put(f"{_S}/signatures/{sig['id']}", json={"name": "CEO", "person_name": "A B", "signature_asset_id": other["id"]}, headers=auth_headers)).json()
    assert changed["signature_approved"] is False  # a different image has to be approved again
    nothing = (await client.post(f"{_S}/signatures", json={"name": "No image"}, headers=auth_headers)).json()
    assert (await client.post(f"{_S}/signatures/{nothing['id']}/approve", json={"approve": True}, headers=auth_headers)).status_code == 422


async def test_reusable_components_are_cleaned_like_any_email_html(client, auth_headers):
    c = (await client.post(f"{_S}/components", json={"name": "Warning", "kind": "warning", "html": '<table><tr><td style="color:red">Careful <b onclick="x()">{{full_name}}</b></td></tr></table><script>1</script>'}, headers=auth_headers)).json()
    assert "<script" not in c["html"] and "onclick" not in c["html"] and "{{full_name}}" in c["html"]
    assert len((await client.get(f"{_S}/components", headers=auth_headers)).json()) == 1
    assert (await client.post(f"{_S}/components", json={"name": "Empty", "kind": "footer", "html": "<script>1</script>"}, headers=auth_headers)).status_code == 422
    assert (await client.delete(f"{_S}/components/{c['id']}", headers=auth_headers)).status_code == 200


async def test_only_real_images_are_accepted_and_are_served_publicly_with_safe_headers(client, auth_headers, db_session):
    up = lambda data, purpose="image", name="x.png": client.post(f"{_S}/assets?purpose={purpose}", files={"file": (name, data, "image/png")}, headers=auth_headers)  # noqa: E731
    assert (await up(b"%PDF-1.4 not an image")).status_code == 422
    assert (await up(b"")).status_code == 422
    assert (await up(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")).status_code == 422  # email clients do not show SVG
    assert (await up(b"x" * (2 * 1024 * 1024 + 10))).status_code == 422
    ok = (await up(png())).json()
    served = await client.get(f"/api/v1/public/email-assets/{ok['token']}")  # no sign-in: an email client fetches it
    assert served.status_code == 200 and served.headers["content-type"] == "image/png" and served.content[:4] == b"\x89PNG"
    assert served.headers["x-content-type-options"] == "nosniff" and "sandbox" in served.headers["content-security-policy"]
    assert (await client.get("/api/v1/public/email-assets/does-not-exist")).status_code == 404
    pdf = (await up(b"%PDF-1.4 hello", purpose="attachment", name="guide.pdf")).json()
    assert pdf["content_type"] == "application/pdf" and pdf["url"] is None
    assert (await client.get(f"/api/v1/public/email-assets/{pdf['token']}")).status_code == 404  # attachments are never public
    assert (await up(png(), purpose="attachment")).status_code == 422  # not a PDF


# ------------------------------------------------------------ history


async def test_every_email_sent_is_recorded_with_its_template_and_version_and_no_message_body(client, auth_headers, db_session, organization, monkeypatch):
    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr("app.db.session.get_db_context", same_session)
    smtp: list = []

    async def fake_smtp(message, **kwargs):
        smtp.append(message)

    monkeypatch.setattr(mail_service.aiosmtplib, "send", fake_smtp)
    t = await create(client, auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    secret = "https://erp.example.com/verify?token=SECRET-TOKEN-123"
    subject, text, html = await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": secret}, organization_id=organization.id)
    assert await mail_service.EmailService().send("asha@example.com", subject, text, html) is True
    monkeypatch.setattr(mail_service.aiosmtplib, "send", lambda *a, **k: (_ for _ in ()).throw(ConnectionError("smtp down")))
    subject, text, html = await render_email(db_session, "verification", {"full_name": "Ravi", "verification_url": secret}, organization_id=organization.id)
    assert await mail_service.EmailService().send("ravi@example.com", subject, text, html) is False
    rows = (await db_session.execute(select(EmailSendRecord).where(EmailSendRecord.organization_id == organization.id).order_by(EmailSendRecord.created_at, EmailSendRecord.recipient))).scalars().all()
    assert [(r.recipient, r.status, r.source, r.key) for r in sorted(rows, key=lambda r: r.recipient)] == [("asha@example.com", "sent", "visual", "verification"), ("ravi@example.com", "failed", "visual", "verification")]
    assert rows[0].template_id == uuid.UUID(t["id"]) and rows[0].version_id is not None
    assert next(r for r in rows if r.status == "failed").error and "smtp down" in next(r for r in rows if r.status == "failed").error
    assert all("SECRET-TOKEN" not in (r.subject + (r.error or "")) for r in rows)  # no link or token is kept
    assert smtp[0]["Subject"] == "Verify your account" and smtp[0]["To"] == "asha@example.com"
    listed = (await client.get(f"{_S}/history?key=verification", headers=auth_headers)).json()
    assert {i["recipient"] for i in listed} == {"asha@example.com", "ravi@example.com"}
    first = next(i for i in listed if i["recipient"] == "asha@example.com")
    assert first["template_name"] == "Verify email" and first["version_number"] == 1 and first["status"] == "sent"
    assert {i["recipient"] for i in (await client.get(f"{_S}/history?status=failed", headers=auth_headers)).json()} == {"ravi@example.com"}


async def test_a_brand_reply_to_and_sender_name_are_used_and_a_subject_cannot_add_a_header(db_session, organization, monkeypatch):
    from packages.email.history import SendMeta, set_send_meta

    sent: list = []

    async def fake_smtp(message, **kwargs):
        sent.append(message)

    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr("app.db.session.get_db_context", same_session)
    monkeypatch.setattr(mail_service.aiosmtplib, "send", fake_smtp)
    set_send_meta(SendMeta(organization_id=organization.id, reply_to="hello@girtechnologies.com", from_name='GIR "Technologies"'))
    await mail_service.EmailService().send("a@example.com", "Hi\r\nBcc: evil@example.com", "text", "<p>x</p>")
    message = sent[0]
    assert message["Reply-To"] == "hello@girtechnologies.com" and message["Bcc"] is None and "\n" not in message["Subject"]
    assert message["From"].startswith("GIR Technologies <")
    # the note applies to one email only
    await mail_service.EmailService().send("b@example.com", "Plain", "text")
    assert sent[1]["Reply-To"] is None


# ------------------------------------------------------------ permissions and isolation


async def test_who_can_view_edit_and_publish(client, auth_headers, staff_headers, db_session, organization):
    t = await create(client, auth_headers)
    assert (await client.get(f"{_S}/library", headers=staff_headers)).status_code == 403  # no permission at all
    assert (await client.get(f"{_S}/library")).status_code == 401
    viewer = await user_with(db_session, organization, ["email_templates.view"])
    editor = await user_with(db_session, organization, ["email_templates.view", "email_templates.manage"])
    admin = await user_with(db_session, organization, ["email_templates.view", "email_templates.manage", "email_templates.publish"])
    assert (await client.get(f"{_S}/templates/{t['id']}", headers=viewer)).status_code == 200
    assert (await client.post(f"{_S}/templates", json={"name": "x", "source_type": "visual", **draft()}, headers=viewer)).status_code == 403
    assert (await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(), headers=viewer)).status_code == 403
    assert (await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(), headers=editor)).status_code == 200
    assert (await client.post(f"{_S}/templates/{t['id']}/publish", headers=editor)).status_code == 403  # editing is not publishing
    assert (await client.post(f"{_S}/test", json={"source_type": "visual", "draft": draft(), "to_email": "a@b.co"}, headers=viewer)).status_code == 403
    assert (await client.post(f"{_S}/templates/{t['id']}/publish", headers=admin)).status_code == 200
    assert (await client.put(f"{_S}/assignments/verification", json={"template_id": t["id"]}, headers=editor)).status_code == 403
    assert (await client.put(f"{_S}/assignments/verification", json={"template_id": t["id"]}, headers=admin)).status_code == 200
    sig = (await client.post(f"{_S}/signatures", json={"name": "S", "person_name": "P"}, headers=editor)).json()
    assert (await client.post(f"{_S}/signatures/{sig['id']}/approve", json={"approve": True}, headers=editor)).status_code == 403
    assert (await client.get(f"{_S}/history", headers=viewer)).status_code == 200


async def test_another_organisations_templates_brands_and_signatures_are_invisible(client, auth_headers, db_session):
    from modules.organizations.repository import OrganizationRepository

    mine = await create(client, auth_headers)
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"o-{uuid.uuid4().hex[:8]}@erpx.example.com")
    theirs = {"Authorization": f"Bearer {token}"}
    assert (await client.get(f"{_S}/templates/{mine['id']}", headers=theirs)).status_code == 404
    assert all(i["id"] != mine["id"] for i in (await client.get(f"{_S}/library", headers=theirs)).json())
    brand = (await client.post(f"{_S}/brands", json={"name": "Mine"}, headers=auth_headers)).json()
    r = await client.post(f"{_S}/templates", json={"name": "x", "source_type": "visual", **draft(brand_profile_id=brand["id"])}, headers=theirs)
    assert r.status_code == 422  # a brand of another organisation cannot be used
    assert (await client.put(f"{_S}/brands/{brand['id']}", json={"name": "Hijack"}, headers=theirs)).status_code == 404
    assert (await client.put(f"{_S}/assignments/verification", json={"template_id": mine["id"]}, headers=theirs)).status_code == 404


async def test_the_placeholder_picker_groups_names_and_limits_an_email_to_what_it_supplies(client, auth_headers):
    everything = (await client.get(f"{_S}/placeholders", headers=auth_headers)).json()
    groups = {p["group"] for p in everything}
    assert {"Account", "Student", "Institution", "Internship", "Company", "Documents", "System"} <= groups
    names = {p["name"] for p in everything}
    assert {"student_name", "institution_location", "internship_start_date", "signature", "brand_footer", "verification_url"} <= names
    only = {p["name"] for p in (await client.get(f"{_S}/placeholders?key=verification", headers=auth_headers)).json()}
    assert "verification_url" in only and "internship_name" not in only and "company_name" in only


async def test_the_older_markdown_editor_still_works_beside_the_studio(client, auth_headers, db_session, organization):
    saved = await client.put("/api/v1/email-templates/verification", json={"subject": "Old way {{full_name}}", "body": "# Hi {{full_name}}\n\n[Go]({{verification_url}})"}, headers=auth_headers)
    assert saved.status_code == 200
    subject, _, html = await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": "https://x.example/v"}, organization_id=organization.id)
    assert subject == "Old way Asha" and "Hi Asha" in html
    items = {i["key"]: i for i in (await client.get(f"{_S}/library", headers=auth_headers)).json() if i["is_system"]}
    assert items["verification"]["creation_method"] == "Markdown (built-in)" and items["verification"]["customised"] is True
    # a published, assigned studio template takes precedence; removing the assignment brings the Markdown wording back
    t = await create(client, auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    assert (await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": "https://x.example/v"}, organization_id=organization.id))[0] == "Verify your account"
    await client.delete(f"{_S}/assignments/verification", headers=auth_headers)
    assert (await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": "https://x.example/v"}, organization_id=organization.id))[0] == "Old way Asha"


# ------------------------------------------------------------ attachments and the modules that send


async def test_shared_pdfs_are_attached_and_a_required_recipient_document_cannot_be_forgotten(client, auth_headers, db_session, organization, monkeypatch):
    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr("app.db.session.get_db_context", same_session)
    smtp: list = []

    async def fake_smtp(message, **kwargs):
        smtp.append(message)

    monkeypatch.setattr(mail_service.aiosmtplib, "send", fake_smtp)
    guide = (await client.post(f"{_S}/assets?purpose=attachment", files={"file": ("guidelines.pdf", b"%PDF-1.4 guide", "application/pdf")}, headers=auth_headers)).json()
    attachments = [{"kind": "shared", "asset": guide["id"], "name": "guidelines.pdf"}, {"kind": "recipient", "name": "Certificate", "required": True}]
    t = await create(client, auth_headers, name="Cert mail", config={"attachments": attachments})
    await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(html=page("<p>Hi {{full_name}} {{internship_title}} {{certificate_type}}</p>"), config={"attachments": attachments}), headers=auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "internship_completion_certificate", t["id"])
    values = {"full_name": "Asha", "internship_title": "Cyber", "certificate_type": "completion"}
    # the preview shows what will go with the email
    prev = (await client.post(f"{_S}/preview", json={"source_type": "visual", "draft": draft(config={"attachments": attachments}), "context": {"type": "sample"}}, headers=auth_headers)).json()
    assert [a["kind"] for a in prev["attachments"]] == ["shared", "recipient"]

    certificate = mail_service.EmailAttachment(filename="Certificate_Asha.pdf", content=b"%PDF-1.4 hers", mime_type="application/pdf")
    subject, text, html = await render_email(db_session, "internship_completion_certificate", values, organization_id=organization.id)
    assert await mail_service.EmailService().send("asha@example.com", subject, text, html, attachments=[certificate]) is True
    names = sorted(part.get_filename() for part in smtp[0].iter_attachments())
    assert names == ["Certificate_Asha.pdf", "guidelines.pdf"]  # her own certificate plus the shared guide

    # the sender forgot the student's certificate: nothing is sent, and the history says why
    subject, text, html = await render_email(db_session, "internship_completion_certificate", values, organization_id=organization.id)
    assert await mail_service.EmailService().send("ravi@example.com", subject, text, html) is False
    assert len(smtp) == 1
    failed = (await db_session.execute(select(EmailSendRecord).where(EmailSendRecord.recipient == "ravi@example.com"))).scalar_one()
    assert failed.status == "failed" and "required attachment is missing" in failed.error and "Certificate" in failed.error
    # an email that does not use the template is not affected
    plain = await render_email(db_session, "announcement", {"full_name": "A", "title": "T", "body": "B", "scope_label": "S"}, organization_id=organization.id)
    assert await mail_service.EmailService().send("x@example.com", *plain) is True


async def _generated_and_approved(client, auth_headers, monkeypatch, db_session, select_emails=None):
    """An internship with generated, approved offer letters, and the background work running on the test session."""
    from modules.our_internships import letter_routes, letter_tasks
    from tests.api.test_offer_letters import approved, by_name, students as letter_students, url as letter_url

    @asynccontextmanager
    async def same_session():
        yield db_session

    queued: list = []
    monkeypatch.setattr(letter_tasks, "get_db_context", same_session)
    monkeypatch.setattr(letter_routes, "enqueue_generation", lambda ids: queued.append(list(ids)))
    monkeypatch.setattr(letter_routes, "enqueue_letter_emails", lambda ids: None)
    internship, _ = await _setup(client, auth_headers, **({"select_emails": select_emails} if select_emails else {}))
    await approved(client, auth_headers, internship)
    await client.post(letter_url(internship, "/generate"), json={}, headers=auth_headers)
    while queued:
        await letter_tasks.generate_batch(queued.pop(0))
    asha = by_name(await letter_students(client, auth_headers, internship))["Asha Rao"]["letter"]["id"]
    await client.post(letter_url(internship, "/approve"), json={"letter_ids": [asha]}, headers=auth_headers)
    return internship, asha, letter_url


async def test_the_offer_letter_release_uses_the_assigned_studio_template_with_the_students_own_pdf(client, auth_headers, db_session, monkeypatch):
    from modules.our_internships import letter_tasks

    mailed: list[dict] = []

    async def send(to, subject, text, html=None, attachments=None):
        mailed.append({"to": to, "subject": subject, "text": text, "html": html, "attachments": attachments or []})
        return True

    internship, asha, letter_url = await _generated_and_approved(client, auth_headers, monkeypatch, db_session)
    monkeypatch.setattr(letter_tasks.email_service, "send", send)
    html = page("<h1>Congratulations {{student_name}}</h1><p>{{internship_position}} at {{company_name}} ({{institution_name}}), ref {{reference}}</p>")
    t = await create(client, auth_headers, name="Offer mail", subject="Offer for {{student_name}} from {{company_name}}", html=html)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "internship_offer_letter", t["id"])
    await client.post(letter_url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)
    assert await letter_tasks._send_letter(uuid.UUID(asha)) is True
    mail = mailed[0]
    assert mail["to"] == "asha@example.com" and mail["subject"] == "Offer for Asha Rao from GIR Technologies"
    assert "Congratulations Asha Rao" in mail["html"] and "Intern at GIR Technologies (Sri Venkateswara College)" in mail["text"]
    assert len(mail["attachments"]) == 1 and mail["attachments"][0].filename.startswith("OfferLetter_AshaRao")  # her own letter
    preview = (await client.post(letter_url(internship, "/email-preview"), json={"student_id": None}, headers=auth_headers)).json()
    assert preview["subject"].startswith("Offer for Asha Rao")
    # without an assignment the email written in the letter settings is used, exactly as before
    await client.delete(f"{_S}/assignments/internship_offer_letter", headers=auth_headers)
    plain = (await client.post(letter_url(internship, "/email-preview"), json={"student_id": None}, headers=auth_headers)).json()
    assert plain["subject"] == "Your internship offer letter - GIR Technologies"


async def test_a_template_the_offer_email_cannot_fill_is_refused_and_a_complete_one_is_sent(client, auth_headers, db_session, monkeypatch):
    from modules.our_internships import letter_tasks

    sent: list = []

    async def send(*args, **kwargs):
        sent.append(args)
        return True

    internship, asha, letter_url = await _generated_and_approved(client, auth_headers, monkeypatch, db_session, select_emails=("asha@example.com",))
    monkeypatch.setattr(letter_tasks.email_service, "send", send)
    bad = await create(client, auth_headers, name="Bad", html=page("<p>{{student_name}} {{verification_url}}</p>"))
    await publish(client, auth_headers, bad)
    await assign(client, auth_headers, "internship_offer_letter", bad["id"], 422)  # a placeholder this email does not supply
    ok = await create(client, auth_headers, name="Ok", html=page("<p>{{student_name}} {{internship_position}}</p>"))
    await publish(client, auth_headers, ok)
    await assign(client, auth_headers, "internship_offer_letter", ok["id"])
    await client.post(letter_url(internship, "/release"), json={"letter_ids": [asha]}, headers=auth_headers)
    assert await letter_tasks._send_letter(uuid.UUID(asha)) is True
    assert len(sent) == 1


async def test_the_internship_welcome_email_uses_a_template_when_one_is_assigned(client, auth_headers, db_session, organization, monkeypatch):
    from modules.our_internships import onboarding

    mailed: list = []

    async def send(to, subject, text, html=None, attachments=None):
        mailed.append((to, subject, text, html))
        return True

    @asynccontextmanager
    async def same_session():
        yield db_session

    monkeypatch.setattr("app.db.session.get_db_context", same_session)
    monkeypatch.setattr(onboarding.email_service, "send", send)
    await _make_user(db_session, organization, is_superuser=False, email="welcome@example.com")
    outcome = onboarding.GrantOutcome(created_account=False, email="welcome@example.com", full_name="Asha Rao", reset_token=None, course_title="Cyber 101", internship_title="Pentrix Cyber Internship")
    await onboarding.notify_access(outcome)
    assert mailed[-1][1] == "Your Pentrix LMS access is ready" and "Cyber 101" in mailed[-1][2]
    assert mailed[-1][3]  # the built-in wording now has an HTML version too
    t = await create(client, auth_headers, name="Welcome", subject="Welcome to {{internship_title}}", html=page('<p>Hi {{full_name}}, {{course_title}}</p><p><a href="{{login_url}}">Sign in</a></p>'))
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "internship_welcome", t["id"])
    await onboarding.notify_access(outcome)
    assert mailed[-1][1] == "Welcome to Pentrix Cyber Internship" and "Hi Asha Rao, Cyber 101" in mailed[-1][2]


# ------------------------------------------------------------ deleting templates (soft: hidden and restorable, nothing erased)


async def test_a_template_you_made_is_deleted_softly_but_not_while_an_erpx_email_uses_it(client, auth_headers, db_session, organization):
    from modules.email_studio.models import EmailStudioTemplate, EmailStudioVersion

    t = await create(client, auth_headers, name="To delete")
    await publish(client, auth_headers, t)
    await client.put(f"{_S}/templates/{t['id']}/draft", json=draft(subject="Second"), headers=auth_headers)
    await assign(client, auth_headers, "verification", t["id"])
    # the library already says it cannot be deleted, and which ERPX email depends on it
    item = next(i for i in (await client.get(f"{_S}/library", headers=auth_headers)).json() if i["id"] == t["id"])
    assert item["can_delete"] is False and [u["name"] for u in item["used_by"]] == ["Verify your email"] and "Use for" in item["delete_blocked_reason"]
    busy = await client.delete(f"{_S}/templates/{t['id']}", headers=auth_headers)
    assert busy.status_code == 409 and "Verify your email" in busy.text and "Use for" in busy.text
    assert any(i["id"] == t["id"] for i in (await client.get(f"{_S}/library", headers=auth_headers)).json())  # still there
    # pointing the ERPX email somewhere else frees it
    await client.delete(f"{_S}/assignments/verification", headers=auth_headers)
    item = next(i for i in (await client.get(f"{_S}/library", headers=auth_headers)).json() if i["id"] == t["id"])
    assert item["can_delete"] is True and item["delete_blocked_reason"] is None
    gone = await client.delete(f"{_S}/templates/{t['id']}", headers=auth_headers)
    assert gone.status_code == 200 and "Recently deleted" in gone.json()["message"]
    assert all(i["id"] != t["id"] for i in (await client.get(f"{_S}/library", headers=auth_headers)).json())
    assert (await client.get(f"{_S}/templates/{t['id']}", headers=auth_headers)).status_code == 404
    assert (await client.delete(f"{_S}/templates/{t['id']}", headers=auth_headers)).status_code == 404  # already gone
    # nothing was erased: the row, its versions and who deleted it are all still there
    tid = uuid.UUID(t["id"])
    row = (await db_session.execute(select(EmailStudioTemplate).where(EmailStudioTemplate.id == tid))).scalar_one()
    assert row.deleted_at is not None and row.deleted_by_user_id is not None
    assert len((await db_session.execute(select(EmailStudioVersion).where(EmailStudioVersion.template_id == tid))).scalars().all()) == 2
    # and it is listed under Recently deleted, from where it comes back whole
    listed = (await client.get(f"{_S}/deleted", headers=auth_headers)).json()
    assert [i["name"] for i in listed if i["id"] == t["id"]] == ["To delete"] and listed[0]["deleted_at"]
    restored = await client.post(f"{_S}/templates/{t['id']}/restore-deleted", headers=auth_headers)
    assert restored.status_code == 200 and restored.json()["deleted_at"] is None and restored.json()["status"] == "published"
    assert any(i["id"] == t["id"] for i in (await client.get(f"{_S}/library", headers=auth_headers)).json())
    assert (await client.post(f"{_S}/templates/{t['id']}/restore-deleted", headers=auth_headers)).status_code == 409  # not deleted


async def test_a_deleted_template_is_never_used_for_a_real_email(client, auth_headers, db_session, organization):
    t = await create(client, auth_headers, name="Short lived")
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    # an assignment cannot be bypassed: even if one were left behind, a deleted template is skipped and the built-in wording is used
    from modules.email_studio.models import EmailStudioTemplate

    row = await db_session.get(EmailStudioTemplate, uuid.UUID(t["id"]))
    from datetime import datetime, timezone

    row.deleted_at = datetime.now(timezone.utc)
    await db_session.flush()
    subject, _, _ = await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": "https://x.example/v"}, organization_id=organization.id)
    assert subject != "Verify your account"


async def test_a_draft_only_and_an_archived_template_can_be_deleted_too(client, auth_headers):
    draft_only = await create(client, auth_headers, name="Never published")
    assert (await client.delete(f"{_S}/templates/{draft_only['id']}", headers=auth_headers)).status_code == 200
    archived = await create(client, auth_headers, name="Archived one")
    await publish(client, auth_headers, archived)
    await client.post(f"{_S}/templates/{archived['id']}/archive", headers=auth_headers)
    assert (await client.delete(f"{_S}/templates/{archived['id']}", headers=auth_headers)).status_code == 200


async def test_system_templates_are_protected_by_a_flag_not_by_their_name(client, auth_headers, db_session, organization):
    from modules.email_studio.models import EmailStudioTemplate

    # the built-in ERPX emails are not studio templates: there is nothing to delete, and no route to do it
    assert (await client.delete(f"{_S}/templates/system:verification", headers=auth_headers)).status_code == 422
    assert (await client.delete(f"{_S}/templates/{uuid.uuid4()}", headers=auth_headers)).status_code == 404
    built_in = [i for i in (await client.get(f"{_S}/library", headers=auth_headers)).json() if i["id"].startswith("system:")]
    assert built_in and all(i["is_system"] and i["can_delete"] is False for i in built_in)
    # a studio template carrying the system flag is refused by the server, whatever it is called
    t = await create(client, auth_headers, name="Totally ordinary name")
    row = await db_session.get(EmailStudioTemplate, uuid.UUID(t["id"]))
    row.is_system = True
    await db_session.flush()
    item = next(i for i in (await client.get(f"{_S}/library", headers=auth_headers)).json() if i["id"] == t["id"])
    assert item["is_system"] is True and item["can_delete"] is False and "protected" in item["delete_blocked_reason"]
    refused = await client.delete(f"{_S}/templates/{t['id']}", headers=auth_headers)
    assert refused.status_code == 403 and "protected" in refused.text
    assert (await client.get(f"{_S}/templates/{t['id']}", headers=auth_headers)).status_code == 200  # untouched
    # the flag is not something a request can set
    r = await client.post(f"{_S}/templates", json={"name": "Sneaky", "source_type": "visual", "category": "Custom Emails", "is_system": True, **draft()}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["is_system"] is False


async def test_sent_emails_keep_their_history_and_the_audit_trail_records_the_deletion(client, auth_headers, db_session, organization, monkeypatch):
    from modules.audit.models import AuditLog

    @asynccontextmanager
    async def same_session():
        yield db_session

    async def fake_smtp(message, **kwargs):
        return None

    monkeypatch.setattr("app.db.session.get_db_context", same_session)
    monkeypatch.setattr(mail_service.aiosmtplib, "send", fake_smtp)
    t = await create(client, auth_headers, name="Used once")
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    subject, text, html = await render_email(db_session, "verification", {"full_name": "Asha", "verification_url": "https://x.example/v"}, organization_id=organization.id)
    assert await mail_service.EmailService().send("asha@example.com", subject, text, html) is True
    await client.delete(f"{_S}/assignments/verification", headers=auth_headers)
    assert (await client.delete(f"{_S}/templates/{t['id']}", headers=auth_headers)).status_code == 200
    rows = (await db_session.execute(select(EmailSendRecord).where(EmailSendRecord.recipient == "asha@example.com"))).scalars().all()
    assert len(rows) == 1 and rows[0].status == "sent" and str(rows[0].template_id) == t["id"]  # the record still points at the template
    history = (await client.get(f"{_S}/history", headers=auth_headers)).json()
    assert any(h["recipient"] == "asha@example.com" and h["template_name"] == "Used once" for h in history)
    # the deletion is in the audit trail: who, when, and what changed
    logs = (
        await db_session.execute(select(AuditLog).where(AuditLog.entity_type == "email_studio_templates", AuditLog.entity_id == uuid.UUID(t["id"])))
    ).scalars().all()
    assert any("deleted_at" in (log.changes or {}) or "deleted_at" in str(log.changes) for log in logs)


async def test_deleting_needs_permission_and_stays_inside_the_organisation(client, auth_headers, db_session, organization):
    from modules.organizations.repository import OrganizationRepository

    t = await create(client, auth_headers, name="Protected")
    viewer = await user_with(db_session, organization, ["email_templates.view"])
    assert (await client.delete(f"{_S}/templates/{t['id']}", headers=viewer)).status_code == 403
    assert (await client.get(f"{_S}/deleted", headers=viewer)).status_code == 403
    other_org = await OrganizationRepository(db_session).create(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other_org, is_superuser=True, email=f"o-{uuid.uuid4().hex[:8]}@erpx.example.com")
    assert (await client.delete(f"{_S}/templates/{t['id']}", headers={"Authorization": f"Bearer {token}"})).status_code == 404
    editor = await user_with(db_session, organization, ["email_templates.view", "email_templates.manage"])
    assert (await client.delete(f"{_S}/templates/{t['id']}", headers=editor)).status_code == 200  # managing is enough
    # another organisation can neither see nor restore it
    assert (await client.post(f"{_S}/templates/{t['id']}/restore-deleted", headers={"Authorization": f"Bearer {token}"})).status_code == 404
    assert (await client.get(f"{_S}/deleted", headers={"Authorization": f"Bearer {token}"})).json() == []
