"""
What a module provides so its documents can be bulk-downloaded.

A source answers four questions, always inside one organization and for one user:

* ``open_scope``: may this user download from this exam / internship / payroll run, and what is it called? This is where
  the module's own permission rules are applied (the same ones its single-document download uses).
* ``placeholders``: which values each document can put into a file name, including the module's own custom fields.
* ``query`` / ``load``: the documents in that scope that exist (filtered, or by id). Never creates anything: a
  certificate that has not been issued yet is not in the list, so an export has no side effects.
* ``fetch``: the document's bytes, exactly as the module itself produces them for its single download or email.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.authentication.models import User


@dataclass(frozen=True)
class Placeholder:
    key: str
    label: str
    example: str = ""
    # Discovered from the module's own data (an exam's registration questions, imported student columns): the name of
    # that field in the module, which is where the value is read from.
    field: str | None = None

    @property
    def custom(self) -> bool:
        return self.field is not None


@dataclass(frozen=True)
class FilterOption:
    value: str
    label: str


@dataclass
class Scope:
    id: uuid.UUID | None
    label: str
    organization_id: uuid.UUID
    # Whatever the source wants to keep while it works (loaded rows, a template it renders with, ...).
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportItem:
    id: uuid.UUID
    title: str
    subtitle: str
    status: str | None
    values: dict[str, object]
    extension: str
    ref: Any = None


class DocumentSource(ABC):
    key: str
    label: str
    module: str
    document_type: str
    # What the scope id names ("exam", "internship", "payroll_run"), or None when the whole organization is the scope.
    scope_kind: str | None
    # The extension every document has, or None when each keeps its own (uploaded files).
    extension: str | None = "pdf"
    status_options: tuple[FilterOption, ...] = ()
    base_placeholders: tuple[Placeholder, ...] = ()
    presets: tuple[tuple[str, str], ...] = ()
    folder_presets: tuple[tuple[str, str], ...] = ()

    @abstractmethod
    async def open_scope(
        self, db: AsyncSession, user: User, organization_id: uuid.UUID, scope_id: uuid.UUID | None
    ) -> Scope:
        """Load the scope inside the organization and check the user may download from it (raise otherwise)."""

    async def placeholders(self, db: AsyncSession, scope: Scope) -> list[Placeholder]:
        return list(self.base_placeholders)

    @abstractmethod
    async def query(self, db: AsyncSession, scope: Scope, search: str | None, status: str | None) -> list[ExportItem]:
        """Every downloadable document in the scope matching the filters, in a stable order (no bytes)."""

    async def load(self, db: AsyncSession, scope: Scope, ids: list[uuid.UUID]) -> list[ExportItem]:
        """The documents with these ids that are still in the scope, in the order given. Ids outside it are dropped."""
        wanted = set(ids)
        found = {item.id: item for item in await self.query(db, scope, None, None) if item.id in wanted}
        return [found[i] for i in ids if i in found]

    @abstractmethod
    async def fetch(self, db: AsyncSession, scope: Scope, item: ExportItem) -> bytes:
        """The document's bytes."""


def matches(search: str | None, *fields: object) -> bool:
    if not search:
        return True
    needle = search.strip().lower()
    return any(needle in str(f).lower() for f in fields if f)


def custom_placeholders(labels: dict[str, str], taken: set[str], example: dict[str, str] | None = None) -> list[Placeholder]:
    """Placeholders for a module's own fields ({field: label}); a key that clashes with a built-in one gets ``info_``."""
    from modules.bulk_exports.filenames import to_key

    out: list[Placeholder] = []
    seen = set(taken)
    for raw, label in labels.items():
        key = to_key(raw)
        if not key:
            continue
        if key in seen:
            key = f"info_{key}"[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(Placeholder(key=key, label=label or raw, example=(example or {}).get(raw, ""), field=raw))
    return out


def custom_values(placeholders: list[Placeholder], data: dict | None) -> dict[str, object]:
    data = data or {}
    return {p.key: data.get(p.field) for p in placeholders if p.field is not None}
