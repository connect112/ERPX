"""
Phase 1 of the composition engine: the art-direction brief, the precedence rules, the six compositions and the engine flag.

What must hold: engine v1 (every post made so far) draws exactly what it always drew; the brand's restrictions beat theme
preferences; a composition is only used when the topic suits it; text never overlaps a composition's artwork; a poor AI brief never
costs a draft; and `visual_direction` now says what the picture is and is read by the renderer through the brief.
"""

import io
import json

import pytest
from PIL import Image

from app.core.config import settings as app_settings
from modules.social_media import art_direction as ad
from modules.social_media import compose, defaults, planner, render, studio
from packages.ai.client import AICompletionResult

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
BRAND = {**defaults.DEFAULT_BRAND, "handle": "@pentrix16"}
RULES = dict(defaults.DEFAULT_DESIGN_RULES)
TEMPLATES = ("neon", "statement", "split", "solid", "editorial")


def S(heading, body="Short body."):
    return {"heading": heading, "body": body}


STEPS = [S("Step 1: Check the sender's address"), S("Step 2: Hover before you click"), S("Step 3: Spot the urgency trick"), S("Step 4: Verify another way"), S("Ten seconds can save you")]


def logo_on_black():
    image = Image.new("RGBA", (300, 200), (0, 0, 0, 255))
    for x in range(100, 200):
        for y in range(60, 140):
            image.putpixel((x, y), (120, 220, 60, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def specs(post_format, content, design):
    return render.specs_for(post_format, content, {"template": "statement", "show_icon": True, **design}, "t", "SOC", BRAND)


def draw(post_format, content, design, logo=None):
    images, fingerprint = render.render(post_format, content, {"template": "statement", "show_icon": True, **design}, "t", "SOC", BRAND, RULES, logo, None)
    return images, fingerprint


def pixels(rendered):
    return Image.open(io.BytesIO(rendered.png)).convert("RGB")


# ---------------- the brief ----------------


def test_a_brief_accepts_whatever_the_ai_sends_and_keeps_only_what_is_usable():
    brief = ad.lenient({"composition": "FLOW", "items": ["a", "b", None, "c", "d", "e"], "focus": ["10", "sec"], "imagery": "photo", "concept": ["Shows", "a funnel"], "metaphor": 5})
    assert brief.composition == "flow" and brief.items == ["a", "b", "c", "d", "e"], "at most five items, empty ones dropped"
    assert brief.focus == "10 sec" and brief.imagery == "none" and brief.concept == "Shows a funnel" and brief.metaphor == ""
    for junk in (None, "text", 5, [], {"composition": "carousel"}, {"items": "x"}):
        assert ad.lenient(junk).composition == "" and ad.lenient(junk).imagery == "none"


def test_the_brief_is_completed_from_the_posts_own_words_when_the_ai_sent_none():
    brief = ad.finalise(None, "The 10-second check before you click", STEPS, support_line="A quick habit that stops most scams.", icon_hint="mail")
    assert brief.concept == "A quick habit that stops most scams." and brief.metaphor == "mail"
    assert brief.focus == "10 second check" and brief.items[:2] == ["Check the sender's address", "Hover before you click"]
    assert brief.imagery == "none", "Phase 1 draws only with code"
    assert brief.composition in ad.COMPOSITIONS


# ---------------- which composition suits the topic ----------------


@pytest.mark.parametrize(
    "headline, slides, composition, ok",
    [
        ("Phishing vs spear phishing", [], "compare", True),
        ("Phishing or spear phishing", [], "compare", False),
        ("The 10-second check before you click", [], "stat", True),
        ("Stay safe online", [], "stat", False),
        ("Stay safe online", STEPS, "stat", True),  # four numbered steps: the count is real
        ("Stay safe online", STEPS[:2], "checklist", False),
        ("Stay safe online", STEPS, "checklist", True),
        ("How a phishing attack unfolds", STEPS, "flow", True),
        ("Stay safe online", [S("One"), S("Two"), S("Three")], "flow", False),  # no sequence in the words
        ("What is a SIEM?", [], "question", True),
        ("A SIEM explained", [], "question", False),
        ("Anything at all", [], "poster", True),
        ("Anything at all", [], "carousel", False),
    ],
)
def test_a_composition_is_only_possible_when_the_topic_suits_it(headline, slides, composition, ok):
    assert ad.suitable(composition, headline, slides) is ok


def test_the_ai_suggestion_wins_among_the_possible_layouts_but_never_repeats_the_last_one():
    brief = ad.ArtBrief(composition="checklist")
    assert ad.choose("Stay safe online", STEPS, brief) == "checklist"
    assert ad.choose("Stay safe online", STEPS, brief, recent=["checklist"]) != "checklist", "not twice in a row"
    assert ad.choose("Stay safe online", [], ad.ArtBrief(composition="checklist")) == "poster", "no steps: not possible, so the poster"
    assert ad.choose("Phishing vs spear phishing", [], ad.ArtBrief(composition="flow")) == "compare", "an impossible suggestion gives way to what suits"


def test_the_layouts_rotate_through_everything_that_suits_the_topic():
    seen = []
    recent: list[str] = []
    for _ in range(8):
        pick = ad.choose("The 10-second check before you click", STEPS, None, recent)
        seen.append(pick)
        recent.insert(0, pick)
    assert all(a != b for a, b in zip(seen, seen[1:])), seen
    assert {"stat", "checklist", "flow", "poster"} <= set(seen), seen


# ---------------- the brand's restrictions come first ----------------


def test_a_theme_the_brand_forbids_is_never_chosen_automatically_but_can_still_be_picked_by_hand():
    banned = {"forbidden_visuals": ["neon or glow effects", "circuit-board or matrix patterns"]}
    assert ad.theme_allowed("neon", banned) is False and ad.theme_allowed("neon", {"forbidden_visuals": []}) is True
    assert ad.theme_allowed("solid", banned) is True and ad.theme_allowed("neon", None) is True
    looks = set()
    history: list[dict] = []
    for i in range(20):
        plan = planner.decide(f"Plain topic {i}", "", history, rules=banned)
        looks.add(plan.template)
        history.insert(0, {"format": plan.format, "template": plan.template})
    assert "neon" not in looks and {"statement", "split", "solid", "editorial"} <= looks
    # by hand: the renderer still draws it
    images, _ = draw("image", {"headline": "Stay safe online", "icon": "shield"}, {"template": "neon"})
    assert images[0].validation["ok"]


def test_an_alert_stays_high_contrast_even_when_a_theme_is_removed():
    plan = planner.decide("A critical patch for a zero-day exploit", "", [], rules={"forbidden_visuals": ["neon"]})
    assert plan.template in ("statement", "solid", "split")


# ---------------- engine v1 is untouched ----------------


def test_engine_v1_draws_exactly_what_it_always_drew_even_if_a_brief_is_present():
    plain = {"headline": "Phishing vs spear phishing", "support_line": "One casts a wide net.", "icon": "mail"}
    briefed = {**plain, "art_direction": {"composition": "compare", "items": ["a", "b", "c"], "focus": "3"}}
    for template in TEMPLATES:
        a, fa = draw("image", plain, {"template": template, "variant": 3})
        b, fb = draw("image", briefed, {"template": template, "variant": 3})
        assert pixels(a[0]).tobytes() == pixels(b[0]).tobytes(), template
        assert fa == fb, "the fingerprint of an artwork made before engine v2 does not change"
    c, fc = draw("image", briefed, {"template": "statement", "variant": 3, "engine": "v2"})
    assert fc != fa and pixels(c[0]).tobytes() != pixels(a[0]).tobytes()


def test_the_fingerprint_follows_the_composition_so_changing_it_makes_the_artwork_stale():
    content = {"headline": "Stay safe online", "slides": STEPS, "icon": "shield"}
    design = {"template": "statement", "show_icon": True, "engine": "v2", "carousel_frame": True}
    one = render.current_fingerprint("carousel", {**content, "art_direction": {"composition": "checklist"}}, design, "t", "SOC", BRAND)
    two = render.current_fingerprint("carousel", {**content, "art_direction": {"composition": "flow"}}, design, "t", "SOC", BRAND)
    assert one and two and one != two


# ---------------- the compositions ----------------

CASES = [
    ("carousel", {"headline": "The 10-second check before you click", "icon": "mail", "cta": "Save this.", "slides": STEPS}, "checklist"),
    ("carousel", {"headline": "How a phishing attack unfolds", "icon": "mail", "cta": "Save this.", "slides": STEPS}, "flow"),
    ("carousel", {"headline": "Four steps to spot a phishing email", "icon": "mail", "cta": "Save this.", "slides": STEPS}, "stat"),
    ("image", {"headline": "Phishing vs spear phishing", "icon": "mail", "support_line": "One casts a wide net; the other targets you by name."}, "compare"),
    ("image", {"headline": "What is a SIEM, really?", "icon": "logs", "support_line": "It collects logs in one place so analysts spot attacks sooner."}, "question"),
]


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("post_format, content, composition", CASES)
def test_every_composition_is_valid_in_every_theme_with_and_without_the_logo(post_format, content, composition, template):
    design = {"template": template, "engine": "v2", "carousel_frame": post_format == "carousel", "variant": 2}
    brief = {"art_direction": {"composition": composition}}
    chosen = specs(post_format, {**content, **brief}, design)[0]
    assert chosen.composition == composition, "the topic suits it, so it is the one drawn"
    for logo in (None, logo_on_black()):
        images, _ = draw(post_format, {**content, **brief}, design, logo)
        assert images[0].validation["ok"], (composition, template, images[0].validation["problems"])


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("post_format, content, composition", CASES)
def test_the_headline_never_overlaps_a_compositions_artwork_the_logo_or_the_footer(post_format, content, composition, template):
    design = {"template": template, "engine": "v2", "carousel_frame": post_format == "carousel", "variant": 2, "show_icon": True}
    spec = render.specs_for(post_format, {**content, "art_direction": {"composition": composition}}, design, "t", "SOC", BRAND)[0]
    palette = render.palette_of(BRAND["colors"])
    logo = render._trimmed(render.load_image(logo_on_black(), "logo").convert("RGBA"))
    _, ctx, placed = render._draw_image(spec, logo, None, palette, RULES, (1080, 1350), post_format, True)
    text = [b["box"] for b in ctx.blocks if b["role"] in ("headline", "subline")]
    art = [b["box"] for b in ctx.blocks if b["role"] == "art"]
    assert text
    if composition == "question":
        assert not art and all(t[3] <= 640 for t in text), "the question mark has no words; the headline stays above it"
    else:
        assert art, "a composition draws words of its own"

    def hit(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    for t in text:
        assert not any(hit(t, a) for a in art), (composition, template, t, art)
        assert placed is None or t[3] <= placed["y"], "the text stops above the logo"


def test_a_composition_that_cannot_fit_its_words_gives_way_to_the_poster_instead_of_failing():
    spec = specs("carousel", {"headline": "The 10-second check before you click", "icon": "mail", "cta": "x", "slides": STEPS}, {"engine": "v2", "carousel_frame": True})[0]
    spec.composition, spec.items = "checklist", tuple("An item with a really long label that cannot possibly fit on one line of the list " * 3 for _ in range(4))
    palette = render.palette_of(BRAND["colors"])
    image, ctx, _ = render._draw_image(spec, None, None, palette, RULES, (1080, 1350), "carousel", True)
    assert image.size == (1080, 1350) and not [b for b in ctx.blocks if b["role"] == "art"], "no half-drawn composition"


def test_the_compositions_look_different_from_each_other_not_just_in_colour():
    shots = {}
    for post_format, content, composition in CASES:
        images, _ = draw(post_format, {**content, "art_direction": {"composition": composition}}, {"template": "statement", "engine": "v2", "carousel_frame": post_format == "carousel", "variant": 2})
        shots[composition] = pixels(images[0]).convert("L").resize((24, 30))
    names = list(shots)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            diff = sum(abs(x - y) for x, y in zip(shots[a].tobytes(), shots[b].tobytes())) / (24 * 30)
            assert diff > 4, f"{a} and {b} are too alike ({diff:.1f})"


# ---------------- through the API: the flag, the brief and visual_direction ----------------

DRAFT = {
    "hooks": ["Ever wondered how phishing works?"],
    "headline": "Phishing vs spear phishing",
    "caption": "One casts a wide net; the other is aimed at you.",
    "cta": "Save this for later.",
    "hashtags": ["phishing", "emailsecurity"],
    "thumbnail_text": "Phishing vs spear phishing",
    "support_line": "One casts a wide net; the other targets you by name.",
    "visual_direction": "an old free-text note",
    "alt_text": "Text: Phishing vs spear phishing",
    "slides": [],
    "objective": "Explain the difference.",
    "claims": [],
    "emphasis": "spear phishing",
    "icon": "mail",
}


class FakeAI:
    def __init__(self, answer):
        self.answer, self.systems = answer, []

    async def complete(self, system_prompt, messages, max_tokens=None, temperature=0.7, timeout=None):
        self.systems.append(system_prompt)
        return AICompletionResult(text=json.dumps(self.answer), model="fake-model", input_tokens=1500, output_tokens=700)


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


async def _generate(client, headers, **body):
    response = await client.post(f"{_BASE}/studio/generate", json={"pillar": "soc", **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_with_the_flag_off_nothing_changes_for_new_drafts(client, auth_headers, monkeypatch, fake_storage):
    assert app_settings.SOCIAL_DESIGN_ENGINE_V2 is False, "off by default"
    ai = FakeAI({**DRAFT, "art_direction": {"composition": "compare"}})
    monkeypatch.setattr(studio, "get_ai_client", lambda: ai)
    post = await _generate(client, auth_headers, topic="Phishing vs spear phishing", format="image")
    assert "art_direction" not in ai.systems[0] and post["design"].get("engine", "v1") == "v1"
    assert post["content"]["art_direction"] is None and post["content"]["visual_direction"] == "an old free-text note"
    assert post["artwork"]["ok"] is True


async def test_with_the_flag_on_the_brief_is_stored_drives_the_picture_and_fills_visual_direction(client, auth_headers, monkeypatch, fake_storage):
    monkeypatch.setattr(app_settings, "SOCIAL_DESIGN_ENGINE_V2", True)
    brief = {"concept": "Two panels that set a wide net against a targeted lure.", "composition": "compare", "metaphor": "net vs hook", "items": [], "focus": ""}
    ai = FakeAI({**DRAFT, "art_direction": brief})
    monkeypatch.setattr(studio, "get_ai_client", lambda: ai)
    post = await _generate(client, auth_headers, topic="Phishing vs spear phishing", format="image")
    assert "art_direction" in ai.systems[0] and post["design"]["engine"] == "v2"
    stored = post["content"]["art_direction"]
    assert stored["composition"] == "compare" and stored["imagery"] == "none"
    assert post["content"]["visual_direction"] == brief["concept"], "visual_direction now says what the picture is"
    metrics = post["artwork"]["files"][0]["metrics"]
    assert post["artwork"]["ok"] is True and metrics["template"]


async def test_a_poor_brief_never_costs_a_draft_and_the_next_post_uses_a_different_composition(client, auth_headers, monkeypatch, fake_storage):
    monkeypatch.setattr(app_settings, "SOCIAL_DESIGN_ENGINE_V2", True)
    ai = FakeAI({**DRAFT, "art_direction": ["not", "an", "object"]})
    monkeypatch.setattr(studio, "get_ai_client", lambda: ai)
    first = await _generate(client, auth_headers, topic="Phishing vs spear phishing", format="image")
    assert first["status"] == "draft" and first["content"]["art_direction"]["composition"] == "compare", "completed from the words: it is a 'vs' headline"
    ai.answer = {**DRAFT, "headline": "What is a SIEM?", "thumbnail_text": "What is a SIEM?", "art_direction": {"composition": "compare"}}
    second = await _generate(client, auth_headers, topic="What is a SIEM?", format="image")
    assert second["content"]["art_direction"]["composition"] == "question", "compare does not suit this headline; a question does"


async def test_editing_the_brief_keeps_it_and_makes_the_artwork_stale_until_it_is_drawn_again(client, auth_headers, monkeypatch, fake_storage):
    monkeypatch.setattr(app_settings, "SOCIAL_DESIGN_ENGINE_V2", True)
    monkeypatch.setattr(studio, "get_ai_client", lambda: FakeAI({**DRAFT, "art_direction": {"composition": "compare"}}))
    post = await _generate(client, auth_headers, topic="Phishing vs spear phishing", format="image")
    content = {**post["content"], "art_direction": {**post["content"]["art_direction"], "composition": "poster"}}
    updated = await client.patch(f"{_BASE}/posts/{post['id']}", json={"content": content}, headers=auth_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"]["art_direction"]["composition"] == "poster"
    checked = await client.post(f"{_BASE}/posts/{post['id']}/check", headers=auth_headers)
    assert checked.status_code == 200, checked.text
    stale = [w for w in checked.json()["warnings"] if w["code"] == "chk_artwork_stale"]
    assert stale and stale[0]["severity"] == "blocking", "the picture no longer matches the brief, and that blocks approval until it is drawn again"


@pytest.mark.parametrize(
    "headline, figure, label, stat_possible",
    [
        ("The 10-second check before you click", "10", "second check", True),
        ("5 habits that stop most account takeovers", "5", "habits", False),  # the headline already starts with it
        ("Learn 3 tools in a week", "3", "tools", True),
        ("Stay safe online", "", "", False),
    ],
)
def test_a_stat_shows_a_number_the_post_really_states_with_a_clean_label_and_never_repeats_the_headline(headline, figure, label, stat_possible):
    assert ad.figure_of(headline, []) == (figure, label)
    assert ad.suitable("stat", headline, []) is stat_possible
