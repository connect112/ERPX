"""
API tests for login-free workshop MCQ exams: admin setup, the tokenised
attendee flow (no auth header anywhere on those calls), scoring,
timeouts, certificate dispatch for everyone who wrote the exam, and the
permission boundary on the admin routes.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from modules.workshop_exams.certificate_pdf import build_certificate_pdf
from modules.workshop_exams.models import WorkshopExamAttendee

pytestmark = pytest.mark.api

_BASE = "/api/v1/workshop-exams"
_PUBLIC = "/api/v1/public/workshop-exams"

_QUESTIONS = [
    {"text": "2 + 2?", "options": ["3", "4", "5"], "correct_indices": [1], "marks": 1},
    {"text": "Capital of France?", "options": ["Paris", "Rome"], "correct_indices": [0], "marks": 2},
    {"text": "Is the sky blue?", "options": ["Yes", "No"], "correct_indices": [0], "marks": 1},
]


async def _open_exam(client, auth_headers, attendees=None, **overrides):
    payload = {"title": "Workshop MCQ", "duration_minutes": 30, **overrides}
    resp = await client.post(_BASE, json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    exam = resp.json()
    resp = await client.post(
        f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers
    )
    assert resp.status_code == 201, resp.text
    attendees = attendees or [
        {"name": "Asha Rao", "email": "asha@example.com"},
        {"name": "Ravi Kumar", "email": "ravi@example.com"},
        {"name": "Meena S", "email": "meena@example.com"},
    ]
    resp = await client.post(f"{_BASE}/{exam['id']}/attendees", json={"attendees": attendees}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return exam


async def _tokens(db_session, exam_id) -> dict[str, str]:
    rows = (
        await db_session.execute(
            select(WorkshopExamAttendee).where(WorkshopExamAttendee.exam_id == uuid.UUID(exam_id))
        )
    ).scalars().all()
    return {a.email: a.access_token for a in rows}


def _correct_answers(questions: list[dict]) -> dict[str, list[int]]:
    by_text = {q["text"]: q["correct_indices"] for q in _QUESTIONS}
    return {q["id"]: by_text[q["text"]] for q in questions}


async def test_attendee_takes_exam_without_login_and_is_scored(client, db_session, auth_headers):
    exam = await _open_exam(client, auth_headers)
    token = (await _tokens(db_session, exam["id"]))["asha@example.com"]

    info = (await client.get(f"{_PUBLIC}/{token}")).json()
    assert info["state"] == "ready"
    assert info["attendee_name"] == "Asha Rao"

    start = await client.post(f"{_PUBLIC}/{token}/start")
    assert start.status_code == 200, start.text
    body = start.json()
    assert len(body["questions"]) == 3
    # The answer key must never reach the browser.
    assert "correct_ind" not in str(body)

    answers = _correct_answers(body["questions"])
    wrong_id = next(q["id"] for q in body["questions"] if q["text"] == "2 + 2?")
    answers[wrong_id] = [0]  # one wrong answer

    resp = await client.post(f"{_PUBLIC}/{token}/submit", json={"answers": answers})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"submitted": True, "score": None, "total_marks": None}  # show_result off

    # One attempt only.
    again = await client.post(f"{_PUBLIC}/{token}/start")
    assert again.status_code == 422
    assert (await client.get(f"{_PUBLIC}/{token}")).json()["state"] == "submitted"

    dash = (await client.get(f"{_BASE}/{exam['id']}/dashboard", headers=auth_headers)).json()
    asha = next(a for a in dash["attendees"] if a["email"] == "asha@example.com")
    assert (asha["score"], asha["total_marks"]) == (3, 4)  # 2 + 1 right, 1 wrong
    assert dash["submitted"] == 1 and dash["not_started"] == 2 and dash["in_progress"] == 0


async def test_unknown_token_is_404_and_questions_not_leaked_before_open(client, db_session, auth_headers):
    assert (await client.get(f"{_PUBLIC}/not-a-real-token")).status_code == 404

    resp = await client.post(_BASE, json={"title": "Draft exam"}, headers=auth_headers)
    exam = resp.json()
    await client.post(f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers)
    await client.post(
        f"{_BASE}/{exam['id']}/attendees",
        json={"attendees": [{"name": "Early Bird", "email": "early@example.com"}]},
        headers=auth_headers,
    )
    token = (await _tokens(db_session, exam["id"]))["early@example.com"]
    assert (await client.get(f"{_PUBLIC}/{token}")).json()["state"] == "not_open"
    assert (await client.post(f"{_PUBLIC}/{token}/start")).status_code == 422


async def test_cannot_open_without_questions_or_attendees_and_questions_lock_once_someone_starts(
    client, db_session, auth_headers
):
    exam = (await client.post(_BASE, json={"title": "Empty"}, headers=auth_headers)).json()
    resp = await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert resp.status_code == 422

    opened = await _open_exam(client, auth_headers)
    # Opened but nobody has started yet: still fixable.
    resp = await client.post(
        f"{_BASE}/{opened['id']}/questions", json={"questions": _QUESTIONS[:1]}, headers=auth_headers
    )
    assert resp.status_code == 201

    token = (await _tokens(db_session, opened["id"]))["asha@example.com"]
    await client.post(f"{_PUBLIC}/{token}/start")
    resp = await client.post(
        f"{_BASE}/{opened['id']}/questions", json={"questions": _QUESTIONS[:1]}, headers=auth_headers
    )
    assert resp.status_code == 422


async def test_duplicate_emails_are_skipped_case_insensitively(client, auth_headers):
    exam = await _open_exam(
        client,
        auth_headers,
        attendees=[{"name": "A", "email": "Dup@Example.com"}],
    )
    resp = await client.post(
        f"{_BASE}/{exam['id']}/attendees",
        json={"attendees": [{"name": "A again", "email": "dup@example.com"}, {"name": "B", "email": "b@example.com"}]},
        headers=auth_headers,
    )
    assert resp.json() == {"added": 1, "skipped_duplicates": 1}


async def test_exam_auto_submits_from_saved_answers_once_time_is_up(client, db_session, auth_headers):
    exam = await _open_exam(client, auth_headers, duration_minutes=10)
    token = (await _tokens(db_session, exam["id"]))["ravi@example.com"]
    body = (await client.post(f"{_PUBLIC}/{token}/start")).json()
    answers = _correct_answers(body["questions"])
    saved = await client.put(f"{_PUBLIC}/{token}/answers", json={"answers": answers})
    assert saved.status_code == 200

    attendee = (
        await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.access_token == token))
    ).scalar_one()
    attendee.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    await db_session.commit()

    # They closed the tab and came back after the timer ran out: whatever
    # they'd autosaved is what gets scored.
    info = (await client.get(f"{_PUBLIC}/{token}")).json()
    assert info["state"] == "submitted"
    await db_session.refresh(attendee)
    assert (attendee.score, attendee.total_marks) == (4, 4)


async def test_certificates_go_to_everyone_who_wrote_the_exam_only(client, db_session, auth_headers):
    exam = await _open_exam(client, auth_headers)
    tokens = await _tokens(db_session, exam["id"])

    # Asha submits; Ravi starts but never submits; Meena never opens it.
    asha = (await client.post(f"{_PUBLIC}/{tokens['asha@example.com']}/start")).json()
    await client.post(
        f"{_PUBLIC}/{tokens['asha@example.com']}/submit", json={"answers": _correct_answers(asha["questions"])}
    )
    ravi = (await client.post(f"{_PUBLIC}/{tokens['ravi@example.com']}/start")).json()
    await client.put(
        f"{_PUBLIC}/{tokens['ravi@example.com']}/answers", json={"answers": _correct_answers(ravi["questions"])}
    )

    resp = await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert "Queued 2" in resp.json()["message"]

    attendees = {a["email"]: a for a in (await client.get(f"{_BASE}/{exam['id']}/attendees", headers=auth_headers)).json()}
    assert attendees["asha@example.com"]["certificate_number"].startswith("WS-")
    assert attendees["ravi@example.com"]["certificate_number"].startswith("WS-")  # finalized from autosave
    assert attendees["meena@example.com"]["certificate_number"] is None
    assert (
        attendees["asha@example.com"]["certificate_number"]
        != attendees["ravi@example.com"]["certificate_number"]
    )

    number = attendees["asha@example.com"]["certificate_number"]
    verified = (await client.get(f"/api/v1/public/workshop-certificates/verify/{number}")).json()
    assert verified["valid"] is True and verified["attendee_name"] == "Asha Rao"
    assert (await client.get("/api/v1/public/workshop-certificates/verify/WS-0000-NOPE")).json()["valid"] is False


def test_certificate_pdf_renders_even_with_a_very_long_name():
    pdf = build_certificate_pdf(
        attendee_name="Venkata Subrahmanya Sai Ramakrishna Chandrasekhar Iyer Narayanaswamy",
        heading="Certificate of Participation",
        body_text='has participated in the workshop "Cyber Security Basics" held on 12 October 2026.',
        issuer_name="GIR Technologies",
        issued_on=datetime(2026, 10, 12, tzinfo=timezone.utc),
        certificate_number="WS-2026-ABCD1234",
        verify_url="https://erp.pentrix.in/verify-workshop-certificate/WS-2026-ABCD1234",
    )
    assert pdf.startswith(b"%PDF") and len(pdf) > 2000


async def test_admin_routes_reject_a_user_without_workshop_permissions(client, db_session, auth_headers):
    from modules.authentication.repository import AuthRepository

    email = f"plain.{uuid.uuid4().hex[:8]}@erpx.example.com"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "PlainUserPass1!", "full_name": "Plain User"}
    )
    user = await AuthRepository(db_session).get_user_by_email(email)
    await AuthRepository(db_session).mark_email_verified(user)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "PlainUserPass1!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    exam = await _open_exam(client, auth_headers)
    for method, url, body in [
        ("post", _BASE, {"title": "Sneaky"}),
        ("get", _BASE, None),
        ("get", f"{_BASE}/{exam['id']}/dashboard", None),
        ("post", f"{_BASE}/{exam['id']}/certificates/send-now", None),
        ("post", f"{_BASE}/{exam['id']}/invites", {"resend_all": True}),
    ]:
        resp = await getattr(client, method)(url, headers=headers, **({"json": body} if body is not None else {}))
        assert resp.status_code in (403, 422), (url, resp.status_code, resp.text)
        assert resp.status_code != 200


async def test_invite_and_certificate_emails_are_built_and_sent_once(client, db_session, auth_headers, monkeypatch):
    from modules.workshop_exams import tasks

    sent = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append({"to": to, "subject": subject, "text": text, "attachments": attachments or []})
        return True

    monkeypatch.setattr(tasks.email_service, "send", fake_send)

    # The API fixtures run everything inside the test's own session; point
    # the tasks at that same session so they see the rows it created.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _same_session():
        yield db_session

    monkeypatch.setattr(tasks, "get_db_context", _same_session)

    exam = await _open_exam(client, auth_headers)
    tokens = await _tokens(db_session, exam["id"])
    attendee = (
        await db_session.execute(
            select(WorkshopExamAttendee).where(WorkshopExamAttendee.access_token == tokens["asha@example.com"])
        )
    ).scalar_one()

    assert await tasks._send_invite(attendee.id) is True
    assert sent[0]["to"] == "asha@example.com"
    assert f"/workshop-exam/{attendee.access_token}" in sent[0]["text"]

    body = (await client.post(f"{_PUBLIC}/{attendee.access_token}/start")).json()
    await client.post(
        f"{_PUBLIC}/{attendee.access_token}/submit", json={"answers": _correct_answers(body["questions"])}
    )
    await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)

    assert await tasks._send_certificate(attendee.id) is True
    cert_mail = sent[-1]
    assert cert_mail["to"] == "asha@example.com"
    assert len(cert_mail["attachments"]) == 1
    assert cert_mail["attachments"][0].mime_type == "application/pdf"
    assert cert_mail["attachments"][0].content.startswith(b"%PDF")

    await db_session.refresh(attendee)
    assert attendee.certificate_sent_at is not None
    # A retry (or a duplicate task) must not email the certificate twice.
    count = len(sent)
    assert await tasks._send_certificate(attendee.id) is True
    assert len(sent) == count


# ---------------- shared registration link, info fields, multi-answer ----------------

_JOIN = "/api/v1/public/workshop-exams/join"


async def _create_join_exam(client, auth_headers, info_fields=None):
    resp = await client.post(
        _BASE,
        json={
            "title": "Open-link MCQ",
            "duration_minutes": 20,
            "info_fields": info_fields
            or [
                {"key": "college", "label": "College", "required": True, "type": "text"},
                {"key": "year", "label": "Year", "required": True, "type": "select", "options": ["1st", "2nd", "3rd"]},
                {"key": "phone", "label": "Phone", "required": False, "type": "phone"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    exam = resp.json()
    await client.post(f"{_BASE}/{exam['id']}/questions", json={"questions": _QUESTIONS}, headers=auth_headers)
    return exam


async def test_students_self_register_from_the_shared_link_with_admin_defined_fields(
    client, db_session, auth_headers
):
    exam = await _create_join_exam(client, auth_headers)
    code = exam["public_code"]

    # A draft exam can't be opened with nobody registered yet only in the
    # pre-registered model; here students register themselves, so the
    # admin opens it with an empty list (see set_status below).
    assert (await client.get(f"{_JOIN}/{code}")).json()["state"] == "not_open"
    resp = await client.post(f"{_JOIN}/{code}/register", json={"name": "A", "email": "a@example.com", "info": {}})
    assert resp.status_code == 422

    opened = await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    assert opened.status_code == 200, opened.text
    page = (await client.get(f"{_JOIN}/{code}")).json()
    assert page["state"] == "open"
    assert [f["key"] for f in page["info_fields"]] == ["college", "year", "phone"]

    # Required field missing / invalid dropdown choice are refused.
    bad = await client.post(
        f"{_JOIN}/{code}/register", json={"name": "Asha", "email": "asha@example.com", "info": {"year": "1st"}}
    )
    assert bad.status_code == 422 and "College" in bad.text
    bad = await client.post(
        f"{_JOIN}/{code}/register",
        json={"name": "Asha", "email": "asha@example.com", "info": {"college": "ABC", "year": "9th"}},
    )
    assert bad.status_code == 422

    ok = await client.post(
        f"{_JOIN}/{code}/register",
        json={
            "name": "  Asha   Rao ",
            "email": "Asha@Example.com",
            "info": {"college": "ABC Engg", "year": "2nd", "extra": "ignored"},
        },
    )
    assert ok.status_code == 200, ok.text
    token = ok.json()["token"]
    assert token and ok.json()["already_registered"] is False

    # The personal link works exactly like an emailed one.
    assert (await client.get(f"{_PUBLIC}/{token}")).json()["attendee_name"] == "Asha Rao"
    attendee = (
        await db_session.execute(select(WorkshopExamAttendee).where(WorkshopExamAttendee.access_token == token))
    ).scalar_one()
    assert attendee.email == "asha@example.com"
    assert attendee.info == {"college": "ABC Engg", "year": "2nd"}  # unknown key dropped, optional phone omitted

    # Registering the same email again never returns the existing token.
    again = await client.post(
        f"{_JOIN}/{code}/register",
        json={"name": "Someone Else", "email": "asha@example.com", "info": {"college": "X", "year": "1st"}},
    )
    assert again.status_code == 200
    assert again.json() == {"token": None, "already_registered": True}

    csv_text = (await client.get(f"{_BASE}/{exam['id']}/results.csv", headers=auth_headers)).text
    assert csv_text.splitlines()[0].startswith("Name,Email,College,Year,Phone")
    assert "ABC Engg" in csv_text


async def test_unknown_registration_code_is_404(client):
    assert (await client.get(f"{_JOIN}/nope")).status_code == 404
    resp = await client.post(f"{_JOIN}/nope/register", json={"name": "A", "email": "a@example.com"})
    assert resp.status_code == 404


async def test_multiple_answer_questions_need_exactly_the_right_set(client, db_session, auth_headers):
    exam = (await client.post(_BASE, json={"title": "Multi"}, headers=auth_headers)).json()
    resp = await client.post(
        f"{_BASE}/{exam['id']}/questions",
        json={
            "questions": [
                {
                    "text": "Pick the primes",
                    "options": ["2", "3", "4", "5"],
                    "correct_indices": [0, 1, 3],
                    "allow_multiple": True,
                    "marks": 3,
                },
                {"text": "Pick one colour", "options": ["Red", "Dog"], "correct_indices": [0], "marks": 1},
            ]
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    await client.post(
        f"{_BASE}/{exam['id']}/attendees",
        json={"attendees": [{"name": "P1", "email": "p1@example.com"}, {"name": "P2", "email": "p2@example.com"}]},
        headers=auth_headers,
    )
    await client.post(f"{_BASE}/{exam['id']}/status", json={"status": "open"}, headers=auth_headers)
    tokens = await _tokens(db_session, exam["id"])

    async def take(email, picks_by_text):
        started = (await client.post(f"{_PUBLIC}/{tokens[email]}/start")).json()
        by_text = {q["text"]: q for q in started["questions"]}
        assert by_text["Pick the primes"]["allow_multiple"] is True
        assert by_text["Pick one colour"]["allow_multiple"] is False
        # The browser sees option indexes; map the wanted option texts back to them.
        answers = {}
        for text, wanted in picks_by_text.items():
            shown = {o["text"]: o["index"] for o in by_text[text]["options"]}
            answers[by_text[text]["id"]] = [shown[w] for w in wanted]
        await client.post(f"{_PUBLIC}/{tokens[email]}/submit", json={"answers": answers})
        attendee = (
            await db_session.execute(
                select(WorkshopExamAttendee).where(WorkshopExamAttendee.access_token == tokens[email])
            )
        ).scalar_one()
        await db_session.refresh(attendee)
        return attendee.score, attendee.total_marks

    assert await take("p1@example.com", {"Pick the primes": ["2", "3", "5"], "Pick one colour": ["Red"]}) == (4, 4)
    # Adding a wrong option earns nothing for that question.
    assert await take("p2@example.com", {"Pick the primes": ["2", "3", "4", "5"], "Pick one colour": ["Red"]}) == (1, 4)


async def test_question_validation_and_editing(client, auth_headers):
    exam = (await client.post(_BASE, json={"title": "Q checks"}, headers=auth_headers)).json()
    url = f"{_BASE}/{exam['id']}/questions"
    for bad in [
        {"text": "x", "options": ["a", "b"], "correct_indices": [0, 1]},  # two answers but single-answer
        {"text": "x", "options": ["a", "b"], "correct_indices": [2]},  # out of range
        {"text": "x", "options": ["a", "a"], "correct_indices": [0]},  # duplicate options
        {"text": "x", "options": ["a", " "], "correct_indices": [0]},  # blank option
        {"text": "x", "options": ["a", "b"], "correct_indices": []},  # no answer key
    ]:
        resp = await client.post(url, json={"questions": [bad]}, headers=auth_headers)
        assert resp.status_code == 422, bad

    created = (
        await client.post(
            url,
            json={"questions": [{"text": "Old", "options": ["a", "b"], "correct_indices": [0]}]},
            headers=auth_headers,
        )
    ).json()[0]
    edited = await client.put(
        f"{url}/{created['id']}",
        json={"text": "New", "options": ["a", "b", "c"], "correct_indices": [1, 2], "allow_multiple": True, "marks": 2},
        headers=auth_headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["correct_indices"] == [1, 2] and edited.json()["text"] == "New"


async def test_info_field_definitions_are_validated(client, auth_headers):
    for bad_fields in [
        [{"key": "name", "label": "Name"}],  # reserved
        [{"key": "Bad Key", "label": "x"}],
        [{"key": "dept", "label": "Dept", "type": "select", "options": ["only one"]}],
        [{"key": "a", "label": "A"}, {"key": "a", "label": "A again"}],
    ]:
        resp = await client.post(_BASE, json={"title": "Bad fields", "info_fields": bad_fields}, headers=auth_headers)
        assert resp.status_code == 422, bad_fields


# ---------------- admin-supplied certificate artwork ----------------


def _png(width=1600, height=1131, mode="RGB") -> bytes:
    import io

    from PIL import Image

    image = Image.new(mode, (width, height), (250, 245, 230) if mode == "RGB" else (250, 245, 230, 0))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def readable_pdfs(monkeypatch):
    """Let tests grep PDF content streams (reportlab compresses them by default)."""
    from reportlab import rl_config

    monkeypatch.setattr(rl_config, "pageCompression", 0)
    monkeypatch.setattr(rl_config, "useA85", 0)


async def _upload_template(client, auth_headers, exam_id, data=None, name="design.png", ctype="image/png"):
    return await client.put(
        f"{_BASE}/{exam_id}/certificate/template",
        files={"file": (name, data if data is not None else _png(), ctype)},
        headers=auth_headers,
    )


async def test_certificate_template_upload_validation(client, auth_headers):
    exam = (await client.post(_BASE, json={"title": "Design checks"}, headers=auth_headers)).json()
    assert exam["has_certificate_template"] is False

    for bad, label in [
        (b"", "empty"),
        (b"%PDF-1.4 not an image", "pdf/garbage"),
        (b"\x89PNG\r\n\x1a\n" + b"junk", "truncated png"),
        (_png() + b"\x00" * (8 * 1024 * 1024), "over 8 MB"),
    ]:
        resp = await _upload_template(client, auth_headers, exam["id"], data=bad)
        assert resp.status_code == 422, label

    ok = await _upload_template(client, auth_headers, exam["id"], data=_png(mode="RGBA"))
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["has_certificate_template"] is True
    assert body["certificate_layout"]["name_x"] == 0.5  # default layout is created with the upload

    # The stored image is what the admin sees back (re-encoded as JPEG).
    shown = await client.get(f"{_BASE}/{exam['id']}/certificate/template", headers=auth_headers)
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/jpeg"
    assert shown.content[:2] == b"\xff\xd8"

    removed = await client.delete(f"{_BASE}/{exam['id']}/certificate/template", headers=auth_headers)
    assert removed.json()["has_certificate_template"] is False
    assert (await client.get(f"{_BASE}/{exam['id']}/certificate/template", headers=auth_headers)).status_code == 422


async def test_certificate_layout_is_validated_and_saved(client, auth_headers):
    exam = (await client.post(_BASE, json={"title": "Layout"}, headers=auth_headers)).json()
    for bad in [{"name_x": 1.5}, {"font_size": 0.9}, {"color": "red"}, {"font": "comic_sans"}]:
        resp = await client.patch(f"{_BASE}/{exam['id']}", json={"certificate_layout": bad}, headers=auth_headers)
        assert resp.status_code == 422, bad
    layout = {
        "name_x": 0.42,
        "name_y": 0.61,
        "font_size": 0.08,
        "max_width": 0.5,
        "color": "#112233",
        "font": "serif_bold_italic",
        "show_verification": True,
    }
    saved = await client.patch(f"{_BASE}/{exam['id']}", json={"certificate_layout": layout}, headers=auth_headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["certificate_layout"] == layout


async def test_preview_prints_a_sample_name_on_the_uploaded_design(client, auth_headers, readable_pdfs):
    exam = (await client.post(_BASE, json={"title": "Preview"}, headers=auth_headers)).json()
    url = f"{_BASE}/{exam['id']}/certificate/preview"
    assert (await client.post(url, json={}, headers=auth_headers)).status_code == 422  # nothing uploaded yet

    await _upload_template(client, auth_headers, exam["id"], data=_png(1600, 1131))
    resp = await client.post(url, json={}, headers=auth_headers)
    assert resp.status_code == 200 and resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF") and b"Sample Student Name" in resp.content
    # Landscape artwork keeps its proportions on an A4-long-edge page.
    assert b"/MediaBox [ 0 0 842" in resp.content

    # An unsaved layout can be previewed without saving it.
    other = await client.post(url, json={"layout": {"name_x": 0.3, "font": "serif_bold"}}, headers=auth_headers)
    assert other.status_code == 200
    assert (await client.post(url, json={"layout": {"color": "nope"}}, headers=auth_headers)).status_code == 422


async def test_portrait_artwork_gets_a_portrait_page(client, auth_headers, readable_pdfs):
    exam = (await client.post(_BASE, json={"title": "Portrait"}, headers=auth_headers)).json()
    await _upload_template(client, auth_headers, exam["id"], data=_png(1131, 1600))
    resp = await client.post(f"{_BASE}/{exam['id']}/certificate/preview", json={}, headers=auth_headers)
    assert b"/MediaBox [ 0 0 595" in resp.content


def test_very_long_name_is_shrunk_to_fit_on_the_design():
    from modules.workshop_exams.certificate_template import (
        CertificateLayout,
        build_templated_certificate_pdf,
        normalize_template,
    )

    jpeg, w, h = normalize_template(_png())
    pdf = build_templated_certificate_pdf(
        template_jpeg=jpeg,
        width_px=w,
        height_px=h,
        layout=CertificateLayout(show_verification=True),
        attendee_name="Venkata Subrahmanya Sai Ramakrishna Chandrasekhar Iyer Narayanaswamy",
        certificate_number="WS-2026-ABCD1234",
        verify_url="https://erp.pentrix.in/verify-workshop-certificate/WS-2026-ABCD1234",
    )
    assert pdf.startswith(b"%PDF")


async def test_test_email_sends_a_sample_certificate(client, auth_headers, monkeypatch):
    from modules.workshop_exams import routes

    sent = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append((to, subject, attachments or []))
        return True

    monkeypatch.setattr(routes.email_service, "send", fake_send)
    exam = (await client.post(_BASE, json={"title": "Mail test"}, headers=auth_headers)).json()
    url = f"{_BASE}/{exam['id']}/certificate/test-email"

    assert (await client.post(url, json={"email": "me@example.com"}, headers=auth_headers)).status_code == 422
    await _upload_template(client, auth_headers, exam["id"])
    assert (await client.post(url, json={"email": "not-an-email"}, headers=auth_headers)).status_code == 422

    resp = await client.post(url, json={"email": "me@example.com"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    to, subject, attachments = sent[0]
    assert to == "me@example.com" and subject.startswith("[TEST]")
    assert attachments[0].mime_type == "application/pdf" and attachments[0].content.startswith(b"%PDF")

    async def failing_send(*a, **kw):
        return False

    monkeypatch.setattr(routes.email_service, "send", failing_send)
    failed = await client.post(url, json={"email": "me@example.com"}, headers=auth_headers)
    assert failed.status_code == 422 and "could not be sent" in failed.text


async def test_real_certificates_use_the_uploaded_design_with_each_students_name(
    client, db_session, auth_headers, monkeypatch, readable_pdfs
):
    from contextlib import asynccontextmanager

    from modules.workshop_exams import tasks

    sent = []

    async def fake_send(to, subject, text, html=None, attachments=None):
        sent.append((to, attachments or []))
        return True

    monkeypatch.setattr(tasks.email_service, "send", fake_send)

    @asynccontextmanager
    async def _same_session():
        yield db_session

    monkeypatch.setattr(tasks, "get_db_context", _same_session)

    exam = await _open_exam(client, auth_headers)
    assert (await _upload_template(client, auth_headers, exam["id"])).status_code == 200
    tokens = await _tokens(db_session, exam["id"])
    ids = {}
    for email in ("asha@example.com", "ravi@example.com"):
        started = (await client.post(f"{_PUBLIC}/{tokens[email]}/start")).json()
        await client.post(
            f"{_PUBLIC}/{tokens[email]}/submit", json={"answers": _correct_answers(started["questions"])}
        )
        ids[email] = (
            await db_session.execute(
                select(WorkshopExamAttendee.id).where(WorkshopExamAttendee.access_token == tokens[email])
            )
        ).scalar_one()
    await client.post(f"{_BASE}/{exam['id']}/certificates/send-now", headers=auth_headers)

    for email in ids:
        assert await tasks._send_certificate(ids[email]) is True

    by_recipient = {to: atts[0].content for to, atts in sent}
    assert b"Asha Rao" in by_recipient["asha@example.com"]
    assert b"Ravi Kumar" in by_recipient["ravi@example.com"]
    assert b"Asha Rao" not in by_recipient["ravi@example.com"]
    assert b"Certificate of Participation" not in by_recipient["asha@example.com"]  # not the generated design

    # Once certificates have gone out, the design is frozen.
    locked = await _upload_template(client, auth_headers, exam["id"])
    assert locked.status_code == 422 and "already been sent" in locked.text
