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
    assert alert.format == "image" and alert.template in ("statement", "solid", "split"), "an alert gets a high-contrast look"
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
    assert set(looks) == {"neon", "statement", "split", "solid", "editorial"}, "every look gets used"
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


def test_a_logo_with_its_own_dark_background_does_not_narrow_the_choice_of_looks():
    history: list[dict] = []
    looks = []
    for i in range(15):
        plan = planner.decide(f"Plain topic {i}", "", history, logo_on_dark=True)
        looks.append(plan.template)
        history.insert(0, {"format": plan.format, "template": plan.template})
    assert set(looks) == {"neon", "statement", "split", "solid", "editorial"}, looks


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


# ---------------- the looks ----------------


@pytest.mark.parametrize("template", ["neon", "statement", "split", "solid", "editorial"])
@pytest.mark.parametrize("variant", [0, 2, 4, 5, 9])
def test_every_look_is_readable_with_and_without_a_black_background_logo(template, variant):
    on_black = _logo((0, 0, 0, 255))
    for logo in (None, on_black):
        images, _ = draw(design={"template": template, "variant": variant}, content={"support_line": "One short sentence that gives the answer."}, logo=logo)
        validation = images[0].validation
        assert validation["ok"], (template, variant, validation["problems"])
        assert all(block["contrast_ok"] for block in images[0].metrics["blocks"]) if "blocks" in images[0].metrics else True


def test_the_looks_really_look_different_from_one_another():
    pictures = {t: pixels(draw(design={"template": t, "variant": 3})[0][0]).resize((1, 1), Image.BOX).getpixel((0, 0)) for t in ("neon", "statement", "split", "solid", "editorial")}
    names = list(pictures)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if {a, b} == {"neon", "statement"}:
                continue  # both are dark; they differ by the circuit pattern and light, checked below
            assert sum(abs(x - y) for x, y in zip(pictures[a], pictures[b])) > 20, (a, b, pictures)
    from PIL import ImageChops

    neon, statement = pixels(draw(design={"template": "neon", "variant": 3})[0][0]), pixels(draw(design={"template": "statement", "variant": 3})[0][0])
    assert ImageChops.difference(neon, statement).convert("L").point(lambda v: 255 if v > 24 else 0).getbbox() is not None


def test_a_black_background_logo_sits_on_a_black_badge_on_light_and_colour_looks():
    on_black = _logo((0, 0, 0, 255))
    for template in ("solid", "editorial"):
        image = pixels(draw(design={"template": template, "variant": 3}, logo=on_black)[0][0])
        # just inside the badge's top-left corner the colour is black, not the design's own colour
        assert max(image.getpixel((96 - 6, image.height - 96 - 128 + 4))) < 30, template


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
    assert post["format"] == "image" and "plan" not in post["generation"] and post["design"] == {"show_icon": True}
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


# ---------------- the quality pass: sentence case, a real cover, highlighted words, steps, progress ----------------


@pytest.mark.parametrize(
    "before, after",
    [
        ("Spot Phishing Fast: Check The Sender", "Spot phishing fast: check the sender"),
        ("What Is A SIEM, Really?", "What is a SIEM, really?"),
        ("Why Pentrix Teaches CVE Basics", "Why Pentrix teaches CVE basics"),
        ("Zero trust, explained in one line", "Zero trust, explained in one line"),
        ("Phishing vs spear phishing", "Phishing vs spear phishing"),
        ("SIEM", "SIEM"),
    ],
)
def test_title_case_headlines_are_turned_into_sentence_case_and_good_ones_are_left_alone(before, after):
    assert studio.sentence_case(before) == after


CONTENT = {
    "headline": "What is a SIEM, really?",
    "emphasis": "SIEM",
    "cta": "Save this if you are learning how SOCs work.",
    "slides": [
        {"heading": "Too many logs", "body": "No human can read them all."},
        {"heading": "Step 2: Collect and correlate", "body": "One place for every log."},
        {"heading": "The takeaway", "body": "A SIEM turns logs into a story."},
    ],
}


def test_a_framed_carousel_gets_a_cover_with_the_headline_and_a_closing_slide_and_an_unframed_one_does_not():
    plain = render.specs_for("carousel", CONTENT, {"template": "neon"}, "t", "SOC", BRAND)
    framed = render.specs_for("carousel", CONTENT, {"template": "neon", "carousel_frame": True}, "t", "SOC", BRAND)
    assert len(plain) == 3 and plain[0].headline == "Too many logs", "nothing changes unless the frame is asked for"
    assert len(framed) == 5
    assert framed[0].headline == "What is a SIEM, really?" and framed[0].subline == "Swipe to read" and framed[0].kicker
    assert framed[1].headline == "Too many logs" and framed[1].kicker == ""
    assert (framed[2].numeral, framed[2].headline) == ("02", "Collect and correlate")
    assert framed[-1].headline == "Save this for later." and "Follow @pentrix16" in framed[-1].subline and "learning how SOCs work" in framed[-1].subline
    assert [s.index for s in framed] == [1, 2, 3, 4, 5] and {s.total for s in framed} == {5}


def test_no_cover_is_added_when_the_first_slide_is_already_the_headline_or_there_is_no_room():
    same = {**CONTENT, "slides": [{"heading": "What is a SIEM, really", "body": "x"}, *CONTENT["slides"][1:]]}
    assert len(render.specs_for("carousel", same, {"carousel_frame": True}, "t", "SOC", BRAND)) == 4  # no cover, one closing slide
    full = {**CONTENT, "slides": [{"heading": f"Slide {i}", "body": "x"} for i in range(10)]}
    assert len(render.specs_for("carousel", full, {"carousel_frame": True}, "t", "SOC", BRAND)) == 10
    long = {**CONTENT, "headline": "A very long headline that would not fit as a cover on its own so it stays in the slides"}
    assert render.specs_for("carousel", long, {"carousel_frame": True}, "t", "SOC", BRAND)[0].headline == "Too many logs"


def test_every_image_of_a_framed_carousel_passes_the_design_checks_in_every_look():
    for template in ("neon", "statement", "split", "solid", "editorial"):
        images, _ = draw("carousel", content=CONTENT, design={"template": template, "carousel_frame": True, "variant": 2}, logo=_logo((0, 0, 0, 255)))
        assert len(images) == 5
        for image in images:
            assert image.validation["ok"], (template, image.slide, image.validation["problems"])


def test_highlighted_words_get_a_marker_and_the_marker_never_changes_the_text_checks():
    with_marker = draw(content={"emphasis": "SIEM"}, design={"template": "statement"})[0][0]
    without = draw(content={"emphasis": ""}, design={"template": "statement"})[0][0]
    from PIL import ImageChops

    box = ImageChops.difference(pixels(with_marker), pixels(without)).convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    assert box is not None, "the highlight is drawn"
    assert with_marker.validation["ok"]
    unknown = draw(content={"emphasis": "not in the headline"}, design={"template": "statement"})[0][0]
    assert pixels(unknown).tobytes() == pixels(without).tobytes(), "words that are not in the headline highlight nothing"


def test_the_highlight_is_part_of_what_the_artwork_shows_so_changing_it_makes_the_artwork_stale():
    a = render.current_fingerprint("image", {"headline": "What is a SIEM?", "emphasis": ""}, {}, "t", "SOC", BRAND)
    b = render.current_fingerprint("image", {"headline": "What is a SIEM?", "emphasis": "SIEM"}, {}, "t", "SOC", BRAND)
    assert a != b


@pytest.fixture
def fake_storage(monkeypatch):
    from packages.storage import client as storage_client

    class Fake:
        def __init__(self):
            self.objects = {}

        async def upload_bytes(self, key, data, content_type):
            self.objects[key] = data

        async def read_bytes(self, key):
            return self.objects[key]

        async def delete_object(self, key):
            self.objects.pop(key, None)

        def presigned_download_url(self, key):
            return f"https://files.test/{key}"

    fake = Fake()
    monkeypatch.setattr(storage_client, "_client", fake)
    return fake


async def test_a_generated_draft_arrives_with_its_artwork_in_sentence_case_with_a_valid_highlight(client, auth_headers, ai, fake_storage):
    ai({**DRAFT, "headline": "Spot Phishing Fast: Check The Sender", "emphasis": "check the sender", "thumbnail_text": "Spot Phishing Fast", "support_line": "The domain after the @ tells the truth."})
    post = await _generate(client, auth_headers, topic="Phishing vs spear phishing", format="image")
    assert post["content"]["headline"] == "Spot phishing fast: check the sender" and post["content"]["thumbnail_text"] == "Spot phishing fast"
    assert post["content"]["emphasis"] == "check the sender"
    files = post["artwork"]["files"]
    assert len(files) == 1 and files[0]["url"] and post["artwork"]["ok"] is True, "the picture is made at once"
    assert not any(w["code"] == "chk_no_artwork" for w in post["warnings"]), post["warnings"]


async def test_an_emphasis_that_is_not_in_the_headline_is_dropped_and_a_carousel_is_generated_framed(client, auth_headers, ai, fake_storage):
    ai({**DRAFT, "headline": "What is a SIEM, really?", "emphasis": "firewall", "slides": [*SLIDES, {"heading": "Step 4: Act", "body": "Respond."}], "support_line": ""})
    post = await _generate(client, auth_headers, topic="What is a SIEM?", format="carousel", auto=True)
    assert post["content"]["emphasis"] == "" and post["design"]["carousel_frame"] is True
    assert len(post["artwork"]["files"]) == 6, "cover + 4 slides + closing slide"


async def test_a_draft_is_kept_even_when_its_artwork_cannot_be_made(client, auth_headers, ai, monkeypatch):
    from packages.storage import client as storage_client

    class Broken:
        async def upload_bytes(self, *a, **k):
            raise RuntimeError("storage is down")

        async def delete_object(self, *a, **k):
            pass

    monkeypatch.setattr(storage_client, "_client", Broken())
    ai(DRAFT)
    post = await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    assert post["status"] == "draft" and not post["artwork"].get("files")


# ---------------- the professional layer: icons, pill label, swipe cue ----------------

from modules.social_media import icons  # noqa: E402


@pytest.mark.parametrize(
    "words, icon",
    [
        ("Spot phishing fast: check the sender", "mail"),
        ("Reset a password the safe way", "key"),
        ("What is a SIEM, really?", "logs"),
        ("Patch Tuesday: what to do first", "bolt"),
        ("How a port scan finds open doors", "network"),
        ("Why encryption protects your data", "lock"),
        ("Nothing recognisable here", "shield"),
    ],
)
def test_the_icon_is_chosen_from_the_posts_own_words(words, icon):
    assert icons.icon_for(words) == icon


def test_every_icon_draws_a_tile_with_the_icon_inside_it():
    for name in icons.ICONS:
        canvas = Image.new("RGB", (300, 300), (30, 30, 30))
        icons.draw_tile(canvas, name, 20, 20, 260, (154, 214, 43), (6, 180, 215))
        centre = canvas.crop((100, 100, 200, 200))
        colours = {px for px in centre.getdata() if px[1] > 120}
        assert colours, f"the {name} icon is drawn in the brand colours"
        assert canvas.getpixel((5, 5)) == (30, 30, 30), "nothing is drawn outside the tile"


@pytest.mark.parametrize("template", ["neon", "statement", "split", "solid", "editorial"])
def test_the_illustration_layer_adds_a_tile_and_keeps_every_check_green(template):
    content = {**CONTENT, "icon": "shield"}
    plain = draw("carousel", content=content, design={"template": template, "carousel_frame": True, "variant": 2})[0]
    rich = draw("carousel", content=content, design={"template": template, "carousel_frame": True, "show_icon": True, "variant": 2}, logo=_logo((0, 0, 0, 255)))[0]
    assert len(rich) == len(plain) == 5
    for image in rich:
        assert image.validation["ok"], (template, image.slide, image.validation["problems"])
    from PIL import ImageChops

    box = ImageChops.difference(pixels(rich[0]), pixels(plain[0])).convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    assert box is not None, "the cover carries the illustration"


def test_a_single_image_with_an_icon_never_lets_the_tile_cover_the_text_or_the_logo():
    for variant in range(0, 8):
        for template in ("neon", "solid", "split", "editorial"):
            image = draw(content={"headline": "Spot phishing fast: check the sender", "support_line": "The domain after the @ sign tells the truth."}, design={"template": template, "show_icon": True, "variant": variant}, logo=_logo((0, 0, 0, 255)))[0][0]
            assert image.validation["ok"], (template, variant, image.validation["problems"])


def test_the_pill_label_and_swipe_cue_belong_to_the_illustrated_look_only():
    plain = pixels(draw("carousel", content=CONTENT, design={"template": "statement", "carousel_frame": True})[0][0])
    rich = pixels(draw("carousel", content=CONTENT, design={"template": "statement", "carousel_frame": True, "show_icon": True})[0][0])
    assert plain.tobytes() != rich.tobytes()
    cover = render.specs_for("carousel", CONTENT, {"carousel_frame": True, "show_icon": True}, "t", "SOC", BRAND)
    assert cover[0].icon == "logs" and cover[0].subline == "", "no 'Swipe to read' line: the swipe cue is drawn in the footer"
    assert render.specs_for("carousel", CONTENT, {"carousel_frame": True}, "t", "SOC", BRAND)[0].icon == ""


async def test_generated_drafts_turn_the_illustration_on_and_keep_only_a_valid_ai_icon(client, auth_headers, ai, fake_storage):
    ai({**DRAFT, "icon": "Lock", "slides": []})
    post = await _generate(client, auth_headers, topic="Why encryption matters", format="image")
    assert post["design"]["show_icon"] is True and post["content"]["icon"] == "lock"
    ai({**DRAFT, "icon": "unicorn", "slides": []})
    other = await _generate(client, auth_headers, topic="Why encryption matters", format="image")
    assert other["content"]["icon"] == "", "an icon that is not in the library is ignored; one is chosen from the words"
    assert post["artwork"]["files"][0]["validation"]["ok"]


async def test_odd_decoration_fields_from_the_ai_never_cost_a_draft(client, auth_headers, ai, fake_storage):
    ai({**DRAFT, "emphasis": ["SIEM", "really"], "icon": ["lock"], "support_line": None, "slides": []})
    post = await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    assert post["status"] == "draft" and post["content"]["icon"] == "lock"
    assert post["content"]["support_line"] == ""


# ---------------- the cover: one big flat circle with the topic icon ----------------


@pytest.mark.parametrize("template", ["neon", "statement", "split", "solid", "editorial"])
def test_a_cover_has_one_big_flat_circle_bleeding_off_the_corner_and_inner_slides_do_not(template):
    content = {**CONTENT, "icon": "mail"}
    plain = pixels(draw("carousel", content=content, design={"template": template, "carousel_frame": True, "variant": 2})[0][0])
    rich = draw("carousel", content=content, design={"template": template, "carousel_frame": True, "show_icon": True, "variant": 2})
    cover, inner = pixels(rich[0][0]), pixels(rich[0][1])
    # a point deep inside the circle, away from the icon, text and footer, is a flat colour that the plain design does not have there
    point = (1000, 1050)
    assert cover.getpixel(point) != plain.getpixel(point) or template == "split", template
    assert inner.getpixel((1000, 1100)) == pixels(draw("carousel", content=content, design={"template": template, "carousel_frame": True, "variant": 2})[0][1]).getpixel((1000, 1100)), "an inner slide has no circle"
    assert rich[0][0].validation["ok"], rich[0][0].validation["problems"]


def test_the_headline_stays_above_the_circle_even_when_it_is_long():
    long = {"headline": "Why one reused password endangers all accounts", "emphasis": "reused password", "icon": "key", "support_line": "One leak should never mean many accounts lost, so use a unique password for each."}
    for template in ("neon", "solid", "editorial", "statement", "split"):
        image = draw(content=long, design={"template": template, "show_icon": True, "variant": 1}, logo=_logo((0, 0, 0, 255)))[0][0]
        assert image.validation["ok"], (template, image.validation["problems"])
        for block in image.metrics.get("blocks", []) if isinstance(image.metrics, dict) else []:
            assert block["role"] != "headline" or block["size_px"] >= render.MIN_HEADLINE_PX
