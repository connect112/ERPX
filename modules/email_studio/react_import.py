"""
Importing React Email source code into Email Studio -- without ever running it.

The pasted TSX/JSX is only *read*: it is parsed into a syntax tree (tree-sitter) and walked by the small interpreter below, which
understands exactly this much and nothing more:

* imports from ``@react-email/components`` (and ``react``), nothing else;
* fixed values: strings, numbers, booleans, objects (style objects), lists, constants declared in the file;
* a component function that returns JSX, other components in the same file, and ``list.map(item => <.../>)`` over a fixed list;
* the React Email components below, a safe subset of plain HTML tags, ``style`` objects and (inside ``<Tailwind>``) ``className``.

Any other statement or expression -- a call, ``new``, ``await``, ``import()``, ``require``, ``eval``, ``process.env`` reads that
matter, event handlers, ``dangerouslySetInnerHTML``, ``<script>`` -- is *refused with the line it is on and a reason*. Nothing the
author wrote is ever compiled or executed on the server or in the browser; the email HTML is produced by this module's own code
and then passes through the same sanitiser as every other email (``sanitize.py``).

The result is the email as HTML (still holding ``{{placeholders}}``), its plain-text twin, and a list of errors and warnings with
line numbers. Warnings cover everything that was changed or left out so that nothing disappears silently.
"""

import html as html_lib
import re
from dataclasses import dataclass, field
from typing import Any, NamedTuple

import tree_sitter_typescript as _ts
from tree_sitter import Language, Parser

from modules.email_studio import tailwind
from modules.email_studio.placeholders import placeholders_in
from modules.email_studio.sanitize import _clean_style, html_to_text, sanitize_document

MAX_SOURCE_CHARS = 200_000
MAX_STEPS = 300_000
MAX_LOOP = 200
MAX_DEPTH = 60
MAX_ELEMENTS = 6_000
MAX_ISSUES = 60

_LANGUAGE = Language(_ts.language_tsx())

SUPPORTED_COMPONENTS = ("Html", "Head", "Preview", "Body", "Container", "Section", "Row", "Column", "Heading", "Text", "Button", "Link", "Img", "Hr", "Tailwind")
_IGNORED_COMPONENTS = ("Font",)
_PRESETS = ("pixelBasedPreset",)  # values (not components) that only configure <Tailwind>  # web fonts do not survive email clients; the font stack falls back
_ALLOWED_IMPORTS = {"react": None, "@react-email/components": set(SUPPORTED_COMPONENTS) | set(_IGNORED_COMPONENTS),
                    "react-email": set(SUPPORTED_COMPONENTS) | set(_IGNORED_COMPONENTS), "@react-email/tailwind": {"Tailwind"},
                    "@react-email/html": {"Html"}, "@react-email/head": {"Head"}, "@react-email/preview": {"Preview"}, "@react-email/body": {"Body"},
                    "@react-email/container": {"Container"}, "@react-email/section": {"Section"}, "@react-email/row": {"Row"}, "@react-email/column": {"Column"},
                    "@react-email/heading": {"Heading"}, "@react-email/text": {"Text"}, "@react-email/button": {"Button"}, "@react-email/link": {"Link"},
                    "@react-email/img": {"Img"}, "@react-email/hr": {"Hr"}}
_PLAIN_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "center", "code", "col", "colgroup", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img",
    "li", "ol", "p", "pre", "s", "small", "span", "strike", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
_FORBIDDEN_TAGS = {
    "script": "scripts never run in an email", "iframe": "frames are blocked by every email client", "object": "plug-ins are blocked", "embed": "plug-ins are blocked",
    "form": "forms do not work in email", "input": "forms do not work in email", "button": "use the <Button> component for a link that looks like a button",
    "textarea": "forms do not work in email", "select": "forms do not work in email", "svg": "SVG is not supported by most email clients; use an image address",
    "video": "video does not play in most email clients", "audio": "audio does not play in most email clients", "canvas": "scripts never run in an email",
    "link": "external resources are not loaded", "base": "it changes every link in the page", "noscript": "scripts never run in an email",
}
_BARE_AMPERSAND = re.compile(r"(?<!&)&(?!&)(?![#A-Za-z0-9]+;)")
_UNITLESS = {"line-height", "font-weight", "opacity", "z-index", "flex", "order", "zoom", "orphans", "widows", "flex-grow", "flex-shrink"}
_ATTR_RENAME = {"className": "class", "colSpan": "colspan", "rowSpan": "rowspan", "cellPadding": "cellpadding", "cellSpacing": "cellspacing", "bgColor": "bgcolor", "vAlign": "valign"}
_PLAIN_ATTRS = {"href", "target", "src", "alt", "width", "height", "align", "valign", "colspan", "rowspan", "cellpadding", "cellspacing", "border", "bgcolor", "role", "dir", "lang", "title"}
_HINTS = {
    "Date": "The date changes every time the email is sent, so it cannot be fixed here. For the year use {{current_year}}.",
    "process": "Environment variables do not exist in an email template. Write the final value into the file.",
    "window": "There is no browser when an email is built.",
    "document": "There is no browser when an email is built.",
    "Math": "Calculations are not run. Write the final value.",
    "JSON": "Data conversion is not run. Write the final value.",
    "require": "Other files cannot be loaded. Paste what you need into this file.",
}

UNDEF = object()  # JavaScript's undefined


class _Point(NamedTuple):
    row: int
    column: int


class N:
    """A syntax-tree node copied out of tree-sitter into plain Python, so nothing here depends on the parser's memory staying valid."""

    __slots__ = ("type", "start_byte", "end_byte", "start_point", "is_named", "is_missing", "has_error", "children", "fields")

    def __init__(self, kind: str, start: int, end: int, point: _Point, named: bool, missing: bool, error: bool):
        self.type, self.start_byte, self.end_byte, self.start_point = kind, start, end, point
        self.is_named, self.is_missing, self.has_error = named, missing, error
        self.children: list["N"] = []
        self.fields: dict[str, "N"] = {}

    @property
    def named_children(self) -> list["N"]:
        return [c for c in self.children if c.is_named]

    def child_by_field_name(self, name: str) -> "N | None":
        return self.fields.get(name)


def _copy_tree(node: Any) -> N:
    """Copy the parse tree into plain Python objects, reading each node's values straight away. Nothing from tree-sitter is kept."""
    point = node.start_point
    copy = N(node.type, node.start_byte, node.end_byte, _Point(point.row, point.column), node.is_named, node.is_missing, node.has_error)
    for index in range(node.child_count):
        child = node.child(index)
        made = _copy_tree(child)
        copy.children.append(made)
        name = node.field_name_for_child(index)
        if name and name not in copy.fields:
            copy.fields[name] = made
    return copy


@dataclass
class Issue:
    severity: str  # error | warning
    message: str
    line: int | None = None
    column: int | None = None
    code: str = "unsupported"
    more_lines: list[int] = field(default_factory=list)  # the same problem again on these lines


@dataclass
class BuildResult:
    ok: bool
    html: str = ""
    text: str = ""
    title: str = ""
    preheader: str = ""
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    props_used: dict[str, str] = field(default_factory=dict)


class Bad(Exception):
    """The source does something this importer does not read. Carries where, and why."""

    def __init__(self, message: str, node: N | None = None, code: str = "unsupported"):
        super().__init__(message)
        self.message, self.node, self.code = message, node, code


@dataclass
class El:
    kind: str  # html head preview body container section row column heading text button link img hr tag font
    tag: str = ""
    attrs: dict[str, str] = field(default_factory=dict)
    style: dict[str, str] = field(default_factory=dict)
    children: list[Any] = field(default_factory=list)  # El | str
    line: int = 0


@dataclass
class Fn:
    params: N | None
    body: N
    env: "Env"
    name: str = ""


class Env:
    def __init__(self, parent: "Env | None" = None):
        self.vars: dict[str, Any] = {}
        self.parent = parent

    def lookup(self, name: str) -> Any:
        scope: Env | None = self
        while scope is not None:
            if name in scope.vars:
                return scope.vars[name]
            scope = scope.parent
        return _MISSING


_MISSING = object()


def _config_colors(config: Any) -> dict[str, str]:
    """Colour names from a Tailwind config object (theme.colors and theme.extend.colors), as plain values."""
    out: dict[str, str] = {}
    theme = config.get("theme") if isinstance(config, dict) else None
    if not isinstance(theme, dict):
        return out
    extend = theme.get("extend")

    def flatten(source: Any, prefix: str) -> None:
        if not isinstance(source, dict):
            return
        for key, value in source.items():
            name = prefix if key == "DEFAULT" and prefix else (f"{prefix}-{key}" if prefix else str(key))
            if isinstance(value, str) and re.match(r"^(#[0-9a-fA-F]{3,8}|rgba?\([\d\s.,%/]+\))$", value.strip()):
                out[name] = value.strip()
            elif isinstance(value, dict):
                flatten(value, name)

    flatten(theme.get("colors"), "")
    flatten(extend.get("colors") if isinstance(extend, dict) else None, "")
    return out


def _kebab(name: str) -> str:
    if name.startswith("--"):
        return name
    name = re.sub(r"^(Webkit|Moz|ms|O)(?=[A-Z])", lambda m: "-" + m.group(1).lower() if m.group(1) != "ms" else "-ms", name)
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower().replace("--", "-")


def _jsx_text(raw: str) -> str:
    """React's rule for text between JSX tags: lines are trimmed, blank lines dropped, the rest joined with one space."""
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    kept: list[str] = []
    for index, line in enumerate(lines):
        if index > 0:
            line = line.lstrip(" \t")
        if index < len(lines) - 1:
            line = line.rstrip(" \t")
        if line:
            kept.append(line)
    return " ".join(kept)


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0", "\\": "\\", "'": "'", '"': '"', "`": "`", "$": "$"}


def _unescape(raw: str) -> str:
    if raw.startswith("\\u{"):
        return chr(int(raw[3:-1], 16))
    if raw.startswith("\\u") and len(raw) == 6:
        return chr(int(raw[2:], 16))
    if raw.startswith("\\x") and len(raw) == 4:
        return chr(int(raw[2:], 16))
    return _ESCAPES.get(raw[1:2], raw[1:2])


def _px(value: Any) -> str:
    return f"{value:g}px" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


class Importer:
    def __init__(self, source: str):
        self.text = source
        self.src = source.encode("utf-8")
        self.errors: list[Issue] = []
        self.warnings: list[Issue] = []
        self.globals = Env()
        self.imports: dict[str, tuple[str, str]] = {}  # local name -> (package, imported name)
        self.namespaces: dict[str, str] = {}
        self.lazy: dict[str, N] = {}
        self.resolving: set[str] = set()
        self.default_export: N | str | None = None
        self.preview_props: dict[str, N] = {}
        self.steps = 0
        self.depth = 0
        self.tailwind = 0
        self.tailwind_colors: list[dict[str, str]] = []
        self.elements = 0
        self.components_used: set[str] = set()
        self.process_warned = False
        self.props_used: dict[str, str] = {}
        self.preview_props_node: N | None = None

    # ---------------------------------------------------------------- reporting

    def snippet(self, node: N, limit: int = 60) -> str:
        text = self.src[node.start_byte:node.end_byte].decode("utf-8", "replace")
        text = " ".join(text.split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def _issue(self, bucket: list[Issue], severity: str, message: str, node: N | None, code: str) -> None:
        line, column = (node.start_point.row + 1, node.start_point.column + 1) if node is not None else (None, None)
        if len(bucket) >= MAX_ISSUES:
            return
        for existing in bucket:
            if existing.message == message:
                if line is not None and line != existing.line and line not in existing.more_lines and len(existing.more_lines) < 30:
                    existing.more_lines.append(line)
                return
        bucket.append(Issue(severity, message, line, column, code))

    def error(self, message: str, node: N | None = None, code: str = "unsupported") -> None:
        self._issue(self.errors, "error", message, node, code)

    def warn(self, message: str, node: N | None = None, code: str = "changed") -> None:
        self._issue(self.warnings, "warning", message, node, code)

    # ---------------------------------------------------------------- the file

    def parse(self) -> N | None:
        tree = Parser(_LANGUAGE).parse(self.src)  # nodes are only valid while their tree is alive
        try:
            root = _copy_tree(tree.root_node)
            if root.has_error and _BARE_AMPERSAND.search(self.text):
                # JSX allows a lone "&" in text ("Terms & Conditions"); the grammar does not. Read a copy where it is a letter of the
                # same width, so every position still matches the original text.
                retry = _BARE_AMPERSAND.sub("~", self.text).encode("utf-8")
                if len(retry) == len(self.src):
                    again = _copy_tree(Parser(_LANGUAGE).parse(retry).root_node)
                    if not again.has_error:
                        root = again
        except RecursionError:
            self.error("The code is nested too deeply to read safely.", None, "too_complex")
            return None
        if root.has_error:
            found: list[N] = []

            def walk(node: N) -> None:
                if len(found) >= 5:
                    return
                if node.is_missing or node.type == "ERROR":
                    found.append(node)
                    if node.type == "ERROR" and not node.is_missing:
                        return
                for child in node.children:
                    if child.has_error or child.is_missing:
                        walk(child)

            walk(root)
            for node in found or [root]:
                if node.is_missing:
                    self.error(f"The code is incomplete: `{node.type}` is missing here.", node, "syntax")
                else:
                    self.error(f"The code could not be read near `{self.snippet(node, 40)}`. Check for a missing bracket, quote or closing tag. "
                               "To show an ERPX placeholder write it inside text as {{student_name}} or as a string: {\"{{student_name}}\"}.", node, "syntax")
            return None
        return root

    def read_file(self, root: N) -> None:
        for statement in root.named_children:
            self.top_level(statement)

    def top_level(self, node: N, exported: bool = False) -> None:
        kind = node.type
        if kind in ("comment", "empty_statement", "hash_bang_line", "interface_declaration", "type_alias_declaration", "ambient_declaration"):
            return
        if kind == "import_statement":
            self.import_statement(node)
        elif kind == "export_statement":
            self.export_statement(node)
        elif kind == "lexical_declaration" or kind == "variable_declaration":
            for declarator in node.named_children:
                if declarator.type != "variable_declarator":
                    continue
                name = declarator.child_by_field_name("name")
                value = declarator.child_by_field_name("value")
                if name is None or name.type != "identifier":
                    self.error("Only simple constants (const name = value) are supported at the top of the file.", declarator, "unsupported_declaration")
                elif value is not None:
                    self.lazy[self.text_of(name)] = value
        elif kind == "function_declaration":
            name = node.child_by_field_name("name")
            if name is not None:
                self.lazy[self.text_of(name)] = node
        elif kind == "expression_statement":
            self.expression_statement(node)
        else:
            self.error(f"`{self.snippet(node, 40)}` runs code when the file loads, which is not supported. Keep only imports, constants and the email component.", node, "dynamic_code")

    def text_of(self, node: N) -> str:
        return self.src[node.start_byte:node.end_byte].decode("utf-8", "replace")

    def import_statement(self, node: N) -> None:
        source = node.child_by_field_name("source")
        package = self.string_value(source) if source is not None else ""
        is_type = any(c.type == "type" for c in node.children)
        allowed = _ALLOWED_IMPORTS.get(package, "no")
        if is_type:
            return
        if allowed == "no" and re.search(r"tailwind\.config$", package):
            # A project's own Tailwind theme cannot be loaded; <Tailwind> falls back to the default scale and says so.
            clause = next((c for c in node.named_children if c.type == "import_clause"), None)
            for ident in (clause.named_children if clause is not None else []):
                if ident.type == "identifier":
                    self.globals.vars[self.text_of(ident)] = {}
            self.warn(f"`{package}` (a custom Tailwind theme) cannot be loaded. The default Tailwind scale and colours are used; classes that rely on your own theme are reported below.", node, "tailwind")
            return
        if allowed == "no":
            if package.startswith((".", "/")):
                why = f"`{package}` is another file, and other files cannot be loaded. Paste its contents into this file."
            elif package.startswith("@react-email/"):
                why = f"`{package}` is not supported here. Supported: @react-email/components (or react-email)."
            else:
                why = f"`{package}` is an external package. Only @react-email/components (or react-email) and react are allowed, because imported code would have to be run."
            self.error(f"Unsupported import: {why}", node, "unsupported_import")
            return
        clause = next((c for c in node.named_children if c.type == "import_clause"), None)
        if clause is None:
            return
        for part in clause.named_children:
            if part.type == "identifier":  # import React from "react"
                continue
            if part.type == "namespace_import":
                name = next((c for c in part.named_children if c.type == "identifier"), None)
                if name is not None and package != "react":
                    self.namespaces[self.text_of(name)] = package
                continue
            if part.type == "named_imports":
                for spec in part.named_children:
                    if spec.type != "import_specifier" or any(c.type == "type" for c in spec.children):
                        continue
                    names = [c for c in spec.named_children if c.type == "identifier"]
                    imported = self.text_of(names[0]) if names else ""
                    local = self.text_of(names[-1]) if names else ""
                    if imported in _PRESETS and package in ("react-email", "@react-email/components"):
                        self.globals.vars[local] = {}
                        continue
                    if allowed is not None and imported not in allowed:
                        self.error(f"`{imported}` from `{package}` is not supported. Supported components: {', '.join(SUPPORTED_COMPONENTS)}. "
                                   "For anything else, build the email in the HTML tab instead.", spec, "unsupported_component")
                        self.imports[local] = (package, "")
                    elif allowed is not None:
                        self.imports[local] = (package, imported)

    def export_statement(self, node: N) -> None:
        declaration = node.child_by_field_name("declaration")
        value = node.child_by_field_name("value")
        is_default = any(c.type == "default" for c in node.children)
        if declaration is not None:
            self.top_level(declaration)
            if is_default:
                name = declaration.child_by_field_name("name")
                self.default_export = self.text_of(name) if name is not None else declaration
            return
        if value is not None and is_default:
            self.default_export = self.text_of(value) if value.type == "identifier" else value
            return
        for child in node.named_children:
            if child.type == "export_clause":
                for spec in child.named_children:
                    names = [self.text_of(c) for c in spec.named_children if c.type == "identifier"]
                    if len(names) == 2 and names[1] == "default":
                        self.default_export = names[0]
            elif child.type in ("string", "namespace_export"):
                self.error("Re-exporting from another file is not supported.", node, "unsupported_import")

    def expression_statement(self, node: N) -> None:
        expression = node.named_children[0] if node.named_children else None
        if expression is not None and expression.type == "assignment_expression":
            left = expression.child_by_field_name("left")
            right = expression.child_by_field_name("right")
            if left is not None and left.type == "member_expression":
                prop = left.child_by_field_name("property")
                if prop is not None and self.text_of(prop) == "PreviewProps" and right is not None:
                    if right.type == "satisfies_expression" or right.type == "as_expression":
                        right = right.named_children[0]
                    if right.type == "object":
                        self.preview_props_node = right
                        return
                if prop is not None and right is not None and right.type in ("identifier", "string", "number", "object", "true", "false", "null"):
                    return  # a fixed value attached to a component (displayName, tailwindConfig...): nothing runs, nothing is used
        self.error(f"`{self.snippet(node, 40)}` runs code when the file loads, which is not supported.", node, "dynamic_code")

    # ---------------------------------------------------------------- evaluation

    def string_value(self, node: N | None) -> str:
        if node is None:
            return ""
        out = []
        for child in node.children:
            if child.type == "string_fragment":
                out.append(self.text_of(child))
            elif child.type == "escape_sequence":
                out.append(_unescape(self.text_of(child)))
        return "".join(out)

    def resolve(self, name: str, env: Env, node: N) -> Any:
        found = env.lookup(name)
        if found is not _MISSING:
            return found
        if name in self.globals.vars:
            return self.globals.vars[name]
        if name in self.lazy:
            if name in self.resolving:
                raise Bad(f"`{name}` refers to itself, which is not supported.", node, "dynamic_code")
            self.resolving.add(name)
            try:
                target = self.lazy[name]
                if target.type == "function_declaration":
                    value: Any = Fn(target.child_by_field_name("parameters"), target.child_by_field_name("body") or target, self.globals, name)
                else:
                    value = self.ev(target, self.globals)
                    if isinstance(value, Fn) and not value.name:
                        value.name = name
            finally:
                self.resolving.discard(name)
            self.globals.vars[name] = value
            return value
        if name == "undefined":
            return UNDEF
        if name in self.imports or name in self.namespaces:
            raise Bad(f"`{name}` is imported but can only be used as a component, like <{name} />.", node, "unsupported_component")
        raise Bad(f"`{name}` is not defined in this file. " + _HINTS.get(name, "Define it as a constant at the top of the file, or write the value directly."), node, "undefined")

    def ev(self, node: N, env: Env) -> Any:
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise Bad("This file is too complex to read safely.", node, "too_complex")
        handler = getattr(self, "_e_" + node.type, None)
        if handler is None:
            raise Bad(self.refuse(node), node, "dynamic_code")
        return handler(node, env)

    def refuse(self, node: N) -> str:
        kind = node.type
        text = self.snippet(node, 50)
        if kind == "new_expression":
            ctor = node.child_by_field_name("constructor")
            hint = _HINTS.get(self.text_of(ctor), "") if ctor is not None else ""
            return f"`{text}` cannot be used: objects are not created while reading the email. {hint}".strip()
        if kind == "call_expression":
            fn = node.child_by_field_name("function")
            head = self.text_of(fn).split(".")[0] if fn is not None else ""
            hint = _HINTS.get(head, "Only fixed values and list.map(item => <.../>) can be used. Write the final text directly or use an ERPX placeholder such as {{student_name}}.")
            return f"`{text}` cannot be used: function calls are never run. {hint}"
        if kind in ("await_expression", "yield_expression"):
            return f"`{text}` cannot be used: asynchronous code is never run."
        if kind in ("assignment_expression", "augmented_assignment_expression", "update_expression"):
            return f"`{text}` cannot be used: changing values is not supported."
        if kind in ("regex", "class", "class_declaration"):
            return f"`{text}` is not supported."
        if kind == "this":
            return "`this` is not supported."
        return f"`{text}` ({kind.replace('_', ' ')}) is not supported: only fixed values, simple styles and JSX are read."

    def _e_string(self, node: N, env: Env) -> str:
        return self.string_value(node)

    def _e_template_string(self, node: N, env: Env) -> str:
        out = []
        for child in node.children:
            if child.type == "string_fragment":
                out.append(self.text_of(child))
            elif child.type == "escape_sequence":
                out.append(_unescape(self.text_of(child)))
            elif child.type == "template_substitution":
                inner = child.named_children[0]
                value = self.ev(inner, env)
                out.append("" if value is UNDEF or value is None else self.to_str(value, inner))
        return "".join(out)

    def to_str(self, value: Any, node: N) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, (str, int, float)):
            return str(value)
        raise Bad("Only text and numbers can be placed in text.", node, "dynamic_code")

    def _e_number(self, node: N, env: Env) -> int | float:
        raw = self.text_of(node).replace("_", "")
        try:
            return int(raw, 0) if re.match(r"^0[xXbBoO]", raw) else (float(raw) if re.search(r"[.eE]", raw) else int(raw))
        except ValueError as exc:
            raise Bad("That number cannot be read.", node) from exc

    def _e_true(self, node: N, env: Env) -> bool:
        return True

    def _e_false(self, node: N, env: Env) -> bool:
        return False

    def _e_null(self, node: N, env: Env) -> None:
        return None

    def _e_undefined(self, node: N, env: Env) -> Any:
        return UNDEF

    def _e_identifier(self, node: N, env: Env) -> Any:
        return self.resolve(self.text_of(node), env, node)

    def _e_parenthesized_expression(self, node: N, env: Env) -> Any:
        return self.ev(node.named_children[0], env)

    _e_as_expression = _e_satisfies_expression = _e_non_null_expression = _e_parenthesized_expression

    def _e_object(self, node: N, env: Env) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for child in node.named_children:
            if child.type == "pair":
                key = child.child_by_field_name("key")
                value = child.child_by_field_name("value")
                if key is None or value is None or key.type == "computed_property_name":
                    raise Bad("Computed property names are not supported.", child)
                name = self.string_value(key) if key.type == "string" else self.text_of(key)
                out[name] = self.ev(value, env)
            elif child.type == "shorthand_property_identifier":
                out[self.text_of(child)] = self.resolve(self.text_of(child), env, child)
            elif child.type == "spread_element":
                spread = self.ev(child.named_children[0], env)
                if isinstance(spread, dict):
                    out.update(spread)
                elif spread not in (None, UNDEF):
                    raise Bad("Only an object can be spread into an object.", child)
            elif child.type == "comment":
                continue
            else:
                raise Bad(f"`{self.snippet(child, 40)}` is not supported inside an object.", child, "dynamic_code")
        return out

    def _e_array(self, node: N, env: Env) -> list[Any]:
        out: list[Any] = []
        for child in node.named_children:
            if child.type == "comment":
                continue
            if child.type == "spread_element":
                spread = self.ev(child.named_children[0], env)
                if not isinstance(spread, list):
                    raise Bad("Only a list can be spread into a list.", child)
                out.extend(spread)
            else:
                out.append(self.ev(child, env))
            if len(out) > 5000:
                raise Bad("The list is too long.", node, "too_complex")
        return out

    def _e_member_expression(self, node: N, env: Env) -> Any:
        text = self.text_of(node)
        if text.startswith("process.env") or text.startswith("import.meta"):
            if not self.process_warned:
                self.process_warned = True
                self.warn("Environment variables (process.env) do not exist in an email template, so they are treated as empty and the fallback value is used. "
                          "Image addresses that depend on them need to be full https:// addresses.", node, "env")
            return UNDEF
        obj_node = node.child_by_field_name("object")
        prop = node.child_by_field_name("property")
        optional = any(c.type == "optional_chain" for c in node.children)
        obj = self.ev(obj_node, env)
        name = self.text_of(prop)
        if obj in (None, UNDEF) or obj is UNDEF:
            if optional:
                return UNDEF
            raise Bad(f"`{self.snippet(obj_node, 30)}` has no value, so `.{name}` cannot be read.", node, "undefined")
        return self.member(obj, name, node)

    def member(self, obj: Any, name: str, node: N) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, UNDEF)
        if isinstance(obj, (list, str)) and name == "length":
            return len(obj)
        if isinstance(obj, list) and name.isdigit():
            index = int(name)
            return obj[index] if index < len(obj) else UNDEF
        raise Bad(f"`.{name}` is not supported here.", node, "dynamic_code")

    def _e_subscript_expression(self, node: N, env: Env) -> Any:
        obj = self.ev(node.child_by_field_name("object"), env)
        index = self.ev(node.child_by_field_name("index"), env)
        if isinstance(obj, list) and isinstance(index, int) and not isinstance(index, bool):
            return obj[index] if 0 <= index < len(obj) else UNDEF
        if isinstance(obj, dict) and isinstance(index, str):
            return obj.get(index, UNDEF)
        if isinstance(obj, str) and isinstance(index, int):
            return obj[index] if 0 <= index < len(obj) else UNDEF
        raise Bad("That lookup is not supported.", node, "dynamic_code")

    def truthy(self, value: Any) -> bool:
        if value is UNDEF or value is None or value is False or value == "" or (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0):
            return False
        return True

    def _e_binary_expression(self, node: N, env: Env) -> Any:
        left_node, right_node = node.child_by_field_name("left"), node.child_by_field_name("right")
        op = self.text_of(node.child_by_field_name("operator"))
        left = self.ev(left_node, env)
        if op == "&&":
            return self.ev(right_node, env) if self.truthy(left) else left
        if op == "||":
            return left if self.truthy(left) else self.ev(right_node, env)
        if op == "??":
            return self.ev(right_node, env) if left in (None, UNDEF) else left
        right = self.ev(right_node, env)
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self.to_str(left, left_node) + self.to_str(right, right_node)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left + right
        elif op in ("-", "*", "/", "%") and isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if op in ("/", "%") and right == 0:
                raise Bad("Division by zero.", node)
            return {"-": left - right, "*": left * right, "/": left / right if op == "/" else 0, "%": left % right if op == "%" else 0}[op]
        elif op in ("===", "=="):
            return left == right
        elif op in ("!==", "!="):
            return left != right
        elif op in ("<", ">", "<=", ">=") and isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return {"<": left < right, ">": left > right, "<=": left <= right, ">=": left >= right}[op]
        raise Bad(f"`{self.snippet(node, 50)}` is not supported.", node, "dynamic_code")

    def _e_unary_expression(self, node: N, env: Env) -> Any:
        op = self.text_of(node.child_by_field_name("operator"))
        value = self.ev(node.child_by_field_name("argument"), env)
        if op == "!":
            return not self.truthy(value)
        if op == "-" and isinstance(value, (int, float)):
            return -value
        if op == "+" and isinstance(value, (int, float)):
            return value
        raise Bad(f"`{self.snippet(node, 50)}` is not supported.", node, "dynamic_code")

    def _e_ternary_expression(self, node: N, env: Env) -> Any:
        condition = self.ev(node.child_by_field_name("condition"), env)
        return self.ev(node.child_by_field_name("consequence" if self.truthy(condition) else "alternative"), env)

    def _e_arrow_function(self, node: N, env: Env) -> Fn:
        params = node.child_by_field_name("parameters") or node.child_by_field_name("parameter")
        return Fn(params, node.child_by_field_name("body"), env)

    _e_function_expression = _e_function = _e_arrow_function

    def _e_call_expression(self, node: N, env: Env) -> Any:
        fn = node.child_by_field_name("function")
        args_node = node.child_by_field_name("arguments")
        args = [a for a in (args_node.named_children if args_node else []) if a.type != "comment"]
        if fn is None or fn.type != "member_expression":
            raise Bad(self.refuse(node), node, "dynamic_code")
        target = self.ev(fn.child_by_field_name("object"), env)
        method = self.text_of(fn.child_by_field_name("property"))
        if method == "map" and isinstance(target, list) and len(args) == 1:
            callback = self.ev(args[0], env)
            if not isinstance(callback, Fn):
                raise Bad("map() needs a function like (item) => <Text>{item}</Text>.", node, "dynamic_code")
            if len(target) > MAX_LOOP:
                raise Bad(f"A list of more than {MAX_LOOP} items is not supported.", node, "too_complex")
            return [self.call(callback, [item, index], node) for index, item in enumerate(target)]
        if method == "join" and isinstance(target, list) and len(args) <= 1:
            sep = self.ev(args[0], env) if args else ","
            return str(sep).join(self.to_str(v, node) for v in target)
        if method in ("toUpperCase", "toLowerCase", "trim") and isinstance(target, str) and not args:
            return {"toUpperCase": target.upper, "toLowerCase": target.lower, "trim": target.strip}[method]()
        raise Bad(self.refuse(node), node, "dynamic_code")

    # ---------------------------------------------------------------- functions and components

    def bind(self, fn: Fn, args: list[Any], scope: Env) -> None:
        params = fn.params
        if params is None:
            return
        parameters = [p for p in params.named_children if p.type in ("required_parameter", "optional_parameter", "identifier")] if params.type == "formal_parameters" else [params]
        for index, parameter in enumerate(parameters):
            value = args[index] if index < len(args) else UNDEF
            pattern = parameter.child_by_field_name("pattern") if parameter.type != "identifier" else parameter
            if pattern is None:
                pattern = parameter.named_children[0]
            self.destructure(pattern, value, scope, parameter)

    def destructure(self, pattern: N, value: Any, scope: Env, origin: N) -> None:
        if pattern.type == "identifier":
            scope.vars[self.text_of(pattern)] = value
            return
        if pattern.type == "assignment_pattern":
            left = pattern.child_by_field_name("left")
            default = pattern.child_by_field_name("right")
            self.destructure(left, value if value is not UNDEF else self.ev(default, scope), scope, origin)
            return
        if pattern.type == "object_pattern":
            source = value if isinstance(value, dict) else {}
            used: set[str] = set()
            for part in pattern.named_children:
                if part.type == "shorthand_property_identifier_pattern":
                    name = self.text_of(part)
                    used.add(name)
                    scope.vars[name] = source.get(name, UNDEF)
                elif part.type == "object_assignment_pattern":
                    name = self.text_of(part.named_children[0])
                    used.add(name)
                    current = source.get(name, UNDEF)
                    scope.vars[name] = current if current is not UNDEF else self.ev(part.named_children[-1], scope)
                elif part.type == "pair_pattern":
                    key = part.child_by_field_name("key")
                    name = self.string_value(key) if key.type == "string" else self.text_of(key)
                    used.add(name)
                    self.destructure(part.child_by_field_name("value"), source.get(name, UNDEF), scope, origin)
                elif part.type == "rest_pattern":
                    rest = {k: v for k, v in source.items() if k not in used}
                    self.destructure(part.named_children[0], rest, scope, origin)
                elif part.type != "comment":
                    raise Bad("That parameter pattern is not supported.", part, "dynamic_code")
            return
        raise Bad("That parameter pattern is not supported.", pattern, "dynamic_code")

    def call(self, fn: Fn, args: list[Any], node: N) -> Any:
        if self.depth > MAX_DEPTH:
            raise Bad("Components are nested too deeply (or refer to themselves).", node, "too_complex")
        self.depth += 1
        try:
            scope = Env(fn.env)
            self.bind(fn, args, scope)
            body = fn.body
            if body.type == "statement_block":
                return self.run_block(body, scope)
            return self.ev(body, scope)
        finally:
            self.depth -= 1

    def run_block(self, block: N, scope: Env) -> Any:
        for statement in block.named_children:
            kind = statement.type
            if kind in ("comment", "empty_statement"):
                continue
            if kind in ("lexical_declaration", "variable_declaration"):
                for declarator in statement.named_children:
                    if declarator.type != "variable_declarator":
                        continue
                    name = declarator.child_by_field_name("name")
                    value = declarator.child_by_field_name("value")
                    if value is None:
                        raise Bad("Declare a value when you create a constant.", declarator)
                    self.destructure(name, self.ev(value, scope), scope, declarator)
            elif kind == "return_statement":
                value = statement.named_children[0] if statement.named_children else None
                return self.ev(value, scope) if value is not None else UNDEF
            else:
                raise Bad(f"`{self.snippet(statement, 50)}` is not supported inside a component: only constants and a `return` are read. "
                          "Logic such as if, for, hooks or function calls is never run.", statement, "dynamic_code")
        raise Bad("The component never returns anything. End it with return (<Html>…</Html>).", block, "no_return")

    # ---------------------------------------------------------------- JSX

    def _e_jsx_element(self, node: N, env: Env) -> Any:
        return self.element(node, env)

    _e_jsx_self_closing_element = _e_jsx_element

    def _e_jsx_fragment(self, node: N, env: Env) -> Any:
        return self.children(node, env)

    def children(self, node: N, env: Env) -> list[Any]:
        out: list[Any] = []
        group: list[tuple[int, int]] = []  # byte ranges only: no N objects are kept across iterations

        def flush() -> None:
            if group:
                raw = self.src[group[0][0]:group[-1][1]].decode("utf-8", "replace")
                text = html_lib.unescape(_jsx_text(raw))
                if text:
                    out.append(text)
                group.clear()

        for child in node.children:
            kind = child.type
            if kind in ("jsx_text", "html_character_reference"):
                group.append((child.start_byte, child.end_byte))
                continue
            if kind in ("jsx_opening_element", "jsx_closing_element", "<>", "</>"):
                continue
            flush()
            if kind in ("jsx_element", "jsx_self_closing_element", "jsx_fragment"):
                self.attempt(out, lambda c=child: self.ev(c, env), child)
            elif kind == "jsx_expression":
                self.attempt(out, lambda c=child: self.expression_child(c, env), child)
        flush()
        return out

    def attempt(self, out: list[Any], action: Any, node: N) -> None:
        """Evaluate one child; if it is refused, record why and carry on, so every problem in the file is reported in one go."""
        try:
            self.flatten_into(out, action(), node)
        except Bad as bad:
            if bad.code != "silent":
                self.error(bad.message, bad.node or node, bad.code)

    def expression_child(self, node: N, env: Env) -> Any:
        inner = [c for c in node.named_children if c.type != "comment"]
        if not inner:
            return None
        expression = inner[0]
        placeholder = self.placeholder_of(expression)
        if placeholder is not None:
            return placeholder
        return self.ev(expression, env)

    def placeholder_of(self, node: N) -> str | None:
        """`{{student_name}}` written bare in JSX is the object {student_name}; read it as the ERPX placeholder it was meant to be."""
        if node.type == "object" and len(node.named_children) == 1 and node.named_children[0].type == "shorthand_property_identifier":
            return "{{" + self.text_of(node.named_children[0]) + "}}"
        return None

    def flatten_into(self, out: list[Any], value: Any, node: N) -> None:
        if value is None or value is UNDEF or isinstance(value, bool):
            return
        if isinstance(value, El):
            out.append(value)
        elif isinstance(value, (str, int, float)):
            out.append(self.to_str(value, node))
        elif isinstance(value, list):
            for item in value:
                self.flatten_into(out, item, node)
        elif isinstance(value, dict):
            raise Bad("An object cannot be placed in the email. Show its text values one by one.", node, "dynamic_code")
        elif isinstance(value, Fn):
            raise Bad("A function cannot be placed in the email.", node, "dynamic_code")

    def element(self, node: N, env: Env) -> Any:
        self.elements += 1
        if self.elements > MAX_ELEMENTS:
            raise Bad("The email has too many elements.", node, "too_complex")
        if self.depth > MAX_DEPTH:
            raise Bad("The email is nested too deeply.", node, "too_complex")
        opening = node if node.type == "jsx_self_closing_element" else node.child_by_field_name("open_tag") or node.named_children[0]
        name_node = opening.child_by_field_name("name")
        name = self.text_of(name_node) if name_node is not None else ""
        resolved = self.resolve_component(name, env, name_node or node)
        props = self.attributes(opening, env, name)
        is_tailwind = resolved == "Tailwind"
        if is_tailwind:
            self.tailwind += 1
            self.tailwind_colors.append(_config_colors(props.get("config")))
        self.depth += 1
        try:
            kids = self.children(node, env) if node.type == "jsx_element" else []
        finally:
            self.depth -= 1
            if is_tailwind:
                self.tailwind -= 1
                self.tailwind_colors.pop()
        if isinstance(resolved, Fn):
            props["children"] = kids
            return self.call(resolved, [props], node)
        return self.build_element(resolved, name, props, kids, node)

    def resolve_component(self, name: str, env: Env, node: N) -> Any:
        if "." in name:
            head, _, tail = name.partition(".")
            if head in self.namespaces:
                allowed = _ALLOWED_IMPORTS.get(self.namespaces[head])
                if allowed is not None and tail in allowed:
                    self.components_used.add(tail)
                    return tail
            raise Bad(f"`<{name}>` is not supported.", node, "unsupported_component")
        if name and name[0].islower():
            return "tag:" + name
        local = env.lookup(name)
        if local is not _MISSING and isinstance(local, Fn):
            return local
        if name in self.imports:
            package, imported = self.imports[name]
            if not imported:
                raise Bad("", node, "silent")  # the import itself was already reported
            self.components_used.add(imported)
            return imported
        if name in self.lazy or name in self.globals.vars:
            value = self.resolve(name, env, node)
            if isinstance(value, Fn):
                return value
            raise Bad(f"`{name}` is not a component.", node, "undefined")
        if name in SUPPORTED_COMPONENTS or name in _IGNORED_COMPONENTS:
            raise Bad(f"`<{name}>` is used but not imported. Add: import {{ {name} }} from \"@react-email/components\";", node, "undefined")
        raise Bad(f"`<{name}>` is not defined in this file and is not a supported React Email component. Supported: {', '.join(SUPPORTED_COMPONENTS)}.", node, "unsupported_component")

    def attributes(self, opening: N, env: Env, name: str) -> dict[str, Any]:
        props: dict[str, Any] = {}
        for attribute in opening.named_children:
            if attribute.type == "jsx_attribute":
                key_node = attribute.named_children[0]
                key = self.text_of(key_node)
                if key_node.type != "property_identifier" and not key.startswith(("data-", "aria-")):
                    self.warn(f"The attribute `{key}` is not supported and was ignored.", attribute)
                    continue
                if re.match(r"^on[A-Z]", key):
                    self.error(f"`{key}` is an event handler. Email clients never run scripts, so interactivity cannot be imported. Use a <Button> or <Link> with an href.", attribute, "event_handler")
                    continue
                if key == "dangerouslySetInnerHTML":
                    self.error("`dangerouslySetInnerHTML` inserts raw HTML and is not allowed. Write the content as JSX, or use the HTML tab to import HTML.", attribute, "dangerous")
                    continue
                if key in ("key", "ref", "suppressHydrationWarning") or key.startswith(("data-", "aria-")):
                    continue
                value_node = attribute.named_children[1] if len(attribute.named_children) > 1 else None
                try:
                    if value_node is None:
                        props[key] = True
                    elif value_node.type == "string":
                        props[key] = html_lib.unescape(self.string_value(value_node))
                    elif value_node.type == "jsx_expression":
                        inner = [c for c in value_node.named_children if c.type != "comment"]
                        placeholder = self.placeholder_of(inner[0]) if inner else None
                        props[key] = placeholder if placeholder is not None else (self.ev(inner[0], env) if inner else UNDEF)
                    else:
                        props[key] = self.ev(value_node, env)
                except Bad as bad:
                    self.error(bad.message, bad.node or attribute, bad.code)
            elif attribute.type == "jsx_expression":  # {...props}
                inner = [c for c in attribute.named_children if c.type != "comment"]
                if inner and inner[0].type == "spread_element":
                    try:
                        spread = self.ev(inner[0].named_children[0], env)
                    except Bad as bad:
                        self.error(bad.message, bad.node or attribute, bad.code)
                        continue
                    if isinstance(spread, dict):
                        props.update(spread)
                    elif spread not in (None, UNDEF):
                        self.error("Only an object can be spread into attributes.", attribute, "dynamic_code")
        return props

    # ---------------------------------------------------------------- building the email tree

    def style_of(self, props: dict[str, Any], node: N) -> dict[str, str]:
        out: dict[str, str] = {}
        classes = props.get("className")
        if isinstance(classes, str) and classes.strip():
            if self.tailwind > 0:
                styles, skipped = tailwind.resolve(classes, self.tailwind_colors[-1] if self.tailwind_colors else None)
                out.update(styles)
                if skipped:
                    self.warn("These Tailwind classes have no email-safe equivalent and were not applied: " + ", ".join(skipped) +
                              ". Use the style prop or a supported utility instead.", node, "tailwind")
            else:
                self.warn(f"className=\"{classes}\" has no effect outside <Tailwind> and was ignored.", node, "tailwind")
        style = props.get("style")
        if isinstance(style, dict):
            for key, value in style.items():
                if value is None or value is UNDEF or isinstance(value, bool):
                    continue
                prop = _kebab(str(key))
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    text = f"{value:g}" if prop in _UNITLESS or value == 0 else _px(value)
                elif isinstance(value, str):
                    text = value.strip()
                else:
                    self.warn(f"The style `{key}` has a value that cannot be used and was ignored.", node, "style")
                    continue
                out[prop] = text
        elif style not in (None, UNDEF):
            self.warn("The style prop is not a plain object and was ignored.", node, "style")
        return out

    def url_of(self, value: Any, node: N, what: str, image: bool = False) -> str:
        if value in (None, UNDEF) or value == "":
            return ""
        if not isinstance(value, str):
            raise Bad(f"The {what} must be text.", node)
        text = value.strip()
        lowered = re.sub(r"[\s\x00-\x1f]", "", text).lower()
        if lowered.startswith(("javascript:", "vbscript:")):
            raise Bad(f"The {what} `{text[:40]}` runs a script, which is never allowed.", node, "dangerous")
        if lowered.startswith("data:"):
            if image:
                self.warn(f"Embedded (data:) images do not work in most email clients, so the {what} was removed. Upload the image and use its https:// address.", node, "image")
                return ""
            raise Bad(f"The {what} `data:` address is not allowed.", node, "dangerous")
        if lowered.startswith("{{") or re.match(r"^(https?://|mailto:|tel:|#)", lowered):
            return text
        self.warn(f"The {what} `{text[:60]}` is not a full web address (https://…), so email clients cannot open it and it was removed.", node, "link")
        return ""

    def build_element(self, resolved: str, name: str, props: dict[str, Any], kids: list[Any], node: N) -> Any:
        line = node.start_point.row + 1
        if resolved.startswith("tag:"):
            return self.plain_tag(resolved[4:], props, kids, node)
        if resolved == "Tailwind":
            if isinstance(props.get("config"), dict) and props["config"] and not _config_colors(props["config"]):
                self.warn("Only the colours of a custom Tailwind config are read. Its other settings (fonts, spacing, screens) are ignored.", node, "tailwind")
            return kids
        if resolved == "Font":
            self.warn("<Font> (a web font) was skipped, because email clients mostly ignore web fonts. The fallback font stack is used.", node, "font")
            return None
        style = self.style_of(props, node)
        attrs: dict[str, str] = {}
        if resolved == "Html":
            return El("html", children=kids, line=line)
        if resolved == "Head":
            return El("head", children=kids, line=line)
        if resolved == "Preview":
            text = "".join(k for k in kids if isinstance(k, str)).strip()
            return El("preview", children=[text], line=line)
        if resolved == "Heading":
            level = props.get("as", "h1")
            if level not in ("h1", "h2", "h3", "h4", "h5", "h6"):
                raise Bad("<Heading as> must be h1 to h6.", node, "unsupported_attribute")
            margins = {}
            for key, parts in (("m", ("margin",)), ("mx", ("margin-left", "margin-right")), ("my", ("margin-top", "margin-bottom")), ("mt", ("margin-top",)),
                               ("mr", ("margin-right",)), ("mb", ("margin-bottom",)), ("ml", ("margin-left",))):
                if isinstance(props.get(key), (int, float)) and not isinstance(props.get(key), bool):
                    for part in parts:
                        margins[part] = _px(props[key])
            return El("heading", tag=level, style={**margins, **style}, children=kids, line=line)
        if resolved == "Button":
            href = self.url_of(props.get("href"), node, "button link")
            pad_x, pad_y = props.get("pX"), props.get("pY")
            if isinstance(pad_x, (int, float)) or isinstance(pad_y, (int, float)):
                px, py = _px(pad_y or 0), _px(pad_x or 0)
                style = {"padding": f"{py} {px}", **style}
            attrs["href"] = href
            return El("button", attrs=attrs, style=style, children=kids, line=line)
        if resolved == "Link":
            attrs["href"] = self.url_of(props.get("href"), node, "link")
            return El("link", attrs=attrs, style=style, children=kids, line=line)
        if resolved == "Img":
            attrs["src"] = self.url_of(props.get("src"), node, "image address", image=True)
            for key in ("alt", "width", "height"):
                if props.get(key) not in (None, UNDEF):
                    attrs[key] = self.to_str(props[key], node)
            return El("img", attrs=attrs, style=style, line=line)
        if resolved in ("Container", "Section", "Row", "Body", "Column", "Text", "Hr"):
            if resolved == "Column":
                for key, out_key in (("align", "align"), ("width", "width"), ("valign", "valign"), ("colSpan", "colspan")):
                    if props.get(key) not in (None, UNDEF):
                        attrs[out_key] = self.to_str(props[key], node)
            return El(resolved.lower(), attrs=attrs, style=style, children=kids, line=line)
        raise Bad(f"`<{name}>` is not supported.", node, "unsupported_component")

    def plain_tag(self, tag: str, props: dict[str, Any], kids: list[Any], node: N) -> Any:
        if tag in _FORBIDDEN_TAGS:
            raise Bad(f"`<{tag}>` is not allowed: {_FORBIDDEN_TAGS[tag]}.", node, "forbidden_tag")
        if tag == "style":
            self.warn("A <style> block was removed: email clients drop or block them. Use inline style props (or <Tailwind>) instead.", node, "style")
            return None
        if tag == "title":
            return El("title", children=kids, line=node.start_point.row + 1)
        if tag in ("meta", "head", "html", "body"):
            return El({"head": "head", "html": "html", "body": "body"}.get(tag, "meta"), children=kids, style=self.style_of(props, node) if tag == "body" else {}, line=node.start_point.row + 1)
        if tag not in _PLAIN_TAGS:
            raise Bad(f"`<{tag}>` is not a supported HTML element in an email.", node, "unsupported_component")
        attrs: dict[str, str] = {}
        for key, value in props.items():
            out_key = _ATTR_RENAME.get(key, key)
            if key in ("style", "className", "children") or value in (None, UNDEF) or isinstance(value, bool):
                continue
            if out_key not in _PLAIN_ATTRS:
                self.warn(f"The attribute `{key}` on <{tag}> is not supported in email and was ignored.", node, "attribute")
                continue
            if out_key in ("href",):
                attrs[out_key] = self.url_of(value, node, "link")
            elif out_key == "src":
                attrs[out_key] = self.url_of(value, node, "image address", image=True)
            else:
                attrs[out_key] = self.to_str(value, node)
        return El("tag", tag=tag, attrs=attrs, style=self.style_of(props, node), children=kids, line=node.start_point.row + 1)


# ---------------------------------------------------------------- HTML out


def _css(style: dict[str, str]) -> str:
    return ";".join(f"{k}:{v}" for k, v in style.items() if v not in ("", None))


def _attr(name: str, value: str) -> str:
    return f' {name}="{html_lib.escape(value, quote=True)}"'


class Writer:
    def __init__(self, importer: Importer):
        self.importer = importer
        self.title = ""
        self.preheader = ""
        self.body_style: dict[str, str] = {}
        self.dropped_style: list[tuple[int, str]] = []

    def style(self, defaults: str, style: dict[str, str], el: El) -> str:
        """The style attribute: the component's defaults, then the author's (so theirs win). Declarations the sanitiser would remove
        are reported, not dropped silently."""
        own = _css(style)
        base = dict(d.split(":", 1) for d in defaults.split(";") if ":" in d)
        for key, value in style.items():
            base.pop(key, None)
            base[key] = value
        merged = _css(base)
        if own:
            kept = {d.split(":", 1)[0] for d in _clean_style(own).split(";") if ":" in d}
            gone = sorted({k for k in style if k.lower() not in kept})
            if gone:
                self.importer.warn(
                    "These styles are not email-safe and were removed: " + ", ".join(f"{k}:{style[k]}" if len(style[k]) < 24 else k for k in gone) +
                    ". (Layout like flex/grid/position does not work in email clients; use Row and Column.)", None if not el.line else _Line(el.line), "style")
        return _attr("style", merged) if merged else ""

    def children(self, el: El) -> str:
        return "".join(self.node(child) for child in el.children)

    def node(self, child: Any) -> str:
        if isinstance(child, str):
            return html_lib.escape(child, quote=False)
        return self.element(child)

    def element(self, el: El) -> str:
        kind = el.kind
        inner = self.children(el)
        if kind == "html":
            return inner
        if kind == "head":
            for child in el.children:
                if isinstance(child, El) and child.kind == "title":
                    self.title = "".join(c for c in child.children if isinstance(c, str)).strip()
            return ""
        if kind in ("title", "meta"):
            return ""
        if kind == "preview":
            self.preheader = (el.children[0] if el.children and isinstance(el.children[0], str) else "").strip()
            return ""
        if kind == "body":
            self.body_style = {**self.body_style, **el.style}
            return inner
        table = ' align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"'
        if kind == "container":
            return f"<table{table}{self.style('max-width:37.5em', el.style, el)}><tbody><tr style=\"width:100%\"><td>{inner}</td></tr></tbody></table>"
        if kind == "section":
            return f"<table{table}{self.style('', el.style, el)}><tbody><tr><td>{inner}</td></tr></tbody></table>"
        if kind == "row":
            return f"<table{table}{self.style('', el.style, el)}><tbody style=\"width:100%\"><tr style=\"width:100%\">{inner}</tr></tbody></table>"
        if kind == "column":
            attrs = "".join(_attr(k, v) for k, v in el.attrs.items())
            return f"<td{attrs}{self.style('', el.style, el)}>{inner}</td>"
        if kind == "text":
            return f"<p{self.style('font-size:14px;line-height:24px;margin:16px 0', el.style, el)}>{inner}</p>"
        if kind == "heading":
            return f"<{el.tag}{self.style('', el.style, el)}>{inner}</{el.tag}>"
        if kind == "button":
            href = _attr("href", el.attrs.get("href", "")) if el.attrs.get("href") else ""
            base = "line-height:100%;text-decoration:none;display:inline-block;max-width:100%"
            return (f"<a{href} target=\"_blank\"{self.style(base, el.style, el)}>"
                    f"<span style=\"max-width:100%;display:inline-block;line-height:120%\">{inner}</span></a>")
        if kind == "link":
            href = _attr("href", el.attrs.get("href", "")) if el.attrs.get("href") else ""
            return f"<a{href} target=\"_blank\"{self.style('color:#067df7;text-decoration:none', el.style, el)}>{inner}</a>"
        if kind == "img":
            attrs = "".join(_attr(k, v) for k, v in el.attrs.items() if v != "" or k == "alt")
            return f"<img{attrs}{self.style('display:block;outline:none;border:none;text-decoration:none', el.style, el)} />"
        if kind == "hr":
            return f"<hr{self.style('width:100%;border:none;border-top:1px solid #eaeaea', el.style, el)} />"
        if kind == "tag":
            attrs = "".join(_attr(k, v) for k, v in el.attrs.items() if v != "")
            style = self.style("", el.style, el)
            if el.tag in ("br", "hr", "img", "col"):
                return f"<{el.tag}{attrs}{style} />"
            return f"<{el.tag}{attrs}{style}>{inner}</{el.tag}>"
        return inner


class _Line:
    """A stand-in for a tree node when only a line number is known."""

    def __init__(self, line: int):
        self.start_point = type("P", (), {"row": line - 1, "column": 0})()


_SIGN_OFF = re.compile(r"(?i)\b(regards|sincerely|best wishes|yours truly|warm regards|kind regards|thanks,|thank you,)\b")


def build(source: str, preheader: str = "") -> BuildResult:
    """Read React Email source and produce the email, or say exactly why it cannot be imported."""
    if not source or not source.strip():
        return BuildResult(ok=False, errors=[Issue("error", "Paste React Email code to import.", None, None, "empty")])
    if len(source) > MAX_SOURCE_CHARS:
        return BuildResult(ok=False, errors=[Issue("error", f"The code is too long ({len(source):,} characters; the limit is {MAX_SOURCE_CHARS:,}).", None, None, "too_long")])
    importer = Importer(source)
    root = importer.parse()
    if root is None:
        return BuildResult(ok=False, errors=importer.errors, warnings=importer.warnings)
    importer.read_file(root)
    for name in list(importer.lazy):  # constants are checked even when unused, so unsupported code never hides in the file
        try:
            importer.resolve(name, importer.globals, root)
        except Bad as bad:
            importer.error(bad.message, bad.node, bad.code)
        except RecursionError:
            importer.error("This file is nested too deeply to read safely.", None, "too_complex")

    entry = importer.default_export
    if entry is None:
        capitalised = [n for n, node in importer.lazy.items() if n[:1].isupper() and node.type in ("function_declaration", "arrow_function", "function_expression")]
        if capitalised:
            entry = capitalised[-1]
            importer.warn(f"There is no `export default`, so `{entry}` was used as the email. Add `export default {entry};` to be explicit.", None, "export")
        else:
            importer.error("No email component was found. Export it with `export default function Email() { return (<Html>…</Html>); }`.", None, "no_component")

    props_node = importer.preview_props_node
    top: list[Any] = []
    if entry is not None:
        try:
            props: dict[str, Any] = {}
            if props_node is not None:
                props = importer.ev(props_node, importer.globals)
                importer.props_used = {k: str(v) for k, v in props.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}
            fn = importer.resolve(entry, importer.globals, root) if isinstance(entry, str) else importer.ev(entry, importer.globals)
            if not isinstance(fn, Fn):
                raise Bad("The default export is not a component function.", root, "no_component")
            importer.flatten_into(top, importer.call(fn, [props], root), root)
        except Bad as bad:
            if bad.code != "silent":
                importer.error(bad.message, bad.node, bad.code)
        except RecursionError:
            importer.error("This file is nested too deeply to read safely.", None, "too_complex")
    for issue in importer.errors + importer.warnings:
        if issue.more_lines:
            issue.message += f" (Also on line{'s' if len(issue.more_lines) > 1 else ''} {', '.join(str(n) for n in sorted(issue.more_lines))}.)"
    errors = sorted((e for e in importer.errors if e.message), key=lambda e: (e.line or 0, e.column or 0))
    importer.warnings.sort(key=lambda w: (w.line or 10**9, w.column or 0))
    if errors:
        return BuildResult(ok=False, errors=errors, warnings=importer.warnings, components=sorted(importer.components_used))

    writer = Writer(importer)
    html_body = "".join(writer.node(item) for item in top)
    if not html_body.strip():
        importer.error("The component returned no content.", None, "empty")
        return BuildResult(ok=False, errors=importer.errors, warnings=importer.warnings)
    style_attr = f' style="{html_lib.escape(_css(writer.body_style), quote=True)}"' if writer.body_style else ""
    document = f"<!DOCTYPE html><html><head><title>{html_lib.escape(writer.title)}</title></head><body{style_attr}>{html_body}</body></html>"
    try:
        final = sanitize_document(document, writer.title, preheader or writer.preheader)
    except ValueError as exc:
        return BuildResult(ok=False, errors=[Issue("error", str(exc), None, None, "too_large")], warnings=importer.warnings)
    text = html_to_text(final)

    if importer.props_used:
        listed = ", ".join(f"{k} = {v[:30]!r}" for k, v in list(importer.props_used.items())[:8])
        importer.warn("The sample values from PreviewProps are written into the email as fixed text (" + listed + "). "
                      "Replace them with ERPX placeholders such as {{student_name}} wherever they should change for each person.", None, "preview_props")
    if "{{signature}}" not in final and _SIGN_OFF.search(text):
        importer.warn("This email already ends with a sign-off. ERPX does not add a signature to imported code on its own; "
                      "use {{signature}} where the chosen signature should appear, or leave the sign-off as written.", None, "signature")
    return BuildResult(
        ok=True, html=final, text=text, title=writer.title, preheader=preheader or writer.preheader, errors=[], warnings=importer.warnings,
        placeholders=placeholders_in(final, writer.title), components=sorted(importer.components_used), props_used=importer.props_used,
    )
