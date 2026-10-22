# SPDX-License-Identifier: LGPL-2.1-or-later
"""``snap_geometry.unit`` refuse un vecteur de norme nulle (revue finale de J6, non bloquant 1) :
``ValueError``, que l'accrochage rattrape avec ``ERRORS``, et non ``ZeroDivisionError``. Sur un
FreeCAD simulé ; le même cas est joué sur le vrai ``App.Vector`` par
``tests/integration/test_accrochage_selection.py``."""

from __future__ import annotations

import math
import sys
import types
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest


@dataclass
class _Vector:
    """``App.Vector`` minimal : composantes et norme."""

    x: float
    y: float
    z: float

    @property
    def Length(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)


@pytest.fixture
def geometry(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """``features.snap_geometry`` importé sur un FreeCAD simulé, puis retiré de ``sys.modules``."""
    freecad: Any = types.ModuleType("FreeCAD")
    freecad.Vector = _Vector
    freecad.Base = MagicMock()
    before = set(sys.modules)
    monkeypatch.setitem(sys.modules, "FreeCAD", freecad)
    monkeypatch.setitem(sys.modules, "Part", MagicMock())
    from freecad.menuiserie.features import snap_geometry

    yield snap_geometry
    for name in set(sys.modules) - before:
        if name.startswith("freecad.menuiserie.features"):
            del sys.modules[name]
    package = sys.modules.get("freecad.menuiserie")
    if package is not None and hasattr(package, "features"):
        delattr(package, "features")


def test_vecteur_normal_norme(geometry: Any) -> None:
    result = geometry.unit(_Vector(0.0, 3.0, 4.0))
    assert (result.x, result.y, result.z) == pytest.approx((0.0, 0.6, 0.8))


@pytest.mark.parametrize("components", [(0.0, 0.0, 0.0), (1e-12, 0.0, 0.0), (0.0, -1e-10, 0.0)])
def test_vecteur_nul_leve_value_error(geometry: Any, components: tuple[float, ...]) -> None:
    with pytest.raises(ValueError, match="norme nulle"):
        geometry.unit(_Vector(*components))
