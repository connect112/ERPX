"""
Email Studio, importing React Email code: checking it, saving it (the pasted source is kept exactly), previewing, test sending,
publishing and using it for an ERPX email, and the rules that stop code that cannot be imported safely. The importer itself is
covered by tests/unit/test_react_import.py.
"""

import uuid

import pytest
from sqlalchemy import select

from modules.email_studio.models import EmailStudioVersion
from modules.email_templates.render import render_email
from tests.api.test_email_studio import _S, assign, create, draft, mailbox, publish, user_with  # noqa: F401

pytestmark = pytest.mark.api

SOURCE = """import { Body, Button, Container, Head, Heading, Html, Preview, Section, Text, Tailwind } from "@react-email/components";

export default function Verify() {
  return (
    <Html>
      <Head><title>Verify</title></Head>
      <Preview>Confirm your email address</Preview>
      <Tailwind>
        <Body className="bg-white">
          <Container className="mx-auto max-w-[560px] p-5">
            <Heading className="text-2xl font-bold">Welcome, {{full_name}}</Heading>
            <Text className="text-[16px] leading-6">Confirm your email to finish signing up.</Text>
            <Section>
              <Button href="{{verification_url}}" className="rounded-lg bg-blue-600 px-5 py-3 text-white">Verify email</Button>
            </Section>
          </Container>
        </Body>
      </Tailwind>
    </Html>
  );
}
"""

BROKEN = SOURCE.replace("<Heading", '<Heading onClick={() => alert(1)}', 1).replace("Confirm your email to finish", '{eval("1")} Confirm your email to finish')


def react(source=SOURCE, **over):
    return {"subject": "Verify your account", "react_source": source, **over}


async def make(client, headers, name="Imported", source=SOURCE, **over):
    payload = {"name": name, "source_type": "react", "category": "Account Verification", **react(source, **over)}
    r = await client.post(f"{_S}/templates", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_the_code_is_checked_without_saving_anything_and_problems_name_their_line(client, auth_headers):
    ok = (await client.post(f"{_S}/react-import/build", json={"source": SOURCE}, headers=auth_headers)).json()
    assert ok["ok"] is True and ok["errors"] == []
    assert "Welcome, {{full_name}}" in ok["html"] and 'href="{{verification_url}}"' in ok["html"] and ok["title"] == "Verify"
    assert ok["preheader"] == "Confirm your email address" and sorted(ok["placeholders"]) == ["full_name", "verification_url"]
    assert ok["unsupported_placeholders"] == []
    typo = (await client.post(f"{_S}/react-import/build", json={"source": SOURCE.replace("{{full_name}}", "{{fullname}}")}, headers=auth_headers)).json()
    assert typo["ok"] is True and typo["unsupported_placeholders"] == ["fullname"]  # reported, so it can be fixed before sending
    bad = (await client.post(f"{_S}/react-import/build", json={"source": BROKEN}, headers=auth_headers)).json()
    assert bad["ok"] is False and bad["html"] == ""
    lines = {e["line"] for e in bad["errors"]}
    assert lines and None not in lines and all("`" in e["message"] or "event handler" in e["message"] for e in bad["errors"])
    assert any("onClick" in e["message"] for e in bad["errors"]) and any("eval" in e["message"] for e in bad["errors"])


async def test_checking_code_needs_permission_to_manage_templates(client, auth_headers, db_session, organization):
    viewer = await user_with(db_session, organization, ["email_templates.view"])
    assert (await client.post(f"{_S}/react-import/build", json={"source": SOURCE}, headers=viewer)).status_code == 403
    assert (await client.post(f"{_S}/react-import/build", json={"source": "x" * 200_001}, headers=auth_headers)).status_code == 422


async def test_imported_code_is_saved_exactly_and_the_email_is_built_on_the_server(client, auth_headers, db_session):
    t = await make(client, auth_headers)
    assert t["source_type"] == "react" and t["current"]["react_source"] == SOURCE  # byte for byte
    assert "Welcome, {{full_name}}" in t["current"]["body_html"] and "<script" not in t["current"]["body_html"].lower()
    assert t["current"]["config"]["react_build"]["ok"] is True
    item = next(i for i in (await client.get(f"{_S}/library", headers=auth_headers)).json() if i["id"] == t["id"])
    assert item["creation_method"] == "React Email code" and item["source_type"] == "react"
    # HTML sent along by the browser is never trusted: the email is always rebuilt from the source
    sneaky = await make(client, auth_headers, name="Sneaky", html="<script>alert(1)</script><p>pwned</p>", editor_json={"type": "doc"})
    assert "pwned" not in sneaky["current"]["body_html"] and "<script" not in sneaky["current"]["body_html"].lower()
    # reopening gives the same source back
    again = (await client.get(f"{_S}/templates/{t['id']}", headers=auth_headers)).json()
    assert again["current"]["react_source"] == SOURCE
    assert (await client.post(f"{_S}/templates", json={"name": "Empty", "source_type": "react", "category": "Custom Emails", "subject": "x", "react_source": "  "}, headers=auth_headers)).status_code == 422


async def test_code_with_errors_can_be_kept_as_a_draft_but_not_previewed_or_published(client, auth_headers):
    t = await make(client, auth_headers, name="Work in progress", source=BROKEN)
    assert t["current"]["react_source"] == BROKEN and t["current"]["body_html"] == ""
    assert t["current"]["config"]["react_build"]["ok"] is False and t["current"]["config"]["react_build"]["errors"] >= 2
    preview = await client.post(f"{_S}/preview", json={"source_type": "react", "draft": react(BROKEN), "context": {"type": "sample", "key": "verification"}}, headers=auth_headers)
    assert preview.status_code == 422 and "Line" in preview.text
    refused = await client.post(f"{_S}/templates/{t['id']}/publish", headers=auth_headers)
    assert refused.status_code == 422 and "cannot be published" in refused.text and "line" in refused.text
    # fixing the code and saving again makes it publishable
    fixed = await client.put(f"{_S}/templates/{t['id']}/draft", json=react(SOURCE), headers=auth_headers)
    assert fixed.status_code == 200 and fixed.json()["current"]["config"]["react_build"]["ok"] is True and "Welcome" in fixed.json()["current"]["body_html"]
    assert (await client.post(f"{_S}/templates/{t['id']}/publish", headers=auth_headers)).status_code == 200


async def test_the_preview_shows_the_final_email_with_sample_data_and_a_test_can_be_sent(client, auth_headers, mailbox):
    body = {"source_type": "react", "draft": react(), "context": {"type": "sample", "key": "verification"}}
    r = (await client.post(f"{_S}/preview", json=body, headers=auth_headers)).json()
    assert r["subject"] == "Verify your account" and "Welcome, Asha Rao" in r["html"] and "https://erp.example.com/verify?token=abc123" in r["html"]
    assert "Welcome, Asha Rao" in r["text"] and r["unsupported"] == [] and r["missing"] == []
    assert "Confirm your email address" in r["html"]  # the <Preview> text became the hidden preview line
    sent = (await client.post(f"{_S}/test", json={**body, "to_email": "me@example.com"}, headers=auth_headers)).json()
    assert sent["sent"] is True
    assert mailbox.sent[0]["subject"] == "[TEST] Verify your account" and "This is a test email" in mailbox.sent[0]["html"]
    bad = {**body, "draft": react(SOURCE.replace("{{verification_url}}", "{{not_a_thing}}"))}
    assert (await client.post(f"{_S}/test", json={**bad, "to_email": "me@example.com"}, headers=auth_headers)).status_code == 422
    # the preview line can be set in the editor instead of in the code
    custom = (await client.post(f"{_S}/preview", json={**body, "draft": react(preheader="Almost there")}, headers=auth_headers)).json()
    assert "Almost there" in custom["html"] and "Confirm your email address" not in custom["html"]


async def test_published_code_is_used_for_the_real_email_with_values_escaped(client, auth_headers, db_session, organization):
    t = await make(client, auth_headers)
    await publish(client, auth_headers, t)
    await assign(client, auth_headers, "verification", t["id"])
    subject, text, html = await render_email(
        db_session, "verification", {"full_name": '<img src=x onerror="evil()">', "verification_url": "https://x.example/v?a=1&b=2"}, organization_id=organization.id
    )
    assert subject == "Verify your account"
    assert "<img src=x" not in html and "&lt;img src=x onerror" in html
    assert 'href="https://x.example/v?a=1&amp;b=2"' in html
    # an ERPX email that needs its link refuses code that dropped it
    no_link = await make(client, auth_headers, name="No link", source=SOURCE.replace('href="{{verification_url}}"', 'href="https://example.com"'))
    await publish(client, auth_headers, no_link)
    refused = await client.put(f"{_S}/assignments/verification", json={"template_id": no_link["id"]}, headers=auth_headers)
    assert refused.status_code == 422 and "verification_url" in refused.text


async def test_editing_keeps_every_version_of_the_source_and_duplicates_carry_it(client, auth_headers, db_session):
    t = await publish(client, auth_headers, await make(client, auth_headers))
    edited = SOURCE.replace("Welcome, ", "Hello again, ")
    saved = (await client.put(f"{_S}/templates/{t['id']}/draft", json=react(edited), headers=auth_headers)).json()
    assert saved["current"]["react_source"] == edited and "Hello again, {{full_name}}" in saved["current"]["body_html"]
    published = await db_session.get(EmailStudioVersion, uuid.UUID(t["published_version_id"]))
    assert published.react_source == SOURCE and "Welcome, {{full_name}}" in published.body_html  # the live version did not change
    versions = (await client.get(f"{_S}/templates/{t['id']}/versions", headers=auth_headers)).json()
    first = next(v for v in versions if v["state"] == "published")
    restored = (await client.post(f"{_S}/templates/{t['id']}/versions/{first['id']}/restore", headers=auth_headers)).json()
    assert restored["current"]["react_source"] == SOURCE
    copy = (await client.post(f"{_S}/templates/{t['id']}/duplicate", headers=auth_headers)).json()
    assert copy["source_type"] == "react" and copy["current"]["react_source"] == SOURCE and copy["id"] != t["id"]


async def test_a_signature_is_added_only_where_the_code_asks_for_it(client, auth_headers):
    sig = (await client.post(f"{_S}/signatures", json={"name": "Team", "scope": "company", "company_name": "GIR Technologies", "person_name": "Srujan"}, headers=auth_headers)).json()
    plain = (await client.post(f"{_S}/preview", json={"source_type": "react", "draft": react(signature_id=sig["id"]), "context": {"type": "sample", "key": "verification"}}, headers=auth_headers)).json()
    assert "Srujan" not in plain["html"]  # imported code is never given a second signature on top of its own sign-off
    placed = SOURCE.replace("</Container>", "<Text>{{signature}}</Text></Container>")
    shown = (await client.post(f"{_S}/preview", json={"source_type": "react", "draft": react(placed, signature_id=sig["id"]), "context": {"type": "sample", "key": "verification"}}, headers=auth_headers)).json()
    assert shown["html"].count("Srujan") == 1
    again = (await client.post(f"{_S}/preview", json={"source_type": "react", "draft": react(placed.replace("</Container>", "<Text>{{signature}}</Text></Container>"), signature_id=sig["id"]), "context": {"type": "sample", "key": "verification"}}, headers=auth_headers)).json()
    assert any("{{signature}}" in w for w in again["warnings"])  # using it twice is reported


async def test_existing_html_and_visual_templates_are_unaffected(client, auth_headers):
    visual = await create(client, auth_headers, name="Visual one")
    html = await create(client, auth_headers, name="Html one", source="html")
    assert visual["source_type"] == "visual" and "react_source" in visual["current"] and visual["current"]["react_source"] is None
    assert html["source_type"] == "html" and html["current"]["react_source"] is None
    assert (await publish(client, auth_headers, visual))["status"] == "published"
    assert (await publish(client, auth_headers, html))["status"] == "published"
    # sending a react payload to a visual template does not turn it into one
    r = await client.put(f"{_S}/templates/{visual['id']}/draft", json={**draft(), "react_source": SOURCE}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["current"]["react_source"] is None and r.json()["source_type"] == "visual"
    # deleting a react template is soft like any other
    t = await make(client, auth_headers, name="Delete me")
    assert (await client.delete(f"{_S}/templates/{t['id']}", headers=auth_headers)).status_code == 200
    restored = (await client.post(f"{_S}/templates/{t['id']}/restore-deleted", headers=auth_headers)).json()
    assert restored["current"]["react_source"] == SOURCE
    rows = (await client.get(f"{_S}/library", headers=auth_headers)).json()
    assert {"Visual one", "Html one", "Delete me"} <= {i["name"] for i in rows}
