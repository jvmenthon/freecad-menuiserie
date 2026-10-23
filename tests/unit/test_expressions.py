# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture des expressions d'un objet (``freecad_types``, issue #40), sans FreeCAD."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from types import ModuleType

import pytest

from tests.unit.aides_freecad import simulated_freecad


@pytest.fixture
def types_module(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """``features.freecad_types`` importé dans le bloc qui isole ``features/`` des autres
    tests."""
    with simulated_freecad(monkeypatch):
        from freecad.menuiserie.features import freecad_types

        yield freecad_types


@dataclass
class FakeObject:
    """Objet avec un ``ExpressionEngine`` comme celui de FreeCAD : (chemin, expression)."""

    ExpressionEngine: list[tuple[str, str]] = field(default_factory=list)


PILOTE = FakeObject(
    [
        ("Length", "Bureau.Width - 44 mm"),
        (".Placement.Base.y", "Bureau.Depth - Width"),
        (".Placement.Base.x", "22 mm"),
    ]
)


def test_chemins_sans_le_point_initial(types_module: ModuleType) -> None:
    assert types_module.expressions_of(PILOTE) == {
        "Length": "Bureau.Width - 44 mm",
        "Placement.Base.y": "Bureau.Depth - Width",
        "Placement.Base.x": "22 mm",
    }


def test_expression_d_une_propriete(types_module: ModuleType) -> None:
    assert types_module.expression_of(PILOTE, "Length") == "Bureau.Width - 44 mm"
    assert types_module.expression_of(PILOTE, "Width") is None
    assert types_module.has_expression(PILOTE, "Placement.Base.y")
    assert not types_module.has_expression(PILOTE, "Placement")


def test_premiere_expression_du_placement_par_ordre_alphabetique(
    types_module: ModuleType,
) -> None:
    assert types_module.placement_expression(PILOTE) == "Placement.Base.x"
    assert types_module.placement_expression(FakeObject([("Length", "800 mm")])) is None


def test_objet_sans_expression(types_module: ModuleType) -> None:
    assert types_module.expressions_of(FakeObject()) == {}
    assert types_module.placement_expression(FakeObject()) is None
