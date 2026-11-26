# SPDX-License-Identifier: LGPL-2.1-or-later
"""Groupe de paramètres FreeCAD simulé (``ParamGet``) pour les tests des réglages."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests.unit.aides_freecad import simulated_freecad

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


@contextmanager
def settings_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Any]:
    """``features.settings`` importé avec un FreeCAD simulé : paramètres en mémoire (``.group``),
    dossier de données utilisateur dans ``tmp_path``."""
    group = FakeParamGroup()
    with simulated_freecad(monkeypatch):
        module: Any = importlib.import_module("freecad.menuiserie.features.settings")
        module.App.ParamGet = lambda _path: group
        module.App.getUserAppDataDir = lambda: str(tmp_path / "FreeCAD")
        module.group = group  # pour les tests
        yield module
