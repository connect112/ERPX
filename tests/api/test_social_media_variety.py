"""
Phase 7: every post should be a different post. The planner varies the format and the look from the topic and the recent posts and
says why; the brand-dark "neon" template changes its pattern, light and text position from post to post; a single image can carry
the answer, not only the question.
"""

import io
import json
from collections import Counter

import pytest
from PIL import Image

from modules.social_media import defaults, planner, render, studio
from packages.ai.client import AICompletionResult

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
BRAND = {**defaults.DEFAULT_BRAND, "handle": "@pentrix16"}
RULES = dict(defaults.DEFAULT_DESIGN_RULES)


def draw(post_format="image", content=None, design=None, title="What is a SIEM?", logo=None):
    content = {"headline": title, **(content or {})}
    images, fingerprint = render.render(post_format, content, {"template": "neon", **(design or {})}, title, "SOC", BRAND, RULES, logo, None)
    return images, fingerprint


def pixels(rendered):
    return Image.open(io.BytesIO(rendered.png)).convert("RGB")


# ---------------- the planner ----------------


@pytest.mark.parametrize(
    "topic, kind",
    [
        ("What is a SIEM?", "explainer"),
        ("How to read a packet capture", "explainer"),
        ("Phishing vs spear phishing", "explainer"),
        ("CVE-2026-1234 patch now", "alert"),
        ("A ransomware attack on a hospital", "alert"),
        ("How to become a SOC analyst: skills and certification", "career"),
        ("Our week at the lab", "general"),
    ],
)
def test_the_topic_decides_what_kind_of_post_it_is(topic, kind):
    assert planner.classify(topic) == kind


def test_an_explainer_is_a_carousel_and_an_alert_is_one_strong_image_when_there_is_no_history():
    explainer = planner.decide("What is a SIEM?", "", [])
    alert = planner.decide("CVE-2026-1234 is being patched", "", [])
    assert (explainer.format, explainer.topic_kind) == ("carousel", "explainer") and "swipe" not in explainer.reason and "carousel" in explainer.reason
    assert alert.format == "image" and alert.template in ("statement", "neon"), "an alert gets a high-contrast look"
    assert explainer.reason and alert.reason


def test_the_format_changes_after_two_of_the_same_in_a_row():
    two_carousels = [{"format": "carousel", "template": "neon"}, {"format": "carousel", "template": "statement"}]
    plan = planner.decide("What is a SIEM?", "", two_carousels)
    assert plan.format == "image" and "last two posts were already carousels" in plan.reason
    one_each = [{"format": "image", "template": "neon"}, {"format": "carousel", "template": "statement"}]
    assert planner.decide("What is a SIEM?", "", one_each).format == "carousel"
    two_images = [{"format": "image", "template": "neon"}, {"format": "image", "template": "statement"}]
    assert planner.decide("CVE-2026-1 alert", "", two_images).format == "carousel"


def test_the_look_is_never_the_same_as_the_last_post_and_rotates_through_all_of_them():
    history: list[dict] = []
    looks = []
    for i in range(12):
        plan = planner.decide(f"Topic number {i} about nothing in particular", "", history)
        looks.append(plan.template)
        history.insert(0, {"format": plan.format, "template": plan.template})
    assert all(a != b for a, b in zip(looks, looks[1:])), looks
    assert set(looks) == {"neon", "statement", "editorial"}, "every look gets used"
    counts = Counter(looks)
    assert max(counts.values()) - min(counts.values()) <= 1, counts


def test_a_long_run_of_posts_never_has_three_of_the_same_format_in_a_row_when_the_topic_allows_a_choice():
    history: list[dict] = []
    formats = []
    for i in range(14):
        plan = planner.decide("What is a SIEM? Part " + str(i), "", history)
        formats.append(plan.format)
        history.insert(0, {"format": plan.format, "template": plan.template})
    assert all(not (a == b == c) for a, b, c in zip(formats, formats[1:], formats[2:])), formats
    assert set(formats) == {"carousel", "image"}


def test_a_logo_with_its_own_dark_background_keeps_the_light_look_away():
    history: list[dict] = []
    for i in range(10):
        plan = planner.decide(f"Plain topic {i}", "", history, logo_on_dark=True)
        assert plan.template in ("neon", "statement"), plan
        history.insert(0, {"format": plan.format, "template": plan.template})


def test_the_same_history_always_gives_the_same_answer():
    history = [{"format": "image", "template": "statement"}]
    assert planner.decide("What is a SOC?", "", history) == planner.decide("What is a SOC?", "", history)


# ---------------- the neon look ----------------

TITLES = ["What is a SIEM?", "Phishing: spot it in 5 seconds", "Patch before you scroll.", "Port scanning, legally", "Why logs matter", "Zero trust in one sentence", "Passwords vs passphrases", "What a SOC analyst does"]


@pytest.mark.parametrize("title", TITLES)
def test_every_neon_post_passes_the_design_checks_with_readable_contrast(title):
    images, _ = draw(content={"support_line": "One place that collects security logs so analysts spot attacks sooner."}, title=title)
    result = images[0].validation
    assert result["ok"], result["problems"]
    assert result["min_contrast"] >= 4.5 and images[0].width == 1080 and images[0].height == 1350


def test_every_post_gets_its_own_pattern_and_the_same_post_always_looks_the_same():
    made = [pixels(draw(title=t)[0][0]) for t in TITLES]
    for i, a in enumerate(made):
        for b in made[i + 1 :]:
            assert list(a.crop((540, 0, 1080, 300)).getdata()) != list(b.crop((540, 0, 1080, 300)).getdata()), "two posts share the same circuit pattern"
    anchors = {draw(title=t)[0][0].metrics["dhash"] for t in TITLES}
    assert len(anchors) == len(TITLES), "layouts repeat"
    again = draw(title=TITLES[0])[0][0]
    assert again.sha256 == draw(title=TITLES[0])[0][0].sha256, "drawing is deterministic"


def test_an_explicit_variant_changes_the_look_and_the_fingerprint():
    plain, fp_plain = draw()
    other, fp_other = draw(design={"variant": 7})
    third, fp_third = draw(design={"variant": 8})
    assert plain[0].sha256 != other[0].sha256 != third[0].sha256
    assert len({fp_plain, fp_other, fp_third}) == 3, "a changed look must invalidate an earlier approval"


def test_carousel_slides_share_one_pattern_and_start_their_headings_at_the_same_height():
    slides = [{"heading": "What is a SOC?", "body": "A team that watches for attacks."}, {"heading": "1. Collect", "body": "Logs flow into one place."}, {"heading": "2. Detect", "body": "Rules spot patterns that mean trouble."}, {"heading": "Save this", "body": "Next: SIEM."}]
    images, _ = draw("carousel", {"slides": slides}, title="What is a SOC?")
    assert all(i.validation["ok"] for i in images)
    tops = [pixels(i).crop((540, 0, 1080, 300)).tobytes() for i in images]
    assert len(set(tops)) == 1, "every slide of a post has the same circuit pattern"
    first_rows = []
    for image in images[1:]:
        rows = [y for y in range(300, 1000) if any(p[0] > 200 and p[1] > 200 and p[2] > 200 for p in list(pixels(image).crop((96, y, 700, y + 1)).getdata())[::6])]
        first_rows.append(rows[0])
    assert max(first_rows) - min(first_rows) <= 3, first_rows


def test_the_answer_line_is_drawn_under_the_headline_and_can_be_turned_off():
    with_line = draw(content={"support_line": "One place that collects security logs."})[0][0]
    assert with_line.validation["rendered_text"]["subline"] == "One place that collects security logs."
    without = draw()[0][0]
    assert without.validation["rendered_text"]["subline"] == ""
    off = draw(content={"support_line": "One place that collects security logs."}, design={"subline": ""})[0][0]
    assert off.validation["rendered_text"]["subline"] == "", "an empty line in the design switches it off"
    override = draw(content={"support_line": "From the studio."}, design={"subline": "Typed by a person."})[0][0]
    assert override.validation["rendered_text"]["subline"] == "Typed by a person."
    assert with_line.sha256 != without.sha256


def test_headline_and_answer_line_together_still_obey_the_text_limit():
    images, _ = draw(content={"support_line": "x" * 160}, title="What is a SIEM?")
    assert not images[0].validation["ok"] and "characters of text" in " ".join(images[0].validation["problems"])
    long_headline, _ = draw(content={"support_line": "A short answer."}, title="x" * 95)
    assert "the design rules allow 90 for the cover" in " ".join(long_headline[0].validation["problems"])


def test_the_palette_accepts_the_second_brand_colour_and_older_settings_without_it():
    assert render.palette_of(BRAND["colors"]).accent2 == (6, 180, 215)
    old = {k: v for k, v in BRAND["colors"].items() if k != "accent2"}
    assert render.palette_of(old).accent2 == (6, 180, 215), "settings saved before the second colour existed still work"


# ---------------- the logo ----------------


def _logo(background, size=(300, 200)):
    image = Image.new("RGBA", size, background)
    for x in range(100, 200):
        for y in range(60, 140):
            image.putpixel((x, y), (120, 220, 60, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_a_logo_with_its_own_black_background_is_recognised_and_sits_on_a_dark_design_without_a_white_box():
    on_black, transparent, on_white = _logo((0, 0, 0, 255)), _logo((0, 0, 0, 0)), _logo((250, 250, 250, 255))
    assert render._logo_has_dark_background(render.load_image(on_black, "logo").convert("RGBA")) is True
    assert render._logo_has_dark_background(render.load_image(transparent, "logo").convert("RGBA")) is False
    assert render._logo_has_dark_background(render.load_image(on_white, "logo").convert("RGBA")) is False

    def corner_pixel(logo_bytes):
        rendered = draw(logo=logo_bytes)[0][0]
        placed = rendered.metrics["logo"]
        assert placed == "bottom_left"
        image = pixels(rendered)
        return image.getpixel((96 - 10, image.height - 96 - 112 - 2 + 10)), image

    chip_free, _ = corner_pixel(on_black)
    chipped, _ = corner_pixel(transparent)
    assert max(chip_free) < 60, "no white chip behind a logo that has its own dark background"
    assert chipped == (255, 255, 255), "a transparent logo still gets the light chip on a dark design"


def test_the_black_of_such_a_logo_blends_into_the_design_instead_of_showing_as_a_box():
    from PIL import ImageChops

    with_logo = pixels(draw(logo=_logo((0, 0, 0, 255)))[0][0])
    without = pixels(draw()[0][0])
    box = ImageChops.difference(with_logo, without).convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    assert box is not None, "the logo is drawn"
    # the whole logo image is 225 x 150 here; only its bright mark (about 75 x 60) may differ from the plain design
    assert box[2] - box[0] < 120 and box[3] - box[1] < 100, f"the logo's black background shows: {box}"


# ---------------- through the API ----------------

DRAFT = {
    "hooks": ["Ever wondered what a SIEM does?"],
    "headline": "What is a SIEM?",
    "caption": "A SIEM collects and correlates security logs so analysts can spot attacks early.",
    "cta": "Save this for later.",
    "hashtags": ["SIEM", "SOC"],
    "thumbnail_text": "What is a SIEM?",
    "support_line": "One place that collects security logs so analysts spot attacks sooner.",
    "visual_direction": "Plain background, one bold headline.",
    "alt_text": "Text reading: What is a SIEM?",
    "slides": [],
    "objective": "Teach beginners what a SIEM is.",
    "claims": [],
}
SLIDES = [{"heading": "What is a SIEM?", "body": "A tool that gathers security logs."}, {"heading": "1. Collect", "body": "Logs flow in."}, {"heading": "2. Save this", "body": "Next: detection."}]


class FakeAI:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    async def complete(self, system_prompt, messages, max_tokens=None, temperature=0.7, timeout=None):
        self.calls.append({"system": system_prompt, "message": messages[0].content})
        return AICompletionResult(text=json.dumps(self.answers.pop(0) if self.answers else DRAFT), model="fake-model", input_tokens=1500, output_tokens=700)


@pytest.fixture
def ai(monkeypatch):
    def install(*answers):
        fake = FakeAI(answers)
        monkeypatch.setattr(studio, "get_ai_client", lambda: fake)
        return fake

    return install


async def _generate(client, headers, **body):
    response = await client.post(f"{_BASE}/studio/generate", json={"pillar": "soc", **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_the_plan_is_shown_before_anything_is_created_and_needs_only_view(client, auth_headers, staff_headers, rbac_seeded):
    plan = await client.post(f"{_BASE}/studio/plan", json={"topic": "What is a SIEM?"}, headers=auth_headers)
    assert plan.status_code == 200
    data = plan.json()
    assert data["format"] == "carousel" and data["topic_kind"] == "explainer" and data["reason"] and data["template"] in ("neon", "statement", "editorial")
    assert (await client.get(f"{_BASE}/posts", headers=auth_headers)).json()["total"] == 0, "planning creates nothing"
    assert (await client.post(f"{_BASE}/studio/plan", json={"topic": "x"}, headers=auth_headers)).status_code == 422
    assert (await client.post(f"{_BASE}/studio/plan", json={"topic": "What is a SIEM?"})).status_code == 401


async def test_auto_chooses_the_format_and_look_records_why_and_the_next_post_differs(client, auth_headers, ai):
    ai({**DRAFT, "slides": SLIDES, "support_line": ""}, DRAFT)
    first = await _generate(client, auth_headers, topic="What is a SIEM?", format="image", auto=True)
    assert first["format"] == "carousel", "the planner overrides the format that was sent"
    plan = first["generation"]["plan"]
    assert plan["format"] == "carousel" and plan["reason"] and first["design"]["template"] == plan["template"]
    assert len(first["content"]["slides"]) == 3 and first["content"]["support_line"] == "", "a carousel carries no answer line"
    second = await _generate(client, auth_headers, topic="Zero trust in simple words", format="carousel", auto=True)
    assert second["design"]["template"] != first["design"]["template"], "the next post doesn't repeat the look"
    assert second["generation"]["plan"]["recent_templates"][0] == first["design"]["template"]


async def test_without_auto_nothing_changes(client, auth_headers, ai):
    ai(DRAFT)
    post = await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    assert post["format"] == "image" and "plan" not in post["generation"] and post["design"] == {}
    assert post["content"]["support_line"] == DRAFT["support_line"], "a single image gets the answer line the AI wrote"


async def test_an_answer_line_that_would_break_the_text_limit_is_left_out_not_failed(client, auth_headers, ai):
    ai({**DRAFT, "support_line": "x" * 200})
    post = await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    assert post["content"]["support_line"] == "" and post["status"] == "draft"


async def test_the_ai_is_asked_for_the_answer_line_and_not_to_repeat_the_call_to_action(client, auth_headers, ai):
    fake = ai(DRAFT)
    await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    system = fake.calls[0]["system"]
    assert "support_line" in system and "GIVES the answer" in system and "Do not repeat the call to action inside the caption" in system


async def test_editing_a_post_keeps_its_answer_line_and_the_neon_template_can_be_chosen(client, auth_headers, ai):
    ai(DRAFT)
    post = await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    edited = await client.patch(f"{_BASE}/posts/{post['id']}", json={"content": {**post["content"], "caption": "A new caption."}}, headers=auth_headers)
    assert edited.status_code == 200 and edited.json()["content"]["support_line"] == DRAFT["support_line"]
    design = await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "neon", "variant": 12}, headers=auth_headers)
    assert design.status_code == 200 and design.json()["design"]["template"] == "neon" and design.json()["design"]["variant"] == 12
    assert (await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "plaid"}, headers=auth_headers)).status_code == 422
