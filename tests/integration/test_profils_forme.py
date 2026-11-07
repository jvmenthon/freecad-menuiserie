# SPDX-License-Identifier: LGPL-2.1-or-later
"""Solide ``Part`` d'une section balayée (issue #5, CH-a, ADR 0029)."""

from __future__ import annotations

import math

import pytest

from freecad.menuiserie.core.edges import EdgeFamily, edge_cut, parse_edge
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.features.extrusion_shape import extrusion_shape

pytestmark = pytest.mark.integration

pytest.importorskip("FreeCAD")
pytest.importorskip("Part")

PIECE = Dimensions(600.0, 300.0, 20.0)
CASES = [
    (EdgeFamily.CHAMFER, 4.0, 3.0),
    (EdgeFamily.ROUND, 5.0, 5.0),
    (EdgeFamily.ROUND, 6.0, 3.0),
    (EdgeFamily.COVE, 4.0, 4.0),
    (EdgeFamily.BULLNOSE, 5.0, 5.0),
    (EdgeFamily.BEAK, 4.0, 3.0),
    (EdgeFamily.OGEE, 8.0, 6.0),
]


@pytest.mark.parametrize(("family", "a", "b"), CASES)
@pytest.mark.parametrize("code", ["Z+Y-", "Z-X+", "Y+X-"])
def test_solide_valide_au_volume_de_la_section(
    family: EdgeFamily, a: float, b: float, code: str
) -> None:
    cut = edge_cut(PIECE, parse_edge(code), family, a, b)
    shape = extrusion_shape(cut)
    assert shape.isValid()
    assert len(shape.Solids) == 1
    # Les arcs elliptiques sont des B-splines : écart relatif de l'ordre du millionième.
    assert shape.Volume == pytest.approx(cut.volume(), rel=1e-4)
    assert not math.isnan(shape.Volume)
