"""
The approved React Email templates.

A developer (or coding agent) writes a React Email component in `apps/email-code-templates/`, it is reviewed and merged like any
other code, and `npm run build` there renders each component to plain HTML in this folder, with every property left as a
`{{prop:name}}` token and every ERPX value as an ordinary `{{placeholder}}`. The API only reads those files: it never runs JSX,
JavaScript or anything uploaded, so the Python service needs no Node.

Administrators edit a template through the properties it declares in `manifest.json`, not its source.
"""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent
_KEY = re.compile(r"^[a-z][a-z0-9_]{1,60}$")


class CodeTemplateError(ValueError):
    """An unknown or unusable approved template. Shown to the admin as is."""


@dataclass(frozen=True)
class CodeProp:
    name: str
    label: str
    type: str  # text | textarea | url | color
    default: str
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class CodeTemplate:
    key: str
    name: str
    description: str
    category: str
    module: str | None
    suggested_for: str | None  # the ERPX email (a key of the built-in list) it is written to replace
    subject: str
    props: tuple[CodeProp, ...]
    html: str
    placeholders: tuple[str, ...] = field(default_factory=tuple)

    @property
    def prop_names(self) -> set[str]:
        return {p.name for p in self.props}

    def default_props(self) -> dict[str, str]:
        return {p.name: p.default for p in self.props}


@lru_cache(maxsize=1)
def _load() -> dict[str, CodeTemplate]:
    manifest_path = _DIR / "manifest.json"
    if not manifest_path.exists():
        return {}
    items = json.loads(manifest_path.read_text(encoding="utf-8"))
    found: dict[str, CodeTemplate] = {}
    for item in items:
        key = item["key"]
        if not _KEY.match(key):
            continue
        html = (_DIR / f"{key}.html").read_text(encoding="utf-8")
        found[key] = CodeTemplate(
            key=key,
            name=item["name"],
            description=item.get("description", ""),
            category=item.get("category", "Custom Emails"),
            module=item.get("module"),
            suggested_for=item.get("suggested_for"),
            subject=item.get("subject", ""),
            props=tuple(
                CodeProp(p["name"], p.get("label", p["name"]), p.get("type", "text"), str(p.get("default", "")), bool(p.get("required", False)), p.get("description", ""))
                for p in item.get("props", [])
            ),
            html=html,
            placeholders=tuple(item.get("placeholders", [])),
        )
    return found


def list_code_templates() -> list[CodeTemplate]:
    return list(_load().values())


def load_code_template(key: str) -> CodeTemplate:
    found = _load().get(key)
    if found is None:
        raise CodeTemplateError("That approved template is not available.")
    return found
