# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lecture des expressions d'un objet (``freecad_types``, issue #40), sans FreeCAD."""

from __future__ import annotations

from dataclasses import dataclass, field

from freecad.menuiserie.features.freecad_types import (
    expression_of,
    expressions_of,
    has_expression,
    placement_expression,
)


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


def test_chemins_sans_le_point_initial() -> None:
    assert expressions_of(PILOTE) == {
        "Length": "Bureau.Width - 44 mm",
        "Placement.Base.y": "Bureau.Depth - Width",
        "Placement.Base.x": "22 mm",
    }


def test_expression_d_une_propriete() -> None:
    assert expression_of(PILOTE, "Length") == "Bureau.Width - 44 mm"
    assert expression_of(PILOTE, "Width") is None
    assert has_expression(PILOTE, "Placement.Base.y")
    assert not has_expression(PILOTE, "Placement")


def test_premiere_expression_du_placement_par_ordre_alphabetique() -> None:
    assert placement_expression(PILOTE) == "Placement.Base.x"
    assert placement_expression(FakeObject([("Length", "800 mm")])) is None


def test_objet_sans_expression() -> None:
    vide = FakeObject()
    assert expressions_of(vide) == {}
    assert placement_expression(vide) is None
