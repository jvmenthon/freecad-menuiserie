# SPDX-License-Identifier: LGPL-2.1-or-later
"""Entrée brute de la liste ``materials`` et objets JSON à clés en double."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from freecad.menuiserie.core.materials._issues import (
    MAX_LISTED_KEYS,
    LibraryFormatError,
    LibraryIssue,
    Severity,
    make_issue,
    unknown_keys_params,
)
from freecad.menuiserie.core.materials._messages import (
    ENTRY_MISSING_FIELD,
    ENTRY_UNKNOWN_KEYS,
    ENTRY_UNKNOWN_KEYS_MORE,
)
from freecad.menuiserie.core.text import quoted_value

_ENTRY_KEYS: Final = frozenset(
    {
        "id",
        "kind",
        "name",
        "density",
        "thicknesses",
        "rough_thicknesses",
        "color",
        "has_grain",
        "texture",
    }
)
TEXTURE_KEYS: Final = ("image", "size")


class JsonObject(dict[str, object]):
    """Objet JSON dont des clés apparaissent plusieurs fois (``json`` garde la dernière valeur)."""

    __slots__ = ("duplicate_keys",)

    def __init__(self, pairs: list[tuple[str, object]], duplicate_keys: tuple[str, ...]) -> None:
        super().__init__(pairs)
        self.duplicate_keys = duplicate_keys


def json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """``object_pairs_hook`` : objet JSON ordinaire, ou :class:`JsonObject` si clés en double."""
    result = dict(pairs)
    if len(result) == len(pairs):
        return result
    seen: set[str] = set()
    duplicates: dict[str, None] = {}
    for key, _ in pairs:
        if key in seen:
            duplicates[key] = None
        seen.add(key)
    return JsonObject(pairs, tuple(duplicates))


def _contains_duplicate_keys(value: object) -> bool:
    """Vrai si ``value`` est ou contient un objet JSON à clés en double (sans récursion)."""
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, JsonObject):
            return True
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
    return False


def duplicated_field(data: Mapping[str, object]) -> str | None:
    """Clé en double de ``data``, ou clé dont la valeur contient un objet à clés en double."""
    if isinstance(data, JsonObject):
        return data.duplicate_keys[0]
    return next((key for key, value in data.items() if _contains_duplicate_keys(value)), None)


@dataclass(frozen=True)
class Entry:
    """Entrée brute de la liste ``materials`` en cours de validation."""

    source: str
    position: int
    data: Mapping[str, object]
    folder: Path | None = None
    material_id: str | None = None

    @property
    def shown_id(self) -> str:
        """Identifiant cité dans les anomalies : l'identifiant validé, sinon « #position »."""
        return self.material_id if self.material_id is not None else f"#{self.position}"

    def issue(self, severity: Severity, template: str, field: str, **params: str) -> LibraryIssue:
        return make_issue(
            severity,
            self.source,
            template,
            self.material_id,
            id=self.shown_id,
            field=field,
            **params,
        )

    def error(self, template: str, field: str, **params: str) -> LibraryFormatError:
        return LibraryFormatError(self.issue(Severity.ERROR, template, field, **params))

    def require(self, key: str) -> object:
        if key not in self.data:
            raise self.error(ENTRY_MISSING_FIELD, key)
        return self.data[key]

    def unknown_keys_issues(self) -> list[LibraryIssue]:
        """Au plus un avertissement, qui liste les clés inconnues de l'entrée."""
        keys = [quoted_value(key) for key in self.data if key not in _ENTRY_KEYS]
        texture = self.data.get("texture")
        if isinstance(texture, dict):
            keys += [f"texture.{quoted_value(k)}" for k in texture if k not in TEXTURE_KEYS]
        if not keys:
            return []
        template = ENTRY_UNKNOWN_KEYS_MORE if len(keys) > MAX_LISTED_KEYS else ENTRY_UNKNOWN_KEYS
        params = unknown_keys_params(keys)
        issue = make_issue(
            Severity.WARNING, self.source, template, self.material_id, id=self.shown_id, **params
        )
        return [issue]
