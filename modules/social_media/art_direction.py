"""
The creative brief of a post: what the picture should be about and how it is composed.

A brief has a concept (one sentence), a visual metaphor, a composition (the layout family), a focus (a key figure or term) and a
few short items (the steps or points the picture may show). The AI proposes one; if it sends none, or a poor one, a brief is derived
from the post's own words, so the pipeline never depends on the AI having answered well.

Precedence when a look is chosen: 1. the brand's restrictions (its forbidden visuals), 2. whether the topic suits a composition,
3. the theme preference (rotation, the planner's choice). A person can always override by hand.

Phase 1: only code-drawn compositions exist. `imagery` is "none" for all of them; generated imagery arrives in a later phase.
"""

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

COMPOSITIONS = ("poster", "stat", "checklist", "compare", "flow", "question")
IMAGERY = ("none", "illustration", "background")
MAX_ITEMS = 5

_STEP = re.compile(r"^(?:step\s*)?(\d{1,2})\s*[:.)–-]\s*(\S.*)$", re.I)
_VS = re.compile(r"\s+(?:vs\.?|versus)\s+", re.I)
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3})(?:[-\s]?)([A-Za-z][A-Za-z-]{1,24}(?:\s+[A-Za-z-]{2,24})?)?")
_PROCESS = re.compile(r"\b(life.?cycle|process|phases?|stages?|pipeline|workflow|flow|kill chain|how .{2,40} works)\b", re.I)


def _text(value: Any, limit: int) -> str:
    """Anything an AI might send for a text field, as a clean string (a list is joined, anything odd is empty)."""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value if isinstance(v, (str, int, float)))
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


class ArtBrief(BaseModel):
    concept: str = Field(default="", max_length=240)
    metaphor: str = Field(default="", max_length=120)
    composition: str = ""
    focus: str = Field(default="", max_length=40)
    items: list[str] = Field(default_factory=list, max_length=MAX_ITEMS)
    imagery: str = "none"

    @field_validator("concept", mode="before")
    @classmethod
    def _concept(cls, value):
        return _text(value, 240)

    @field_validator("metaphor", mode="before")
    @classmethod
    def _metaphor(cls, value):
        return _text(value, 120)

    @field_validator("focus", mode="before")
    @classmethod
    def _focus(cls, value):
        return _text(value, 40)

    @field_validator("composition", mode="before")
    @classmethod
    def _composition(cls, value):
        value = _text(value, 20).lower()
        return value if value in COMPOSITIONS else ""

    @field_validator("imagery", mode="before")
    @classmethod
    def _imagery(cls, value):
        value = _text(value, 20).lower()
        return value if value in IMAGERY else "none"

    @field_validator("items", mode="before")
    @classmethod
    def _items(cls, value):
        if not isinstance(value, list):
            return []
        out = [_text(v, 40) for v in value]
        return [v for v in out if v][:MAX_ITEMS]


def lenient(raw: Any) -> ArtBrief:
    """A brief from whatever the AI (or an editor) sent; anything unusable becomes an empty brief."""
    if isinstance(raw, ArtBrief):
        return raw
    if not isinstance(raw, dict):
        return ArtBrief()
    try:
        return ArtBrief.model_validate(raw)
    except Exception:  # noqa: BLE001 - a poor brief must never cost a draft
        return ArtBrief()


# ---------------- what the post itself offers ----------------


def short_label(text: str, limit: int = 34) -> str:
    """A heading as a short label: the first clause, cut at a word boundary, never ending in a dangling word."""
    text = " ".join(text.split())
    text = re.split(r"\s[:–—-]\s|:\s", text, maxsplit=1)[0] if len(text) > limit else text
    if len(text) <= limit:
        return text.rstrip(" ,;:.")
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.&")


def items_of(slides: list[dict], brief: ArtBrief | None = None) -> list[str]:
    """The points the picture may list: the brief's own items, else the slides' headings without their step numbers."""
    if brief and brief.items:
        return brief.items[:MAX_ITEMS]
    headings = [" ".join(str(s.get("heading", "")).split()) for s in slides or []]
    if numbered_steps(slides) >= 3:
        headings = [h for h in headings if _STEP.match(h)]  # a list of steps lists the steps, not the takeaway
    elif len(headings) > MAX_ITEMS:
        headings = headings[:-1] if len(headings) <= MAX_ITEMS + 1 else headings  # the last slide is usually the takeaway
    out: list[str] = []
    for heading in headings:
        match = _STEP.match(heading)
        label = short_label(match.group(2) if match else heading)
        if label and label.lower() not in {o.lower() for o in out}:
            out.append(label)
    return out[:MAX_ITEMS]


def numbered_steps(slides: list[dict]) -> int:
    return sum(1 for s in slides or [] if _STEP.match(" ".join(str(s.get("heading", "")).split())))


_FILLER = {"that", "to", "for", "of", "the", "a", "an", "and", "in", "on", "with", "you", "your", "your", "is", "are", "can", "will", "by", "at", "from", "or"}


def _clean_label(label: str) -> str:
    """A figure's label without the filler words that follow it in the sentence ("habits that" -> "habits")."""
    words = [w for w in label.replace("-", " ").split()]
    while words and words[-1].lower() in _FILLER:
        words.pop()
    if words and words[0].lower() in _FILLER:
        return ""
    return " ".join(words[:2])


def figure_of(headline: str, slides: list[dict], brief: ArtBrief | None = None) -> tuple[str, str]:
    """(figure, label) for the "stat" composition: a number the post really states, else the real count of numbered steps."""
    if brief and brief.focus:
        match = re.match(r"^(\d{1,3})\s*(.*)$", brief.focus)
        if match:
            return match.group(1), _clean_label(match.group(2))
    match = _NUMBER.search(headline or "")
    if match:
        return match.group(1), _clean_label(match.group(2) or "")
    steps = numbered_steps(slides)
    if steps >= 3:
        return str(steps), "steps"
    return "", ""


def versus_of(headline: str) -> tuple[str, str]:
    parts = _VS.split(headline or "", maxsplit=1)
    if len(parts) != 2:
        return "", ""
    left, right = (short_label(p.strip(" ?!.:"), 26) for p in parts)
    return (left, right) if left and right else ("", "")


# ---------------- which compositions suit this post ----------------


def suitable(composition: str, headline: str, slides: list[dict], brief: ArtBrief | None = None, post_format: str = "image") -> bool:
    items = items_of(slides, brief)
    if composition == "poster":
        return True
    if composition == "stat":
        figure = figure_of(headline, slides, brief)[0]
        # a headline that already starts with the number ("5 habits that ...") would only repeat it
        return bool(figure) and not (headline or "").lstrip().startswith(figure)
    if composition == "checklist":
        return 3 <= len(items) <= MAX_ITEMS
    if composition == "compare":
        return bool(versus_of(headline)[0])
    if composition == "flow":
        return 3 <= len(items) <= 4 and (numbered_steps(slides) >= 3 or bool(_PROCESS.search(headline or "")))
    if composition == "question":
        return (headline or "").strip().endswith("?")
    return False


# Topic-driven preference when the AI suggests nothing usable: the most specific layout first.
_PREFERENCE = ("compare", "stat", "flow", "checklist", "question", "poster")


def choose(
    headline: str,
    slides: list[dict],
    brief: ArtBrief | None = None,
    recent: list[str] | None = None,
    post_format: str = "image",
) -> str:
    """The composition to draw. Topic suitability decides what is possible; the AI's suggestion wins among the possible ones; a
    layout is not repeated back to back, and otherwise the one used least recently wins, the more specific layout first on a tie."""
    recent = [r for r in (recent or []) if r in COMPOSITIONS]
    possible = [c for c in COMPOSITIONS if suitable(c, headline, slides, brief, post_format)]
    last = recent[0] if recent else None
    wanted = brief.composition if brief and brief.composition in possible else ""
    if wanted and wanted != last:
        return wanted
    pool = [c for c in _PREFERENCE if c in possible and c != last] or [c for c in _PREFERENCE if c in possible]

    def age(c: str) -> int:
        return recent.index(c) if c in recent else len(recent) + 5  # larger = longer ago (or never)

    oldest = max(age(c) for c in pool)
    tied = [c for c in pool if age(c) == oldest]  # still in order of how specific the layout is
    return tied[0]


def resolve(headline: str, slides: list[dict], brief: ArtBrief | None = None, post_format: str = "image") -> str:
    """The composition to draw now: the stored brief's, if the post still suits it; otherwise the best one for the post as it is."""
    if brief and brief.composition and suitable(brief.composition, headline, slides, brief, post_format):
        return brief.composition
    return choose(headline, slides, brief, [], post_format)


def derive(headline: str, slides: list[dict], support_line: str = "", icon_hint: str = "") -> ArtBrief:
    """A brief made only from the post's own words, with no AI: used when none was sent."""
    figure, label = figure_of(headline, slides)
    brief = ArtBrief(
        concept=(support_line or headline)[:240],
        metaphor=icon_hint,
        focus=(f"{figure} {label}".strip() if figure else ""),
        items=items_of(slides),
    )
    return brief


def finalise(
    raw: Any,
    headline: str,
    slides: list[dict],
    support_line: str = "",
    recent: list[str] | None = None,
    post_format: str = "image",
    icon_hint: str = "",
) -> ArtBrief:
    """The brief that is stored with the post: the AI's, completed from the post's words, with a composition that suits the topic."""
    brief = lenient(raw)
    base = derive(headline, slides, support_line, icon_hint)
    brief.concept = brief.concept or base.concept
    brief.metaphor = brief.metaphor or base.metaphor
    brief.focus = brief.focus or base.focus
    brief.items = brief.items or base.items
    brief.imagery = "none"  # Phase 1: only code-drawn compositions
    brief.composition = choose(headline, slides, brief, recent, post_format)
    return brief


# ---------------- the brand's restrictions come first ----------------

_THEME_BANS = {
    "neon": ("neon", "glow", "circuit"),
}


def theme_allowed(template: str, rules: dict | None) -> bool:
    """False if the brand's forbidden visuals rule this theme out of an automatic choice. A person can still pick it by hand."""
    words = _THEME_BANS.get(template)
    if not words or not rules:
        return True
    forbidden = " ".join(str(v).lower() for v in (rules.get("forbidden_visuals") or []))
    return not any(w in forbidden for w in words)

