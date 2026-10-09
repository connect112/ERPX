"""
Social Media phase 2b: the artwork renderer, the image library, designs and approvals, AI backgrounds, proofreading
and the nine-post grid.

Storage is an in-memory fake and the image/AI providers are stubs. The renderer tests draw real pictures with the real
font and look at the pixels.
"""

import base64
import io
import json
import uuid

import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import select

from modules.social_media import assets, defaults, grid, image_provider, render, studio
from modules.social_media.models import AIUsage, SocialAsset, SocialPost
from packages.ai.client import AICompletionResult
from packages.storage import client as storage_client

pytestmark = pytest.mark.api

_BASE = "/api/v1/social-media"
BRAND = {**defaults.DEFAULT_BRAND, "handle": "@pentrix"}
RULES = defaults.DEFAULT_DESIGN_RULES


# ---------------- helpers ----------------


def png(size=(400, 300), color=(30, 90, 200), mode="RGB", info=None) -> bytes:
    image = Image.new(mode, size, color)
    out = io.BytesIO()
    meta = None
    if info:
        meta = PngImagePlugin.PngInfo()
        for k, v in info.items():
            meta.add_text(k, v)
    image.save(out, format="PNG", pnginfo=meta)
    return out.getvalue()


def jpeg(size=(800, 600), color=(120, 130, 140)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="JPEG")
    return out.getvalue()


def draw(post_format="image", content=None, design=None, logo=None, picture=None, brand=None, rules=None, title="Why logs matter", pillar="SOC"):
    content = content or {"headline": "Why logs matter"}
    design = {"template": "editorial", **(design or {})}
    return render.render(post_format, content, design, title, pillar, brand or BRAND, rules or RULES, logo, picture)


def pixels(rendered: render.Rendered) -> Image.Image:
    return Image.open(io.BytesIO(rendered.png)).convert("RGB")


# ---------------- the renderer ----------------


@pytest.mark.parametrize("template", ["editorial", "statement", "photo", "screenshot"])
def test_every_template_draws_a_valid_image_of_the_right_size(template):
    picture = png((1600, 1200), (60, 80, 120)) if template in ("photo", "screenshot") else None
    images, _ = draw(design={"template": template}, picture=picture)
    assert len(images) == 1 and (images[0].width, images[0].height) == (1080, 1350)
    assert images[0].validation["ok"], images[0].validation["problems"]
    assert images[0].validation["fonts"] == ["Inter"]


def test_stories_and_reel_covers_are_tall_and_keep_text_clear_of_the_app_interface():
    for fmt in ("story", "reel"):
        (image,), _ = draw(post_format=fmt)
        assert (image.width, image.height) == (1080, 1920) and image.validation["ok"]
        headline = next(b for b in image.validation["blocks"] if b["role"] == "headline")
        assert headline
    picture = pixels(image)
    top_band = picture.crop((0, 0, 1080, render.TALL_SAFE_TOP - 20)).getcolors(maxcolors=1_000_000)
    assert len(top_band) == 1, "nothing is drawn in the band the app's own controls cover"


def test_a_carousel_is_one_image_per_slide_with_a_page_count():
    slides = [{"heading": f"Step {i}", "body": "Short body text."} for i in range(1, 5)]
    images, _ = draw(post_format="carousel", content={"slides": slides})
    assert [i.slide for i in images] == [0, 1, 2, 3] and all(i.validation["ok"] for i in images)
    assert len({i.sha256 for i in images}) == 4
    with pytest.raises(render.RenderError):
        draw(post_format="carousel", content={"slides": slides[:1]})
    with pytest.raises(render.RenderError):
        draw(post_format="carousel", content={"slides": slides * 3})


def test_the_same_input_always_gives_the_same_picture():
    a, fa = draw(design={"template": "statement"})
    b, fb = draw(design={"template": "statement"})
    assert a[0].sha256 == b[0].sha256 and fa == fb
    c, fc = draw(content={"headline": "Why logs matter most"}, design={"template": "statement"})
    assert c[0].sha256 != a[0].sha256 and fc != fa


def test_text_that_cannot_fit_is_refused_never_clipped_or_shrunk_to_nothing():
    with pytest.raises(render.RenderError, match="too long"):
        draw(content={"headline": "word " * 120})
    with pytest.raises(render.RenderError, match="too long"):
        draw(design={"subline": "x " * 400})


def test_a_word_longer_than_the_line_is_broken_so_it_cannot_run_off_the_image():
    (image,), _ = draw(content={"headline": "Supercalifragilisticexpialidocious" * 2})
    box = next(b for b in image.validation["blocks"] if b["role"] == "headline")
    face = render.font(box["size_px"], 700)
    lines = render.wrap("Supercalifragilisticexpialidocious" * 2, face, 1080 - 2 * render.MARGIN)
    assert len(lines) >= 2 and all(face.getlength(line) <= 1080 - 2 * render.MARGIN for line in lines)


def test_the_design_rules_are_enforced_and_reported():
    (long_headline,), _ = draw(content={"headline": "one two three four five six seven eight nine ten"})
    assert not long_headline.validation["ok"] and "words" in long_headline.validation["problems"][0]
    (dense,), _ = draw(content={"headline": "Short headline"}, design={"subline": "x" * 120}, rules={**RULES, "max_cover_text_chars": 40})
    assert not dense.validation["ok"] and any("characters" in p for p in dense.validation["problems"])


def test_low_contrast_colours_are_replaced_and_the_contrast_is_measured():
    pale = {**BRAND, "colors": {**BRAND["colors"], "muted": "#F0F0F0", "ink": "#F5F5F5"}}
    (image,), _ = draw(brand=pale, design={"subline": "Supporting line here."})
    assert image.validation["ok"], image.validation["problems"]
    assert image.validation["min_contrast"] >= 4.5


def test_a_busy_picture_is_darkened_until_the_text_can_be_read():
    noisy = Image.new("RGB", (1200, 1600), (245, 245, 245))
    out = io.BytesIO()
    noisy.save(out, format="PNG")
    (image,), _ = draw(design={"template": "photo"}, picture=out.getvalue())
    assert image.validation["ok"], image.validation["problems"]
    assert image.validation["min_contrast"] >= 4.5
    assert pixels(image).getpixel((1000, 700))[0] < 245, "the bright picture was darkened"


def test_the_logo_is_placed_pixel_for_pixel_with_only_its_empty_margin_trimmed():
    logo = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    logo.paste(Image.new("RGBA", (300, 150), (255, 0, 0, 255)), (100, 175))  # a red bar in a transparent frame
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    (with_logo,), _ = draw(logo=buf.getvalue())
    (without,), _ = draw(logo=None)
    assert with_logo.metrics["logo"] == "bottom_left" and without.metrics["logo"] is None
    image = pixels(with_logo)
    reds = [image.getpixel((x, y)) for x in range(render.MARGIN + 5, render.MARGIN + 150, 7) for y in range(1350 - render.MARGIN - 90, 1350 - render.MARGIN - 8, 7)]
    assert all(p == (255, 0, 0) for p in reds), "the logo colour is exactly as uploaded: nothing recoloured or redrawn"
    assert any("No approved logo" in n for n in without.validation["notes"])
    (hidden,), _ = draw(logo=buf.getvalue(), design={"show_logo": False})
    assert hidden.metrics["logo"] is None


def test_the_logo_gets_a_light_chip_on_a_dark_design_so_it_stays_visible():
    logo = png((300, 120), (10, 10, 10), mode="RGBA")
    (image,), _ = draw(design={"template": "statement"}, logo=logo)
    chip = pixels(image).getpixel((render.MARGIN - 6, 1350 - render.MARGIN - 60))
    assert chip == (255, 255, 255)


def test_templates_that_need_a_picture_say_so():
    with pytest.raises(render.RenderError, match="needs a picture"):
        draw(design={"template": "photo"})
    with pytest.raises(render.RenderError, match="needs a screenshot"):
        draw(design={"template": "screenshot"})
    with pytest.raises(render.RenderError, match="couldn't be read"):
        draw(design={"template": "photo"}, picture=b"not an image")
    with pytest.raises(render.RenderError, match="Choose one"):
        draw(design={"template": "neon"})


def test_the_fingerprint_follows_exactly_what_is_shown():
    specs = render.specs_for("image", {"headline": "Why logs matter"}, {"template": "editorial"}, "t", "SOC", BRAND)
    same = render.specs_for("image", {"headline": "Why logs matter"}, {"template": "editorial"}, "other title", "SOC", BRAND)
    assert render.fingerprint(specs, {}) == render.fingerprint(same, {})  # the title is not shown, so it doesn't matter
    changed = render.specs_for("image", {"headline": "Why logs matter."}, {"template": "editorial"}, "t", "SOC", BRAND)
    assert render.fingerprint(changed, {}) != render.fingerprint(specs, {})
    assert render.current_fingerprint("carousel", {"slides": []}, {}, "t", None, BRAND) is None


# ---------------- grid analysis (pure) ----------------


def tile(template="editorial", color="#F6F7F9", lum=0.9, headline="A", dhash="0" * 16, chars=20, logo="bottom_left", px=100):
    return {"metrics": {"template": template, "dominant": color, "luminance": lum, "headline": headline, "dhash": dhash, "text_chars": chars, "logo": logo, "headline_px": px}}


def codes(tiles, live=True):
    return {f["code"] for f in grid.analyze(tiles, RULES, live)}


def test_neighbours_in_a_three_column_grid():
    assert grid.neighbours(9) == [(0, 1), (0, 3), (1, 2), (1, 4), (2, 5), (3, 4), (3, 6), (4, 5), (4, 7), (5, 8), (6, 7), (7, 8)]


def test_a_varied_grid_has_nothing_to_flag():
    palette = [("editorial", "#F6F7F9", 0.9), ("statement", "#0F172A", 0.05), ("photo", "#3B5B8C", 0.1), ("screenshot", "#E6E9EF", 0.8)]
    tiles = [tile(*palette[i % 4], headline=f"unique headline number {i} here", dhash=f"{(i * 0x1111111111111111) & 0xFFFFFFFFFFFFFFFF:016x}") for i in range(9)]
    findings = {f["code"] for f in grid.analyze(tiles, RULES, live_available=True)}
    assert not {c for c in findings if c.startswith("grid_") and c not in ("grid_abrupt_change",)}


def test_neighbours_that_look_the_same_merge_into_a_block():
    assert "grid_same_look" in codes([tile(), tile(), tile("statement", "#0F172A", 0.05)])
    assert "grid_same_look" not in codes([tile(), tile("statement", "#0F172A", 0.05)])


def test_a_whole_row_or_column_of_one_layout_is_flagged_but_a_mix_is_not():
    row = [tile(color="#111111", lum=0.1), tile(color="#aa0000", lum=0.3), tile(color="#00aa00", lum=0.5)]
    assert "grid_row_repeat" in codes(row + [tile("photo", "#445566", 0.2), tile("statement", "#0F172A", 0.05), tile("screenshot", "#E6E9EF", 0.8)])
    assert "grid_column_repeat" in codes([tile(color="#111111", lum=0.1), tile("photo", "#445566", 0.2), tile("statement", "#0F172A", 0.05), tile(color="#aa0000", lum=0.3), tile("screenshot", "#E6E9EF", 0.8), tile("photo", "#996633", 0.4), tile(color="#00aa00", lum=0.5)])
    assert "grid_row_repeat" not in codes([tile(), tile("statement", "#0F172A", 0.05), tile("photo", "#445566", 0.2)])


def test_too_many_of_one_layout_is_flagged_as_uniform():
    mixed = [tile("editorial", f"#{i * 20:02x}{i * 10:02x}{i * 5:02x}", 0.5, headline=f"head {i}", dhash=f"{i:016x}") for i in range(7)] + [tile("statement", "#0F172A", 0.05), tile("photo", "#445566", 0.2)]
    assert "grid_uniform" in codes(mixed)


def test_repeated_headlines_and_near_identical_artwork_are_flagged():
    assert "grid_repeated_headline" in codes([tile(headline="What is a SIEM and why it matters"), tile("statement", "#0F172A", 0.05, headline="What is a SIEM and why it matters")])
    assert "grid_repeated_artwork" in codes([tile(dhash="ffff0000ffff0000"), tile(dhash="ffff0000ffff0001", headline="Different words")])


def test_dense_text_inconsistent_logo_type_scale_and_abrupt_jumps_are_flagged():
    findings = codes([tile(chars=400), tile("statement", "#0F172A", 0.01, headline="b", dhash="f" * 16, logo=None, px=40)])
    assert {"grid_text_dense", "grid_logo_inconsistent", "grid_type_scale", "grid_abrupt_change"} <= findings


def test_a_missing_live_profile_is_stated_rather_than_hidden():
    assert "grid_live_unavailable" in codes([tile()], live=False)
    assert "grid_live_unavailable" not in codes([tile()], live=True)
    assert "grid_too_small" in codes([tile()])


# ---------------- storage fake, fixtures ----------------


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload_bytes(self, key, data, content_type="application/octet-stream"):
        self.objects[key] = data

    async def read_bytes(self, key, max_bytes=20 * 1024 * 1024):
        if key not in self.objects:
            raise RuntimeError("missing")
        return self.objects[key]

    async def delete_object(self, key):
        self.deleted.append(key)
        self.objects.pop(key, None)

    def presigned_download_url(self, key):
        return f"https://files.test/{key}"


@pytest.fixture
def storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage_client, "_client", fake)
    return fake


async def _upload(client, headers, data, kind="photo", name="pic.png", alt=""):
    return await client.post(f"{_BASE}/assets", files={"file": (name, data, "image/png")}, data={"kind": kind, "alt_text": alt}, headers=headers)


async def _logo(client, headers, size=(600, 600)):
    asset = (await _upload(client, headers, png(size, (30, 90, 200), mode="RGBA"), kind="logo", name="logo.png")).json()
    used = await client.post(f"{_BASE}/assets/{asset['id']}/use-as-logo", headers=headers)
    assert used.status_code == 200, used.text
    return asset


async def _post(client, headers, **kw):
    body = {"title": "t", "format": "image", "pillar": "soc", "content": {"headline": "Why logs matter", "caption": "Logs tell the story of an attack."}}
    body.update(kw)
    response = await client.post(f"{_BASE}/posts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def _render(client, headers, post_id, design=None):
    if design is not None:
        response = await client.put(f"{_BASE}/posts/{post_id}/design", json=design, headers=headers)
        assert response.status_code == 200, response.text
    return await client.post(f"{_BASE}/posts/{post_id}/render", headers=headers)


def _codes(post):
    return {w.get("code") for w in post["warnings"]}


async def _check(client, headers, post_id):
    response = await client.post(f"{_BASE}/posts/{post_id}/check", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------- the image library ----------------


async def test_an_upload_is_checked_reencoded_and_stored_under_our_own_name(client, auth_headers, storage, db_session, organization):
    tagged = png((300, 200), info={"Comment": "<script>alert(1)</script>", "Author": "someone"})
    response = await _upload(client, auth_headers, tagged, kind="screenshot", name="../../etc/passwd<>.png", alt="A lab screenshot")
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["kind"] == "screenshot" and asset["synthetic"] is False and asset["alt_text"] == "A lab screenshot"
    assert asset["filename"] == "passwd.png" and asset["url"].startswith("https://files.test/social/")
    row = (await db_session.execute(select(SocialAsset).where(SocialAsset.id == uuid.UUID(asset["id"])))).scalar_one()
    stored = storage.objects[row.storage_key]
    assert row.storage_key.startswith(f"social/{organization.id}/assets/") and "passwd" not in row.storage_key
    assert b"script" not in stored and b"tEXt" not in stored, "embedded metadata is not kept"
    assert row.sha256 and (row.width, row.height) == (300, 200)


@pytest.mark.parametrize(
    "data, message",
    [
        (b"", "empty"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "usable image"),
        (b"just some text", "usable image"),
        (png((30, 30)), "too small"),
        (b"\x89PNG\r\n\x1a\n" + b"0" * 100, "usable image"),
    ],
)
async def test_bad_uploads_are_refused_with_a_reason(client, auth_headers, storage, data, message):
    response = await _upload(client, auth_headers, data)
    assert response.status_code == 422 and message in response.text and storage.objects == {}


async def test_uploads_have_size_and_format_limits(client, auth_headers, storage, monkeypatch):
    gif = io.BytesIO()
    Image.new("RGB", (200, 200)).save(gif, format="GIF")
    assert "PNG, JPEG or WebP" in (await _upload(client, auth_headers, gif.getvalue())).text
    monkeypatch.setattr(assets, "MAX_SIDE", 500)
    assert "too large" in (await _upload(client, auth_headers, png((800, 600)))).text
    monkeypatch.setattr(assets, "MAX_UPLOAD_BYTES", 1000)
    assert "larger than" in (await _upload(client, auth_headers, png((300, 300), info={"x": "y" * 2000}))).text
    assert (await _upload(client, auth_headers, png(), kind="background")).status_code == 422  # backgrounds are generated, not uploaded
    assert (await _upload(client, auth_headers, png(), kind="video")).status_code == 422


async def test_a_jpeg_photo_is_stored_as_a_jpeg_and_a_logo_as_lossless_png(client, auth_headers, storage, db_session):
    photo = (await client.post(f"{_BASE}/assets", files={"file": ("p.jpg", jpeg(), "image/jpeg")}, data={"kind": "photo"}, headers=auth_headers)).json()
    logo = (await _upload(client, auth_headers, png((200, 200), (5, 5, 5), mode="RGBA"), kind="logo")).json()
    assert photo["content_type"] == "image/jpeg" and logo["content_type"] == "image/png"
    stored_logo = Image.open(io.BytesIO(storage.objects[(await db_session.get(SocialAsset, uuid.UUID(logo["id"]))).storage_key]))
    assert stored_logo.mode == "RGBA" and stored_logo.getpixel((10, 10)) == (5, 5, 5, 255)


async def test_library_access_needs_permissions(client, staff_headers, rbac_seeded, storage):
    assert (await client.get(f"{_BASE}/assets", headers=staff_headers)).status_code == 403
    assert (await _upload(client, staff_headers, png())).status_code == 403
    assert (await client.post(f"{_BASE}/posts/{uuid.uuid4()}/render", headers=staff_headers)).status_code == 403
    assert (await client.get(f"{_BASE}/grid", headers=staff_headers)).status_code == 403


async def test_only_a_logo_can_become_the_approved_logo_and_it_cannot_be_deleted_while_in_use(client, auth_headers, storage):
    photo = (await _upload(client, auth_headers, png())).json()
    assert (await client.post(f"{_BASE}/assets/{photo['id']}/use-as-logo", headers=auth_headers)).status_code == 422
    logo = await _logo(client, auth_headers)
    listed = (await client.get(f"{_BASE}/assets", headers=auth_headers)).json()
    assert {a["id"]: a["is_logo"] for a in listed} == {photo["id"]: False, logo["id"]: True}
    assert (await client.delete(f"{_BASE}/assets/{logo['id']}", headers=auth_headers)).status_code == 409
    assert (await client.delete(f"{_BASE}/assets/{photo['id']}", headers=auth_headers)).status_code == 204
    assert len(storage.deleted) == 1 and len((await client.get(f"{_BASE}/assets?kind=photo", headers=auth_headers)).json()) == 0


async def test_the_logo_setting_cannot_point_at_a_file_that_is_not_this_organisations_logo(client, auth_headers, storage, db_session):
    from modules.organizations.repository import OrganizationRepository
    from tests._fixtures import _make_user

    brand = (await client.get(f"{_BASE}/settings", headers=auth_headers)).json()["brand"]
    for key in ("social/someone-else/assets/x.png", "../../secrets", "social/anything"):
        response = await client.put(f"{_BASE}/settings", json={"brand": {**brand, "logo_key": key}}, headers=auth_headers)
        assert response.status_code == 422, key
    other = await OrganizationRepository(db_session).create(name="Other", slug=f"o-{uuid.uuid4().hex[:6]}")
    await db_session.flush()
    _, token = await _make_user(db_session, other, is_superuser=True, email=f"o-{uuid.uuid4().hex[:6]}@erpx.example.com")
    theirs = (await _upload(client, {"Authorization": f"Bearer {token}"}, png(), kind="logo")).json()
    their_key = (await db_session.get(SocialAsset, uuid.UUID(theirs["id"]))).storage_key
    stolen = await client.put(f"{_BASE}/settings", json={"brand": {**brand, "logo_key": their_key}}, headers=auth_headers)
    assert stolen.status_code == 422, "another organisation's logo can't be used"
    assert (await client.delete(f"{_BASE}/assets/{theirs['id']}", headers=auth_headers)).status_code == 404


# ---------------- designs and rendering ----------------


async def test_rendering_draws_validates_stores_and_links_the_artwork(client, auth_headers, storage):
    await _logo(client, auth_headers)
    post = await _post(client, auth_headers)
    rendered = await _render(client, auth_headers, post["id"], {"template": "editorial", "subline": "A plain guide."})
    assert rendered.status_code == 200, rendered.text
    art = rendered.json()["artwork"]
    assert art["ok"] is True and art["template"] == "editorial" and art["logo_key"] and len(art["files"]) == 1
    file = art["files"][0]
    assert file["url"].startswith("https://files.test/social/") and (file["width"], file["height"]) == (1080, 1350)
    assert Image.open(io.BytesIO(storage.objects[file["key"]])).size == (1080, 1350)
    assert file["validation"]["ok"] and file["metrics"]["logo"] == "bottom_left" and len(file["metrics"]["dhash"]) == 16
    again = (await _render(client, auth_headers, post["id"])).json()["artwork"]
    assert again["files"][0]["sha256"] == file["sha256"], "rendering twice gives the same picture"


async def test_a_new_render_replaces_the_old_files_and_removing_deletes_them(client, auth_headers, storage):
    post = await _post(client, auth_headers)
    first = (await _render(client, auth_headers, post["id"], {"template": "editorial"})).json()["artwork"]["files"][0]["key"]
    second = (await _render(client, auth_headers, post["id"], {"template": "statement"})).json()["artwork"]["files"][0]["key"]
    assert first != second and first in storage.deleted and first not in storage.objects and second in storage.objects
    removed = await client.delete(f"{_BASE}/posts/{post['id']}/artwork", headers=auth_headers)
    assert removed.json()["artwork"] == {} and removed.json()["design"]["template"] == "statement"  # the design is kept
    assert second not in storage.objects


async def test_a_carousel_renders_one_file_per_slide(client, auth_headers, storage):
    post = await _post(client, auth_headers, format="carousel", content={"headline": "h", "caption": "c", "slides": [{"heading": "One", "body": "First"}, {"heading": "Two", "body": "Second"}]})
    art = (await _render(client, auth_headers, post["id"], {"template": "editorial"})).json()["artwork"]
    assert [f["slide"] for f in art["files"]] == [0, 1] and len(storage.objects) == 2


async def test_designs_that_need_a_picture_validate_the_picture(client, auth_headers, storage):
    post = await _post(client, auth_headers)
    # Choosing the template first is fine (an AI background can fill it); drawing without a picture is not.
    assert (await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo"}, headers=auth_headers)).status_code == 200
    needs = await client.post(f"{_BASE}/posts/{post['id']}/render", headers=auth_headers)
    assert needs.status_code == 422 and "Choose a picture" in needs.text
    logo = await _logo(client, auth_headers)
    assert (await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo", "background_asset_id": logo["id"]}, headers=auth_headers)).status_code == 422
    assert (await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo", "background_asset_id": str(uuid.uuid4())}, headers=auth_headers)).status_code == 404
    picture = (await _upload(client, auth_headers, png((1200, 1600), (40, 60, 90)))).json()
    ok = await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo", "background_asset_id": picture["id"]}, headers=auth_headers)
    assert ok.status_code == 200 and ok.json()["design"]["background_asset_id"] == picture["id"]
    rendered = (await client.post(f"{_BASE}/posts/{post['id']}/render", headers=auth_headers)).json()
    assert rendered["artwork"]["background"]["kind"] == "photo" and rendered["artwork"]["synthetic_background"] is False
    assert (await client.delete(f"{_BASE}/assets/{picture['id']}", headers=auth_headers)).status_code == 409  # in use


async def test_a_text_that_cannot_fit_gives_a_clear_error_and_changes_nothing(client, auth_headers, storage):
    slides = [{"heading": "Short", "body": "Fine."}, {"heading": "Two", "body": "Fine too."}]
    post = await _post(client, auth_headers, format="carousel", content={"headline": "h", "caption": "c", "slides": slides})
    await _render(client, auth_headers, post["id"], {"template": "editorial"})
    before = set(storage.objects)
    too_long = [{"heading": "Short", "body": "Fine."}, {"heading": "Two", "body": "word " * 80}]
    await client.patch(f"{_BASE}/posts/{post['id']}", json={"content": {"headline": "h", "caption": "c", "slides": too_long}}, headers=auth_headers)
    response = await client.post(f"{_BASE}/posts/{post['id']}/render", headers=auth_headers)
    assert response.status_code == 422 and "too long" in response.text
    assert set(storage.objects) == before, "a failed render leaves the earlier artwork alone"


async def test_artwork_cannot_be_changed_on_a_post_that_is_cancelled_or_on_its_way_to_instagram(client, auth_headers, storage, db_session):
    post = await _post(client, auth_headers)
    await _render(client, auth_headers, post["id"], {"template": "editorial"})
    row = (await db_session.execute(select(SocialPost).where(SocialPost.id == uuid.UUID(post["id"])))).scalar_one()
    for state in ("scheduled", "published", "cancelled"):
        row.status = state
        await db_session.flush()
        assert (await client.post(f"{_BASE}/posts/{post['id']}/render", headers=auth_headers)).status_code == 409
        assert (await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "statement"}, headers=auth_headers)).status_code == 409
        assert (await client.delete(f"{_BASE}/posts/{post['id']}/artwork", headers=auth_headers)).status_code == 409


# ---------------- artwork and approval ----------------


async def _approve(client, headers, post_id):
    await client.post(f"{_BASE}/posts/{post_id}/transition", json={"action": "submit"}, headers=headers)
    return await client.post(f"{_BASE}/posts/{post_id}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=headers)


async def test_artwork_that_matches_the_post_can_be_approved_and_changing_it_withdraws_the_approval(client, auth_headers, storage):
    await _logo(client, auth_headers)
    post = await _post(client, auth_headers)
    await _render(client, auth_headers, post["id"], {"template": "editorial"})
    checked = await _check(client, auth_headers, post["id"])
    assert not ({"chk_artwork_stale", "chk_artwork_invalid", "chk_no_artwork"} & _codes(checked))
    approved = await _approve(client, auth_headers, post["id"])
    assert approved.status_code == 200, approved.text
    changed = (await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "statement"}, headers=auth_headers)).json()
    assert changed["status"] == "draft" and changed["approval_withdrawn"] is True and changed["approved_at"] is None


async def test_the_approved_hash_covers_the_artwork(client, auth_headers, storage, db_session):
    post = await _post(client, auth_headers)
    await _render(client, auth_headers, post["id"], {"template": "editorial"})
    await _approve(client, auth_headers, post["id"])
    row = (await db_session.execute(select(SocialPost).where(SocialPost.id == uuid.UUID(post["id"])))).scalar_one()
    from modules.social_media.service import content_hash

    assert row.approved_content_hash == content_hash(row)
    row.artwork = {**row.artwork, "files": [{**row.artwork["files"][0], "sha256": "0" * 64}]}
    assert row.approved_content_hash != content_hash(row), "swapping the picture after approval is detectable"


async def test_artwork_out_of_date_with_the_words_blocks_approval_until_it_is_made_again(client, auth_headers, storage):
    post = await _post(client, auth_headers)
    await _render(client, auth_headers, post["id"], {"template": "editorial"})
    await client.patch(f"{_BASE}/posts/{post['id']}", json={"content": {"headline": "A different headline", "caption": "Logs tell the story of an attack."}}, headers=auth_headers)
    stale = await _check(client, auth_headers, post["id"])
    assert "chk_artwork_stale" in _codes(stale)
    await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "submit"}, headers=auth_headers)
    blocked = await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=auth_headers)
    assert blocked.status_code == 422 and "artwork" in blocked.text.lower()
    await client.post(f"{_BASE}/posts/{post['id']}/render", headers=auth_headers)
    fresh = await _check(client, auth_headers, post["id"])
    assert "chk_artwork_stale" not in _codes(fresh)
    assert (await client.post(f"{_BASE}/posts/{post['id']}/transition", json={"action": "approve", "acknowledge_warnings": True}, headers=auth_headers)).status_code == 200


async def test_artwork_that_breaks_the_design_rules_blocks_approval(client, auth_headers, storage):
    post = await _post(client, auth_headers, content={"headline": "one two three four five six seven eight nine ten", "caption": "c"})
    art = (await _render(client, auth_headers, post["id"], {"template": "editorial"})).json()["artwork"]
    assert art["ok"] is False
    checked = await _check(client, auth_headers, post["id"])
    assert "chk_artwork_invalid" in _codes(checked)
    assert (await _approve(client, auth_headers, post["id"])).status_code == 422


async def test_missing_artwork_and_missing_logo_are_noted_but_do_not_block(client, auth_headers, storage):
    post = await _post(client, auth_headers)
    assert "chk_no_artwork" in _codes(await _check(client, auth_headers, post["id"]))
    await _render(client, auth_headers, post["id"], {"template": "editorial"})
    codes_now = _codes(await _check(client, auth_headers, post["id"]))
    assert "chk_no_logo" in codes_now and "chk_no_artwork" not in codes_now
    assert (await _approve(client, auth_headers, post["id"])).status_code == 200


# ---------------- AI backgrounds ----------------


@pytest.fixture
def image_ai(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "SOCIAL_IMAGE_API_KEY", "k")
    monkeypatch.setattr(settings, "SOCIAL_IMAGE_API_BASE_URL", "https://images.test")
    monkeypatch.setattr(settings, "SOCIAL_IMAGE_MODEL", "image-model")
    prompts = []

    async def fake(prompt):
        prompts.append(prompt)
        return jpeg((1024, 1536), (50, 70, 110))

    monkeypatch.setattr(image_provider, "generate_background", fake)
    return prompts


async def test_an_ai_background_is_synthetic_costed_and_only_changes_the_picture(client, auth_headers, storage, image_ai, db_session, organization):
    post = await _post(client, auth_headers)
    await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo", "subline": "From the lab"}, headers=auth_headers)
    first = await client.post(f"{_BASE}/posts/{post['id']}/background", json={"direction": "soft paper texture"}, headers=auth_headers)
    assert first.status_code == 200, first.text
    art = first.json()["artwork"]
    assert art["synthetic_background"] is True and art["background"]["synthetic"] is True and art["ok"] is True
    prompt = image_ai[0]
    assert "no text" in prompt.lower() and "soft paper texture" in prompt and "circuit" in prompt, "the design rules' forbidden visuals are in the prompt"
    assert first.json()["design"]["subline"] == "From the lab", "typography settings are untouched"
    assert "chk_synthetic_background" in _codes(await _check(client, auth_headers, post["id"]))
    asset = (await db_session.execute(select(SocialAsset).where(SocialAsset.kind == "background", SocialAsset.organization_id == organization.id))).scalar_one()
    assert asset.synthetic is True and asset.provenance["model"] == "image-model" and "AI-generated" in asset.alt_text
    usage = (await db_session.execute(select(AIUsage).where(AIUsage.organization_id == organization.id, AIUsage.kind == "image"))).scalars().all()
    assert len(usage) == 1 and float(usage[0].est_cost_inr) == 4.0
    second = (await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)).json()
    assert second["design"]["background_asset_id"] != first.json()["design"]["background_asset_id"]


async def test_an_ai_background_needs_the_photo_template_and_a_configured_provider(client, auth_headers, storage, monkeypatch):
    post = await _post(client, auth_headers)
    await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "editorial"}, headers=auth_headers)
    wrong = await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)
    assert wrong.status_code == 422 and "Photo template" in wrong.text
    await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo", "background_asset_id": (await _upload(client, auth_headers, png((600, 800)))).json()["id"]}, headers=auth_headers)
    off = await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)
    assert off.status_code == 422 and "aren't set up" in off.text
    usage = (await client.get(f"{_BASE}/usage", headers=auth_headers)).json()
    assert usage["image_configured"] is False


async def test_the_budget_stops_image_generation_too(client, auth_headers, storage, image_ai):
    await client.put(f"{_BASE}/settings", json={"budgets": {"monthly_budget_inr": 3, "alert_at_percent": 50}}, headers=auth_headers)
    post = await _post(client, auth_headers)
    picture = (await _upload(client, auth_headers, png((600, 800)))).json()
    await client.put(f"{_BASE}/posts/{post['id']}/design", json={"template": "photo", "background_asset_id": picture["id"]}, headers=auth_headers)
    assert (await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)).status_code == 200  # spends 4 against a budget of 3
    blocked = await client.post(f"{_BASE}/posts/{post['id']}/background", json={}, headers=auth_headers)
    assert blocked.status_code == 422 and "budget" in blocked.text and len(image_ai) == 1


async def test_the_image_provider_only_accepts_inline_image_data(monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import ServiceUnavailableError

    monkeypatch.setattr(settings, "SOCIAL_IMAGE_API_KEY", "k")
    monkeypatch.setattr(settings, "SOCIAL_IMAGE_API_BASE_URL", "https://images.test")
    monkeypatch.setattr(settings, "SOCIAL_IMAGE_MODEL", "m")
    answers = []

    class Response:
        def __init__(self, payload, status=200):
            self.payload, self.status_code = payload, status

        def raise_for_status(self):
            if self.status_code >= 400:
                import httpx

                raise httpx.HTTPStatusError("x", request=None, response=self)

        def json(self):
            return self.payload

    class Http:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            assert url == "https://images.test/v1/images/generations" and headers["Authorization"] == "Bearer k" and json["model"] == "m"
            return answers.pop(0)

    monkeypatch.setattr(image_provider.httpx, "AsyncClient", Http)
    answers.append(Response({"data": [{"b64_json": base64.b64encode(b"imagebytes").decode()}]}))
    assert await image_provider.generate_background("p") == b"imagebytes"
    answers.append(Response({"data": [{"url": "http://169.254.169.254/latest/meta-data"}]}))
    with pytest.raises(ServiceUnavailableError, match="link instead"):
        await image_provider.generate_background("p")
    answers.append(Response({"data": [{"b64_json": "!!!not base64!!!"}]}))
    with pytest.raises(ServiceUnavailableError):
        await image_provider.generate_background("p")
    answers.append(Response({}, status=500))
    with pytest.raises(ServiceUnavailableError, match="500"):
        await image_provider.generate_background("p")


# ---------------- proofreading ----------------


class FakeAI:
    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    async def complete(self, system_prompt, messages, max_tokens=None, temperature=0.7, timeout=None):
        self.calls.append(messages[0].content)
        return AICompletionResult(text=json.dumps(self.answers.pop(0)), model="fake", input_tokens=500, output_tokens=100)


async def test_proofreading_checks_the_words_drawn_on_the_artwork_and_is_costed(client, auth_headers, storage, monkeypatch, db_session, organization):
    post = await _post(client, auth_headers, content={"headline": "Why logs matr", "caption": "c"})
    await _render(client, auth_headers, post["id"], {"template": "editorial", "subline": "Teh basics"})
    fake = FakeAI([{"ok": False, "issues": [{"text": "matr", "suggestion": "matter"}, {"text": "Teh", "suggestion": "The"}]}])
    monkeypatch.setattr(studio, "get_ai_client", lambda: fake)
    response = await client.post(f"{_BASE}/posts/{post['id']}/proofread", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is False and [i["suggestion"] for i in response.json()["issues"]] == ["matter", "The"]
    assert "Why logs matr" in fake.calls[0] and "Teh basics" in fake.calls[0]
    usage = (await db_session.execute(select(AIUsage).where(AIUsage.organization_id == organization.id, AIUsage.kind == "proofread"))).scalars().all()
    assert len(usage) == 1
    stored = (await client.get(f"{_BASE}/posts/{post['id']}", headers=auth_headers)).json()["artwork"]["proofread"]
    assert stored["ok"] is False and stored["fingerprint"]
    monkeypatch.setattr(studio, "get_ai_client", lambda: FakeAI([{"ok": True, "issues": []}]))
    assert (await client.post(f"{_BASE}/posts/{post['id']}/proofread", headers=auth_headers)).json() == {"ok": True, "issues": [], "current": True}


async def test_proofreading_a_carousel_without_slides_explains_what_is_missing(client, auth_headers, storage):
    post = await _post(client, auth_headers, format="carousel", content={"headline": "h", "caption": "c"})
    response = await client.post(f"{_BASE}/posts/{post['id']}/proofread", headers=auth_headers)
    assert response.status_code == 422 and "carousel" in response.text.lower()


# ---------------- the grid, end to end ----------------


async def test_the_grid_shows_designed_posts_pins_the_one_being_approved_and_says_what_is_missing(client, auth_headers, storage):
    ids = []
    for i, template in enumerate(["editorial", "editorial", "statement"]):
        post = await _post(client, auth_headers, title=f"Post {i}", content={"headline": f"Distinct headline number {i}", "caption": f"Caption {i} is unique."})
        await _render(client, auth_headers, post["id"], {"template": template})
        ids.append(post["id"])
    await _post(client, auth_headers, title="No artwork yet")
    data = (await client.get(f"{_BASE}/grid", headers=auth_headers)).json()
    assert len(data["tiles"]) == 3 and data["missing"] == 6 and data["live_available"] is False
    assert all(t["url"].startswith("https://files.test/") for t in data["tiles"])
    assert {f["code"] for f in data["findings"]} >= {"grid_same_look", "grid_live_unavailable"}
    assert data["verdict"] == "review" and "not the complete grid" in data["note"]
    focused = (await client.get(f"{_BASE}/grid?post_id={ids[0]}", headers=auth_headers)).json()
    assert focused["tiles"][0]["post_id"] == ids[0] and focused["tiles"][0]["is_focus"] is True
    assert (await client.get(f"{_BASE}/grid?post_id={uuid.uuid4()}", headers=auth_headers)).status_code == 200


async def test_an_empty_grid_says_there_is_not_enough_to_judge(client, auth_headers, storage):
    data = (await client.get(f"{_BASE}/grid", headers=auth_headers)).json()
    assert data["tiles"] == [] and data["verdict"] == "not_enough" and data["missing"] == 9
