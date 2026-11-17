# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD simulé pour importer ``features/`` dans les tests unitaires."""

from __future__ import annotations

import importlib
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
            if name.startswith(("freecad.menuiserie.features", "freecad.menuiserie._api")) or (
                name == "freecad.menuiserie.api"
            ):
                del sys.modules[name]
        features = sys.modules.get("freecad.menuiserie")
        if features is not None and hasattr(features, "features"):
            delattr(features, "features")


@contextmanager
def imported_with_stubs(module: str, stubs: dict[str, Any]) -> Iterator[Any]:
    """Module ``module`` importé avec les modules ``stubs`` (nom → doublure) à la place des vrais ;
    à la sortie, les modules de l'atelier importés dans le bloc sont retirés et les modules
    remplacés rendus, pour ne pas fausser les autres tests."""
    before = set(sys.modules)
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        yield importlib.import_module(module)
    finally:
        for name in set(sys.modules) - before:
            if name.startswith("freecad.menuiserie"):
                del sys.modules[name]
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
