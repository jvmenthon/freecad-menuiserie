# SPDX-License-Identifier: LGPL-2.1-or-later
"""Écriture d'une rotation libre (RO-b, critères B1 à B5) dans ``freecadcmd``."""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.features.freecad_types import placement_expression
from tests.integration.cadre import stale_or_invalid

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
part_rotate = pytest.importorskip("freecad.menuiserie.features.part_rotate")
part_drag = pytest.importorskip("freecad.menuiserie.features.part_drag")


def placement_angles(obj: Any) -> tuple[float, float, float]:
    yaw, pitch, roll = obj.Placement.Rotation.getYawPitchRoll()
    return (roll, pitch, yaw)


def center(obj: Any) -> Any:
    size = (obj.Length.Value, obj.Width.Value, obj.Thickness.Value)
    return obj.Placement.multVec(App.Vector(size[0] / 2, size[1] / 2, size[2] / 2))


@pytest.fixture
def piece(document: Any) -> Any:
    obj = wood_part.create_wood_part(document)
    obj.Placement = App.Placement(App.Vector(100, 200, 300), App.Rotation())
    document.recompute()
    return obj


def test_b1_angles_absolus_centre_fixe(document: Any, piece: Any) -> None:
    before = center(piece)
    assert part_rotate.rotate_to(piece, (90.0, 30.0, -45.0))
    assert placement_angles(piece) == pytest.approx((90.0, 30.0, -45.0), abs=1e-6)
    assert center(piece).isEqual(before, 1e-6)


def test_b1_expression_sur_le_placement_rien_n_est_ecrit(document: Any, piece: Any) -> None:
    piece.setExpression("Placement.Base.x", "50 mm")
    document.recompute()
    before = App.Placement(piece.Placement)
    assert placement_expression(piece) is not None
    assert part_rotate.rotate_to(piece, (0.0, 0.0, 45.0)) is False
    assert piece.Placement == before


def test_b2_piece_usinee_ecrit_la_brute(document: Any, piece: Any) -> None:
    machined = pytest.importorskip("freecad.menuiserie.features.machined_part")
    wrapper = machined.create_machined_part(piece)
    document.recompute()
    assert part_rotate.rotate_to(wrapper, (0.0, 0.0, 30.0))
    assert placement_angles(piece) == pytest.approx((0.0, 0.0, 30.0), abs=1e-6)
    assert wrapper.Placement.isSame(piece.Placement, 1e-9)


def test_b3_geste_absolu_depuis_le_debut_et_echap(document: Any, piece: Any) -> None:
    start = App.Placement(piece.Placement)
    memento = part_drag.begin_drag(piece)
    for angle in (10.0, 40.0, 25.0):
        assert part_rotate.rotate_by(memento, 2, angle)
    assert placement_angles(piece) == pytest.approx((0.0, 0.0, 25.0), abs=1e-6)  # pas 75
    part_drag.restore(memento)
    assert piece.Placement.Base.isEqual(start.Base, 1e-9)
    assert piece.Placement.Rotation.isSame(start.Rotation, 1e-9)


def test_b3_geste_tourne_autour_de_l_axe_fixe_du_document(document: Any, piece: Any) -> None:
    piece.Placement = App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), 90))
    memento = part_drag.begin_drag(piece)
    part_rotate.rotate_by(memento, 2, 90.0)
    expected = App.Rotation(App.Vector(0, 0, 1), 90).multiply(App.Rotation(App.Vector(1, 0, 0), 90))
    assert piece.Placement.Rotation.isSame(expected, 1e-9)


def test_b4_fin_de_rotation_un_recalcul_et_distance_mise_a_jour(document: Any, piece: Any) -> None:
    memento = part_drag.begin_drag(piece)
    part_rotate.rotate_by(memento, 1, 30.0)
    assert part_rotate.end_rotation(memento) == []
    assert stale_or_invalid(document) == []
    assert placement_angles(piece) == pytest.approx((0.0, 30.0, 0.0), abs=1e-6)


def test_b5_dans_un_conteneur_les_angles_sont_ceux_du_placement_local(
    document: Any, piece: Any
) -> None:
    container = document.addObject("App::Part", "Conteneur")
    container.Placement = App.Placement(
        App.Vector(1000, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90)
    )
    container.addObject(piece)
    piece.Placement = App.Placement(App.Vector(10, 20, 30), App.Rotation())
    before = center(piece)
    assert part_rotate.rotate_to(piece, (0.0, 0.0, 20.0))
    assert placement_angles(piece) == pytest.approx((0.0, 0.0, 20.0), abs=1e-6)  # local
    assert center(piece).isEqual(before, 1e-6)
