"""
Composition library: genuinely different layouts for a cover, drawn in code from the post's own words.

    poster     a big flat circle with the topic icon (drawn by render.py itself)
    stat       a giant figure with its label ("10  second check")
    checklist  stacked rows with ticks, one for each step of the post
    compare    two panels side by side, "this" vs "that"
    flow       connected numbered nodes, one for each step
    question   an oversized question mark for a question headline

Each composition decides where the headline may sit (`y_head` to `limit`) and draws its own artwork in the rest of the picture. All
shapes are flat colour. Nothing here is generated or fetched: this is Phase 1, with the art slot of each layout filled by code.
`layout()` returns None when a composition cannot be drawn well (a label that will not fit); the caller then draws the poster.
"""

from dataclasses import dataclass
from typing import Callable

from PIL import ImageDraw

from modules.social_media import art_direction

INK = (8, 12, 10)
WHITE = (250, 252, 248)


@dataclass
class Tone:
    text: tuple[int, int, int]  # plain text on the picture's own background
    card: tuple[int, int, int]  # fill of a card or panel
    card_text: tuple[int, int, int]
    hi: tuple[int, int, int]  # the highlight colour
    on_hi: tuple[int, int, int]
    line: tuple[int, int, int]
    deco: tuple[int, int, int]  # large decorative shapes and figures
    badge: tuple[int, int, int]
    on_badge: tuple[int, int, int]
    glyph: tuple[int, int, int] = (0, 0, 0)  # the oversized question mark
    outlined: bool = False  # cards on a light picture get a fine outline


@dataclass
class Geo:
    w: int
    h: int
    y: int  # where the text may start (below the label)
    clear: int  # the lowest y that art may reach (above the logo)
    template: str
    seed: int


@dataclass
class Layout:
    y_head: int
    limit: int  # the lowest y the headline and its line may reach
    biggest: int  # the largest headline size
    draw: Callable[[], None]  # draws the art (before the text)


def tone_for(R, template: str, palette, seed: int) -> Tone | None:
    flat = R._flat_colour(palette, seed)
    if template in ("neon", "statement"):
        hi = (palette.accent, palette.accent2)[(seed // 2) % 2]
        return Tone((238, 242, 240), (26, 32, 30), (238, 242, 240), hi, INK, (74, 84, 80), hi, WHITE, INK, glyph=hi)
    if template == "split":
        hi = palette.accent if flat != palette.accent else palette.accent2
        return Tone(INK, INK, WHITE, hi, INK, INK, INK, INK, WHITE, glyph=hi)
    if template == "solid":
        return Tone(INK, INK, WHITE, WHITE, INK, INK, INK, INK, WHITE, glyph=WHITE)
    if template == "editorial":
        return Tone(palette.ink, (255, 255, 255), palette.ink, palette.accent, INK, (206, 214, 208), palette.primary, INK, WHITE, glyph=palette.accent, outlined=True)
    return None  # photo and screenshot have their own layouts


def layout(R, ctx, spec, geo: Geo, slides: list[dict] | None = None) -> Layout | None:
    """The layout of a composition, or None for the poster, an unknown name, or a composition that cannot be drawn well here."""
    tone = tone_for(R, geo.template, ctx.palette, geo.seed)
    if tone is None or spec.composition in ("", "poster"):
        return None
    builder = {"stat": _stat, "checklist": _checklist, "compare": _compare, "flow": _flow, "question": _question}.get(spec.composition)
    if builder is None:
        return None
    try:
        return builder(R, ctx, spec, geo, tone)
    except R.RenderError:
        return None


def _centered(R, ctx, fitted, cx: int, y: int, preferred, role: str = "art") -> None:
    """A fitted block with every line centred on cx."""
    face = R.font(fitted.size, fitted.weight)
    for i, line in enumerate(fitted.lines):
        width = int(face.getlength(line))
        one = R.Fitted([line], fitted.size, fitted.weight, fitted.line_height)
        R._draw_block(ctx, one, cx - width // 2, y + i * fitted.line_height, preferred, role, width)


def _tick(ctx, cx: int, cy: int, r: int, colour) -> None:
    ctx.draw.line((cx - r * 0.45, cy + r * 0.02, cx - r * 0.1, cy + r * 0.38, cx + r * 0.5, cy - r * 0.34), fill=colour, width=max(6, r // 4), joint="curve")


# ---------------- stat ----------------


def _stat(R, ctx, spec, g: Geo, tone: Tone) -> Layout | None:
    if not spec.figure:
        return None
    inner = g.w - 2 * R.MARGIN
    size = 400
    face = R.font(size, 900)
    box = face.getbbox(spec.figure)
    while (box[2] - box[0]) > inner * 0.58 and size > 220:
        size -= 20
        face = R.font(size, 900)
        box = face.getbbox(spec.figure)
    fw, fh = box[2] - box[0], box[3] - box[1]
    label_x = R.MARGIN + fw + 40
    label_w = g.w - R.MARGIN - label_x
    label = None
    below = False
    if spec.figure_label:
        if label_w >= 220:
            label = R.fit(spec.figure_label, label_w, int(fh * 0.55), 72, 34, 800, 3, 1.08, "figure label")
        else:
            below = True
            label = R.fit(spec.figure_label, inner, 90, 60, 34, 800, 1, 1.1, "figure label")
    y_fig = g.y + 4
    art_bottom = y_fig + fh + ((label.height + 18) if (label and below) else 0)
    figure_colour = tone.deco

    def draw():
        ctx.draw.text((R.MARGIN - box[0], y_fig - box[1]), spec.figure, font=face, fill=figure_colour)
        if label:
            if below:
                R._draw_block(ctx, label, R.MARGIN, y_fig + fh + 18, tone.text, "art", inner)
            else:
                R._draw_block(ctx, label, label_x, y_fig + fh - label.height, tone.text, "art", label_w)

    return Layout(art_bottom + 44, g.clear, 112, draw)


# ---------------- checklist ----------------

ROW_GAP = 16


def _checklist(R, ctx, spec, g: Geo, tone: Tone) -> Layout | None:
    items = list(spec.items)[:5]
    if len(items) < 3:
        return None
    inner = g.w - 2 * R.MARGIN
    ROW_H = 104 if len(items) <= 4 else 86  # five rows are a little slimmer so every step the post lists fits
    total = len(items) * ROW_H + (len(items) - 1) * ROW_GAP
    top = g.clear - total
    fitted = [R.fit(item, inner - 150, ROW_H - 40, 40, 28, 700, 1, 1.1, "checklist item") for item in items]

    def draw():
        for i, lab in enumerate(fitted):
            ry = top + i * (ROW_H + ROW_GAP)
            ctx.draw.rounded_rectangle((R.MARGIN, ry, g.w - R.MARGIN, ry + ROW_H), radius=30, fill=tone.card, outline=tone.line if tone.outlined else None, width=2)
            cx, cy = R.MARGIN + 62, ry + ROW_H // 2
            ctx.draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=tone.hi)
            _tick(ctx, cx, cy, 30, tone.on_hi)
            R._draw_block(ctx, lab, R.MARGIN + 116, cy - lab.height // 2, tone.card_text, "art", inner - 150)

    return Layout(g.y + 6, top - 44, 128, draw)


# ---------------- compare ----------------

PANEL_H = 360


def _compare(R, ctx, spec, g: Geo, tone: Tone) -> Layout | None:
    left, right = art_direction.versus_of(spec.headline)
    if not left:
        return None
    inner = g.w - 2 * R.MARGIN
    gap = 28
    pw = (inner - gap) // 2
    top = g.clear - PANEL_H
    a = R.fit(left, pw - 120, 230, 68, 36, 800, 3, 1.06, "panel label")  # the VS badge sits over the inner edge of both panels
    b = R.fit(right, pw - 120, 230, 68, 36, 800, 3, 1.06, "panel label")
    lx, rx = R.MARGIN, R.MARGIN + pw + gap

    def draw():
        ctx.draw.rounded_rectangle((lx, top, lx + pw, top + PANEL_H), radius=40, fill=tone.card, outline=tone.line if tone.outlined else None, width=2)
        ctx.draw.rounded_rectangle((rx, top, rx + pw, top + PANEL_H), radius=40, fill=tone.hi)
        R._draw_block(ctx, a, lx + 36, top + (PANEL_H - a.height) // 2, tone.card_text, "art", pw - 120)
        R._draw_block(ctx, b, rx + 84, top + (PANEL_H - b.height) // 2, tone.on_hi, "art", pw - 120)
        cx, cy = g.w // 2, top + PANEL_H // 2
        ctx.draw.ellipse((cx - 54, cy - 54, cx + 54, cy + 54), fill=tone.badge)
        vs = R.Fitted(["VS"], 40, 800, 44)
        tw = int(R.font(40, 800).getlength("VS"))
        R._draw_block(ctx, vs, cx - tw // 2, cy - 22, tone.on_badge, "art", tw)  # the text box stays inside the badge

    return Layout(g.y + 6, top - 44, 124, draw)


# ---------------- flow ----------------


def _flow(R, ctx, spec, g: Geo, tone: Tone) -> Layout | None:
    items = list(spec.items)
    if not 3 <= len(items) <= 4:
        return None  # more steps than nodes fit: a half list would mislead, so the poster is drawn instead
    n = len(items)
    inner = g.w - 2 * R.MARGIN
    d = 124
    span = (inner - d) // (n - 1)
    label_w = span - 20
    labels = [R.fit(item, label_w, 112, 34, 26, 700, 3, 1.12, "flow label") for item in items]
    art_h = d + 26 + max(lab.height for lab in labels)
    top = g.clear - art_h
    cy = top + d // 2
    centres = [R.MARGIN + d // 2 + i * span for i in range(n)]

    def draw():
        for i in range(n - 1):
            x0, x1 = centres[i] + d // 2 + 10, centres[i + 1] - d // 2 - 10
            ctx.draw.line((x0, cy, x1, cy), fill=tone.deco, width=6)
            ctx.draw.line((x1 - 20, cy - 16, x1, cy, x1 - 20, cy + 16), fill=tone.deco, width=6, joint="curve")
        for i, cx in enumerate(centres):
            ctx.draw.ellipse((cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2), fill=tone.hi, outline=tone.line if tone.outlined else None, width=2)
            num = R.Fitted([str(i + 1)], 60, 800, 64)
            nw = int(R.font(60, 800).getlength(str(i + 1)))
            R._draw_block(ctx, num, cx - nw // 2, cy - 32, tone.on_hi, "art", nw)
            _centered(R, ctx, labels[i], cx, top + d + 26, tone.text)

    return Layout(g.y + 6, top - 44, 124, draw)


# ---------------- question ----------------


def _question(R, ctx, spec, g: Geo, tone: Tone) -> Layout | None:
    if not spec.headline.strip().endswith("?"):
        return None
    size = 780
    face = R.font(size, 900)
    box = face.getbbox("?")
    fw, fh = box[2] - box[0], box[3] - box[1]
    x = g.w - fw + 70 - box[0]
    bottom = g.h - 150
    y_top = bottom - fh

    def draw():
        ctx.draw.text((x, y_top - box[1]), "?", font=face, fill=tone.glyph)

    return Layout(g.y + 6, y_top - 30, 124, draw)
