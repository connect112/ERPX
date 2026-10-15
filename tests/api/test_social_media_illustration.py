"""
Phase 2 of the composition engine: one AI illustration per post, on request, inside a hard server-side image budget.

What must hold: nothing is generated unless the provider is configured and a person asks; the same concept never costs twice; at most
SOCIAL_IMAGE_MAX_ASSETS images and SOCIAL_IMAGE_BUDGET_USD dollars in total, counting failed and retried attempts; the API key is never
logged or returned; the picture is labelled synthetic and drawn in the brand's two tones; attaching one withdraws an approval; and
nothing in this workflow approves, schedules or publishes.
"""

import io
import json
import uuid

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.core.config import settings as app_settings
from app.core.exceptions import ServiceUnavailableError
from app.db.session import engine
from modules.social_media import art_direction as ad
from modules.social_media import compose, defaults, image_budget, image_provider, render, studio
from modules.social_media.models import AIUsage, SocialAsset
from packages.ai.client import AICompletionResult

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
KEY = "sk-test-SECRET-123456789"
BRAND = {**defaults.DEFAULT_BRAND, "handle": "@pentrix16"}
RULES = dict(defaults.DEFAULT_DESIGN_RULES)

DRAFT = {
    "hooks": ["What is a SIEM?"],
    "headline": "What is a SIEM, really?",
    "caption": "A SIEM collects security logs in one place.",
    "cta": "Save this for later.",
    "hashtags": ["siem", "soc"],
    "thumbnail_text": "What is a SIEM, really?",
    "support_line": "It collects logs in one place so analysts spot attacks sooner.",
    "visual_direction": "",
    "alt_text": "Text: What is a SIEM, really?",
    "slides": [],
    "objective": "Explain a SIEM.",
    "claims": [],
    "emphasis": "SIEM",
    "icon": "logs",
    "art_direction": {"concept": "Logs from many systems flowing into one place.", "metaphor": "streams joining a river", "composition": "poster"},
}


def art_png(size=(1024, 1024), seed=1) -> bytes:
    """A stand-in for a generated picture: abstract shapes in arbitrary colours (the engine must map them to the brand's tones)."""
    image = Image.new("RGB", size, (200 + seed, 40, 90))
    for i in range(6):
        for x in range(i * 120, i * 120 + 160):
            for y in range(100 + i * 90, 260 + i * 90):
                if x < size[0] and y < size[1]:
                    image.putpixel((x, y), (30 + i * 30, 180 - i * 20, 60 + seed))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class FakeAI:
    def __init__(self, answer):
        self.answer = answer

    async def complete(self, system_prompt, messages, max_tokens=None, temperature=0.7, timeout=None):
        return AICompletionResult(text=json.dumps(self.answer), model="fake-model", input_tokens=1500, output_tokens=700)


@pytest.fixture
def fake_storage(monkeypatch):
    from packages.storage import client as storage_client

    class Fake:
        def __init__(self):
            self.objects = {}

        async def upload_bytes(self, key, data, content_type):
            self.objects[key] = data

        async def read_bytes(self, key, max_bytes=0):
            return self.objects[key]

        async def delete_object(self, key):
            self.objects.pop(key, None)

        def presigned_download_url(self, key):
            return f"https://files.test/{key}"

    fake = Fake()
    monkeypatch.setattr(storage_client, "_client", fake)
    return fake


@pytest.fixture
def engine_v2(monkeypatch):
    monkeypatch.setattr(app_settings, "SOCIAL_DESIGN_ENGINE_V2", True)


@pytest.fixture
def provider(monkeypatch):
    """A configured image provider whose calls are recorded; each call returns a different stand-in picture."""
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_API_KEY", KEY)
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_API_BASE_URL", "https://images.test")
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_MODEL", "image-model")
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_QUALITY", "medium")
    calls = []

    async def fake(prompt, size=image_provider.SIZE):
        calls.append({"prompt": prompt, "size": size})
        return art_png(tuple(int(v) for v in size.split("x")), seed=len(calls))

    monkeypatch.setattr(image_provider, "generate_image", fake)
    return calls


async def _post(client, headers, monkeypatch, **override):
    monkeypatch.setattr(studio, "get_ai_client", lambda: FakeAI({**DRAFT, **override}))
    response = await client.post(f"{_BASE}/studio/generate", json={"topic": "What is a SIEM?", "format": "image", "pillar": "soc"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _used(db_session, organization):
    return (await db_session.execute(select(func.count()).select_from(AIUsage).where(AIUsage.organization_id == organization.id, AIUsage.kind == "image"))).scalar_one()


# ---------------- nothing happens until it is configured and asked for ----------------


async def test_it_is_off_until_the_provider_is_configured_and_nothing_is_spent(client, auth_headers, engine_v2, fake_storage, monkeypatch, db_session, organization):
    assert not image_provider.configured(), "no key in the default configuration"
    post = await _post(client, auth_headers, monkeypatch)
    response = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)
    assert response.status_code == 422 and "aren't set up" in response.text
    usage = (await client.get(f"{_BASE}/usage", headers=auth_headers)).json()
    assert usage["image_configured"] is False and usage["image_budget"] is None
    assert await _used(db_session, organization) == 0


async def test_a_post_on_the_standard_engine_is_refused_before_anything_is_spent(client, auth_headers, fake_storage, provider, monkeypatch, db_session, organization):
    post = await _post(client, auth_headers, monkeypatch)  # engine flag off: engine v1
    assert post["design"].get("engine", "v1") == "v1"
    response = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)
    assert response.status_code == 422 and "new design engine" in response.text
    assert provider == [] and await _used(db_session, organization) == 0


async def test_drafting_never_generates_an_image(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch, db_session, organization):
    await _post(client, auth_headers, monkeypatch)
    assert provider == [] and await _used(db_session, organization) == 0, "images are made only when a person asks"


# ---------------- the workflow ----------------


async def test_one_illustration_is_made_labelled_synthetic_and_drawn_with_the_post(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch, db_session, organization):
    post = await _post(client, auth_headers, monkeypatch)
    plain = post["artwork"]["files"][0]["sha256"]
    response = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": "calm and simple"}, headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["design"]["art_asset_id"] and body["content"]["art_direction"]["imagery"] == "illustration"
    assert body["artwork"]["ok"] is True and body["artwork"]["synthetic_background"] is True and body["artwork"]["illustration"]["synthetic"] is True
    assert body["artwork"]["files"][0]["sha256"] != plain, "the picture shows the illustration"
    assert len(provider) == 1 and provider[0]["size"] == "1024x1024", "a poster takes a square picture"
    prompt = provider[0]["prompt"].lower()
    assert "no text" in prompt and "calm and simple" in prompt and "logs from many systems" in prompt
    assert "circuit-board" in prompt and "neon" in prompt, "the brand's forbidden visuals are in the prompt as things to avoid"
    asset = (await db_session.execute(select(SocialAsset).where(SocialAsset.id == uuid.UUID(body["design"]["art_asset_id"])))).scalar_one()
    assert asset.synthetic is True and "AI-generated" in asset.alt_text
    assert asset.provenance["model"] == "image-model" and asset.provenance["prompt_hash"] and asset.provenance["size"] == "1024x1024"
    assert KEY not in json.dumps(asset.provenance), "the key is never stored"
    assert await _used(db_session, organization) == 1
    assert "chk_synthetic_background" in [w["code"] for w in (await client.post(f"{_BASE}/posts/{post['id']}/check", headers=auth_headers)).json()["warnings"]]


async def test_the_same_concept_is_never_paid_for_twice(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch, db_session, organization):
    post = await _post(client, auth_headers, monkeypatch)
    first = (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)).json()
    again = (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)).json()
    assert again["design"]["art_asset_id"] == first["design"]["art_asset_id"]
    assert len(provider) == 1 and await _used(db_session, organization) == 1
    other = (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": "a different idea"}, headers=auth_headers)).json()
    assert other["design"]["art_asset_id"] != first["design"]["art_asset_id"] and len(provider) == 2, "a different concept is a new picture"


async def test_a_post_with_a_visual_composition_shows_the_picture_in_a_panel(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch):
    post = await _post(client, auth_headers, monkeypatch, art_direction={"concept": "A funnel of logs.", "composition": "checklist"})
    made = (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)).json()
    assert made["content"]["art_direction"]["composition"] == "visual" and provider[0]["size"] == "1536x1024", "a panel takes a wide picture"
    assert made["artwork"]["ok"] is True


async def test_attaching_an_illustration_withdraws_an_approval_and_taking_it_off_does_too(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch):
    post = await _post(client, auth_headers, monkeypatch)
    await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "submit"}, headers=auth_headers)
    approved = await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=auth_headers)
    assert approved.status_code == 200 and approved.json()["status"] == "approved", approved.text
    made = (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)).json()
    assert made["status"] == "draft" and made["approval_withdrawn"] is True and made["approved_at"] is None
    await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "submit"}, headers=auth_headers)
    assert (await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=auth_headers)).status_code == 200
    removed = await client.delete(f"{_BASE}/posts/{post['id']}/illustration", headers=auth_headers)
    assert removed.status_code == 200 and removed.json()["approval_withdrawn"] is True and removed.json()["status"] == "draft"
    body = removed.json()
    assert body["design"]["art_asset_id"] is None and body["content"]["art_direction"]["imagery"] == "none" and body["artwork"]["ok"] is True
    assert body["artwork"].get("illustration") is None


async def test_the_illustration_never_approves_schedules_or_publishes(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch):
    post = await _post(client, auth_headers, monkeypatch)
    made = (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)).json()
    assert made["status"] == "draft" and made["approved_at"] is None and made["scheduled_at"] is None and made["published_at"] is None


def test_a_different_illustration_is_a_different_artwork_so_only_the_exact_approved_one_can_be_published():
    content = {"headline": "What is a SIEM?", "icon": "logs", "art_direction": {"composition": "visual", "imagery": "illustration"}}
    base = {"template": "statement", "show_icon": True, "engine": "v2"}
    a = render.current_fingerprint("image", content, {**base, "art_asset_id": str(uuid.uuid4())}, "t", "SOC", BRAND)
    b = render.current_fingerprint("image", content, {**base, "art_asset_id": str(uuid.uuid4())}, "t", "SOC", BRAND)
    none = render.current_fingerprint("image", content, base, "t", "SOC", BRAND)
    assert a and b and none and len({a, b, none}) == 3


# ---------------- the hard budget ----------------


async def test_the_image_limit_counts_every_attempt_including_failed_ones_and_nothing_is_called_over_it(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch, db_session, organization):
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_MAX_ASSETS", 3)
    post = await _post(client, auth_headers, monkeypatch)

    async def failing(prompt, size=image_provider.SIZE):
        provider.append({"prompt": prompt, "size": size})
        raise ServiceUnavailableError("The image service didn't answer. Try again in a moment.")

    monkeypatch.setattr(image_provider, "generate_image", failing)
    for attempt in range(2):
        response = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": f"try {attempt}"}, headers=auth_headers)
        assert response.status_code == 503, response.text
    assert await _used(db_session, organization) == 2, "a failed attempt keeps its slot: the provider may have charged for it"
    calls_before = len(provider)

    async def working(prompt, size=image_provider.SIZE):
        provider.append({"prompt": prompt, "size": size})
        return art_png()

    monkeypatch.setattr(image_provider, "generate_image", working)
    assert (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": "third"}, headers=auth_headers)).status_code == 200
    refused = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": "fourth"}, headers=auth_headers)
    assert refused.status_code == 422 and "testing limit is reached" in refused.text and "3 of 3" in refused.text
    assert len(provider) == calls_before + 1, "the provider is not called once the limit is reached"
    assert await _used(db_session, organization) == 3


async def test_the_dollar_budget_stops_images_before_the_count_does(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch, db_session, organization):
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_QUALITY", "high")  # estimated at $0.25 each
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_BUDGET_USD", 0.30)
    post = await _post(client, auth_headers, monkeypatch)
    assert (await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": "one"}, headers=auth_headers)).status_code == 200
    refused = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={"direction": "two"}, headers=auth_headers)
    assert refused.status_code == 422 and "budget would be exceeded" in refused.text
    assert len(provider) == 1 and await _used(db_session, organization) == 1


async def test_with_no_quality_set_every_image_is_priced_at_the_worst_case_so_the_budget_cannot_be_overrun(monkeypatch):
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_COST_USD", 0.0)
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_QUALITY", "")
    assert image_budget.est_usd() == 0.25
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_QUALITY", "medium")
    assert image_budget.est_usd() == 0.07
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_COST_USD", 0.5)
    assert image_budget.est_usd() == 0.5, "an explicit price wins"
    assert app_settings.SOCIAL_IMAGE_MAX_ASSETS == 10 and app_settings.SOCIAL_IMAGE_BUDGET_USD == 5.0, "the approved testing limits are the defaults"


async def test_an_ai_background_counts_toward_the_same_limit(client, auth_headers, fake_storage, provider, monkeypatch, db_session, organization):
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_MAX_ASSETS", 1)

    async def background(prompt):
        return art_png((1024, 1536))

    monkeypatch.setattr(image_provider, "generate_background", background)
    post = (await client.post(f"{_BASE}/posts", json={"title": "t", "format": "image", "pillar": "soc", "content": {"headline": "Why logs matter", "caption": "Logs tell the story."}}, headers=auth_headers)).json()
    await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo"}, headers=auth_headers)
    assert (await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)).status_code == 200
    again = await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)
    assert again.status_code == 422 and "testing limit is reached" in again.text


async def test_the_usage_overview_shows_the_image_limit_once_configured(client, auth_headers, provider, db_session, organization):
    usage = (await client.get(f"{_BASE}/usage", headers=auth_headers)).json()
    shown = usage["image_budget"]
    assert usage["image_configured"] is True and shown["assets_max"] == 10 and shown["assets_used"] == 0 and shown["budget_usd"] == 5.0 and shown["is_estimate"] is True
    assert KEY not in json.dumps(usage)


async def test_a_second_request_for_the_same_post_while_one_is_running_is_refused_not_paid_twice(client, auth_headers, engine_v2, fake_storage, provider, monkeypatch, db_session, organization):
    from sqlalchemy import text

    post = await _post(client, auth_headers, monkeypatch)
    async with engine.connect() as other:
        key = image_budget._key("social-image-post", uuid.UUID(post["id"]))
        assert (await other.execute(text("select pg_try_advisory_lock(:k)"), {"k": key})).scalar_one() is True
        try:
            response = await client.post(f"{_BASE}/posts/{post['id']}/illustration", json={}, headers=auth_headers)
        finally:
            await other.execute(text("select pg_advisory_unlock(:k)"), {"k": key})
    assert response.status_code == 409 and "already being made" in response.text
    assert provider == [] and await _used(db_session, organization) == 0


# ---------------- the key is never exposed ----------------


async def test_the_api_key_is_only_ever_sent_as_the_authorization_header_and_never_logged_or_returned(monkeypatch):
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_API_KEY", KEY)
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_API_BASE_URL", "https://images.test")
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_MODEL", "image-model")
    monkeypatch.setattr(app_settings, "SOCIAL_IMAGE_QUALITY", "medium")
    seen = {}
    logged = []

    class Logger:
        def warning(self, *a, **k):
            logged.append((a, k))

        info = error = debug = warning

    class Response:
        status_code = 401

        def raise_for_status(self):
            import httpx

            raise httpx.HTTPStatusError(f"401 for url with {KEY}", request=None, response=self)

        def json(self):
            return {}

    class Http:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            seen.update({"url": url, "json": json, "headers": headers})
            return Response()

    monkeypatch.setattr(image_provider.httpx, "AsyncClient", Http)
    monkeypatch.setattr(image_provider, "logger", Logger())
    with pytest.raises(ServiceUnavailableError) as raised:
        await image_provider.generate_image("a prompt", "1024x1024")
    assert seen["headers"]["Authorization"] == f"Bearer {KEY}" and KEY not in json.dumps(seen["json"]) and seen["json"]["quality"] == "medium"
    assert KEY not in str(raised.value) and KEY not in repr(logged), "not in the error shown to people, not in the logs"


# ---------------- how the picture is drawn ----------------

TEMPLATES = ("neon", "statement", "split", "solid", "editorial")


def draw_with_art(composition, template, logo=None):
    content = {"headline": "What is a SIEM, really?", "icon": "logs", "support_line": "It collects logs in one place so analysts spot attacks sooner.", "art_direction": {"composition": composition, "imagery": "illustration"}}
    design = {"template": template, "show_icon": True, "engine": "v2", "art_asset_id": str(uuid.uuid4()), "variant": 2}
    return render.render("image", content, design, "t", "SOC", BRAND, RULES, logo, None, art_png((1536, 1024)))


@pytest.mark.parametrize("template", TEMPLATES)
@pytest.mark.parametrize("composition", ["visual", "poster"])
def test_an_illustration_is_drawn_in_every_theme_with_the_checks_green(composition, template):
    images, _ = draw_with_art(composition, template)
    assert images[0].validation["ok"], (composition, template, images[0].validation["problems"])


@pytest.mark.parametrize("template", TEMPLATES)
def test_the_headline_stays_above_the_illustration_panel(template):
    content = {"headline": "What is a SIEM, really?", "icon": "logs", "support_line": "It collects logs in one place so analysts spot attacks sooner.", "art_direction": {"composition": "visual", "imagery": "illustration"}}
    design = {"template": template, "show_icon": True, "engine": "v2", "art_asset_id": str(uuid.uuid4()), "variant": 2}
    spec = render.specs_for("image", content, design, "t", "SOC", BRAND)[0]
    assert spec.composition == "visual"
    palette = render.palette_of(BRAND["colors"])
    art = Image.open(io.BytesIO(art_png((1536, 1024)))).convert("RGB")
    _, ctx, _ = render._draw_image(spec, None, None, palette, RULES, (1080, 1350), "image", True, art=art)
    text = [b["box"] for b in ctx.blocks if b["role"] in ("headline", "subline")]
    assert text and all(t[3] <= 1350 - 96 - 214 - compose.VISUAL_H for t in text), "the words end above the picture"


def test_a_generated_picture_is_mapped_to_the_brands_two_tones_so_it_cannot_leave_the_palette():
    art = Image.open(io.BytesIO(art_png((1536, 1024)))).convert("RGB")
    dark, light = (8, 12, 10), (154, 214, 43)
    mapped = compose.duotone(art, dark, light)
    lo = tuple(min(a, b) for a, b in zip(dark, light))
    hi = tuple(max(a, b) for a, b in zip(dark, light))
    for pixel in set(mapped.getdata()):
        assert all(lo[i] - 1 <= pixel[i] <= hi[i] + 1 for i in range(3)), pixel


def test_a_missing_illustration_gives_way_to_the_poster_instead_of_failing():
    content = {"headline": "What is a SIEM, really?", "icon": "logs", "art_direction": {"composition": "visual", "imagery": "illustration"}}
    design = {"template": "statement", "show_icon": True, "engine": "v2", "art_asset_id": str(uuid.uuid4())}
    images, _ = render.render("image", content, design, "t", "SOC", BRAND, RULES, None, None, None)
    assert images[0].validation["ok"]


def test_engine_v1_ignores_an_illustration_entirely():
    content = {"headline": "What is a SIEM, really?", "icon": "logs", "support_line": "x"}
    a, fa = render.render("image", content, {"template": "statement", "show_icon": True}, "t", "SOC", BRAND, RULES, None, None, None)
    b, fb = render.render("image", content, {"template": "statement", "show_icon": True, "art_asset_id": str(uuid.uuid4())}, "t", "SOC", BRAND, RULES, None, None, art_png())
    assert a[0].png == b[0].png and fa == fb, "the standard renderer is untouched"


def test_the_prompt_carries_the_brand_restrictions_and_never_asks_for_people_text_or_screens():
    brief = ad.ArtBrief(concept="Logs from many systems flowing into one place.", metaphor="streams joining a river")
    prompt = __import__("modules.social_media.illustration", fromlist=["x"]).build_prompt(brief, "What is a SIEM?", BRAND, RULES, "1024x1024", "")
    lowered = prompt.lower()
    for banned in RULES["forbidden_visuals"]:
        assert banned.lower() in lowered, banned
    assert "no text" in lowered and "people" in lowered and "screens" in lowered and "flat" in lowered
    assert "logs from many systems" in lowered and "streams joining a river" in lowered
