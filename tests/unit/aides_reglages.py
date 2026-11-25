# SPDX-License-Identifier: LGPL-2.1-or-later
"""Groupe de paramètres FreeCAD simulé (``ParamGet``) pour les tests des réglages."""

from __future__ import annotations

from typing import Any

_TYPES = {"Bool": "Boolean", "Int": "Integer", "Float": "Float", "String": "String"}


class FakeParamGroup:
    """Groupe de paramètres : ``Get…``, ``Set…``, ``Rem…`` et ``GetContents`` comme FreeCAD."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], Any] = {}

    def GetContents(self) -> list[tuple[str, str, Any]] | None:
        return [(kind, key, value) for (kind, key), value in self.values.items()] or None

    def __getattr__(self, name: str) -> Any:
        for prefix in ("Get", "Set", "Rem"):
            suffix = name.removeprefix(prefix)
            if name.startswith(prefix) and suffix in _TYPES:
                return getattr(self, f"_{prefix.lower()}")(_TYPES[suffix])
        raise AttributeError(name)

    def _get(self, kind: str) -> Any:
        return lambda key, default=None: self.values.get((kind, key), default)

    def _set(self, kind: str) -> Any:
        return lambda key, value: self.values.__setitem__((kind, key), value)

    def _rem(self, kind: str) -> Any:
        return lambda key: self.values.pop((kind, key), None)
