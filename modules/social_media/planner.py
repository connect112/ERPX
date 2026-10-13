"""
Deciding the format and the look of a post, so the feed doesn't become the same post over and over.

Two decisions are made for each new post, from the topic and from what the account posted recently:

- the format: an explainer, a how-to or a career topic reads best as a carousel (people swipe and save); a one-line alert or a
  single idea fits one strong image. If the last posts all used the same format, the other one is chosen.
- the look: of the templates that need no extra picture (light "editorial", dark "statement", the brand-dark "neon", a colour
  panel over dark "split", and the full-colour "solid"), the one not used for the longest time, and never the same as the previous
  post. Neon, split and solid also change their pattern or colour and the text position from post to post on their own. A logo that
  brings its own black background melts into the dark looks and sits on a black badge on the light and colour ones.

It is plain rules, not AI, so it costs nothing, gives the same answer for the same history, and always says why. A person can
override both choices.
"""

import re
import uuid
from dataclasses import dataclass, asdict

from sqlalchemy.ext.asyncio import AsyncSession

from modules.social_media.history import HistoryService

TEMPLATES = ("neon", "statement", "split", "solid", "editorial")  # the ones that need no picture
FORMATS = ("carousel", "image")
LOOKBACK = 8

_EXPLAINER = re.compile(r"\b(what is|what are|how (do|does|to|can)|why|explained|explain|vs\.?|versus|difference|guide|basics|beginner|steps|step by step|checklist|mistakes|tips?|roadmap|lifecycle|phases?|types of|ways to)\b", re.I)
_ALERT = re.compile(r"\bcve-\d+|\b(vulnerab\w*|breach\w*|zero[- ]day|ransomware|patch\w*|exploit\w*|advisor(y|ies)|kev|outage|leak\w*|attack on|incident)\b", re.I)
_CAREER = re.compile(r"\b(career|job|jobs|interview|resume|cv|certification|certified|skills|become a|path)\b", re.I)


def classify(topic: str, notes: str = "") -> str:
    text = f"{topic} {notes}"
    if _ALERT.search(text):
        return "alert"
    if _CAREER.search(text):
        return "career"
    if _EXPLAINER.search(text):
        return "explainer"
    return "general"


@dataclass
class Plan:
    format: str
    template: str
    topic_kind: str
    reason: str
    recent_formats: list[str]
    recent_templates: list[str]


def decide(topic: str, notes: str, recent: list[dict], logo_on_dark: bool = False) -> Plan:
    """`recent` is the newest-first list of {"format", "template"} for the account's latest feed posts."""
    kind = classify(topic, notes)
    formats = [r["format"] for r in recent if r.get("format") in FORMATS][:LOOKBACK]
    templates = [r["template"] for r in recent if r.get("template") in TEMPLATES][:LOOKBACK]
    reasons: list[str] = []

    # ---- format ----
    preferred = {"explainer": "carousel", "career": "carousel", "alert": "image"}.get(kind)
    if preferred is None:
        # nothing about the topic decides it: use whichever format was used less in the last posts
        preferred = "carousel" if formats.count("carousel") <= formats.count("image") else "image"
        reasons.append("The topic doesn't point to a format, so " + ("a carousel" if preferred == "carousel" else "a single image") + " was chosen because it was used less recently.")
    else:
        why = {"explainer": "an explainer is easier to follow and save as a carousel", "career": "a career topic works best as a carousel people can save", "alert": "a short alert reads best as one strong image"}[kind]
        reasons.append(f"This looks like {'an' if kind in ('explainer', 'alert') else 'a'} {kind} topic: {why}.")
    chosen = preferred
    if len(formats) >= 2 and formats[0] == formats[1] == preferred:
        chosen = "image" if preferred == "carousel" else "carousel"
        reasons.append(f"The last two posts were already {'carousels' if preferred == 'carousel' else 'single images'}, so {'a single image with the answer on it' if chosen == 'image' else 'a carousel'} gives the feed some variety.")

    # ---- look ----
    last = templates[0] if templates else None
    candidates = list(TEMPLATES)
    if kind == "alert":
        candidates = ["statement", "solid", "split"]  # high contrast, quick to read
    ranked = []
    for t in candidates:
        since = templates.index(t) if t in templates else len(templates) + 5  # larger = longer ago (or never)
        ranked.append((since, -TEMPLATES.index(t), t))
    ranked.sort(reverse=True)
    template = next((t for _, _, t in ranked if t != last), ranked[0][2])
    if not templates:
        reasons.append(f"There are no earlier posts to compare with, so the {template} look was chosen.")
    else:
        used = templates.index(template) if template in templates else None
        noun = lambda n: f"{n} post" + ("" if n == 1 else "s")  # noqa: E731
        reasons.append(
            f"The {template} look was chosen because it hasn't been used {'in the last ' + noun(len(templates)) if used is None else 'for ' + noun(used)}"
            + (f" and the last post used {last}." if last else ".")
        )
    return Plan(chosen, template, kind, " ".join(reasons), formats[:4], templates[:4])


class Planner:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def recent(self, organization_id: uuid.UUID) -> list[dict]:
        rows = await HistoryService(self.db).recent(organization_id, limit=LOOKBACK * 2)
        return [{"format": p.format, "template": (p.design or {}).get("template") or "editorial"} for p in rows if p.format in FORMATS]

    async def plan(self, organization_id: uuid.UUID, topic: str, notes: str = "", logo_on_dark: bool = False) -> dict:
        return asdict(decide(topic, notes, await self.recent(organization_id), logo_on_dark))
