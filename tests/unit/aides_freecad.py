# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD simulé pour importer ``features/`` dans les tests unitaires."""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest


class Stub(types.ModuleType):
    """Module FreeCAD de remplacement : tout attribut inconnu est un ``MagicMock``."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        value = MagicMock(name=name)
        setattr(self, name, value)
        return value


@contextmanager
def simulated_freecad(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """``FreeCAD`` et ``Part`` simulés (traduction neutre) le temps du bloc ; les modules de
    ``features/`` importés dans le bloc sont retirés de ``sys.modules`` à la sortie (les autres
    tests ne doivent pas les voir). Donne la liste des avertissements écrits."""
    report: list[str] = []
    freecad: Any = Stub("FreeCAD")
    freecad.Qt = types.SimpleNamespace(translate=lambda _context, text: text)
    freecad.Console = types.SimpleNamespace(PrintWarning=report.append)
    before = set(sys.modules)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "Part", Stub("Part"))
    try:
        yield report
    finally:
        for name in set(sys.modules) - before:
            if name.startswith("freecad.menuiserie.features") or name == "freecad.menuiserie.api":
                del sys.modules[name]
        features = sys.modules.get("freecad.menuiserie")
        if features is not None and hasattr(features, "features"):
            delattr(features, "features")
