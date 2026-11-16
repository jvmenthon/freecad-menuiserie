# SPDX-License-Identifier: LGPL-2.1-or-later
"""Épaisseur tirée à la souris dans un sens puis dans l'autre (retours de jv, 2026-11-16).

Agrandir puis rapetisser l'épaisseur d'une pièce assemblée, par l'une ou l'autre face : au
relâchement, l'assemblage tient. Les pièces posées sur la face tirée la suivent pendant le
glissement (issue #133), comme celles qui s'allongent (ADR 0060) ; l'aperçu recalcule les
assemblages qui tiennent, pour que les usinages soient à leur place.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.test_epaisseur_cote import corner, holds

App = pytest.importorskip("FreeCAD")
drag = pytest.importorskip("freecad.menuiserie.features.part_drag")
Vec3 = pytest.importorskip("freecad.menuiserie.core.geometry").Vec3
machined = pytest.importorskip("freecad.menuiserie.features.machined_part")

pytestmark = pytest.mark.integration

SEQUENCES = ([25, 30, 20, 10, 5], [30, 18, 10], [25, 12], [10, 30, 12])


@pytest.mark.parametrize("piece", ["guest", "host"])
@pytest.mark.parametrize("lowered", [False, True])
@pytest.mark.parametrize("values", SEQUENCES)
def test_agrandir_puis_rapetisser(
    document: Any, piece: str, lowered: bool, values: list[float]
) -> None:
    host, guest, joint = corner(document)
    part = guest if piece == "guest" else host
    memento = drag.begin_drag(part)
    for value in values:
        shift = Vec3(0, 0, 18 - value) if lowered else Vec3(0, 0, 0)
        drag.resize_part(memento, "Thickness", value, shift, lowered=lowered)
    drag.end_drag(memento)
    assert holds(document, joint), joint.State


def test_piece_posee_suit_la_face_pendant_le_glissement(document: Any) -> None:
    """H tirée par sa face haute : I, posée dessus, monte avec elle à chaque pas."""
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    assert guest.Placement.Base.z == pytest.approx(25)
    drag.resize_part(memento, "Thickness", 12, Vec3(0, 0, 0))
    assert guest.Placement.Base.z == pytest.approx(12)
    messages = drag.end_drag(memento)
    assert any("suivent sa face" in m for m in messages)


def test_echap_rend_la_piece_posee(document: Any) -> None:
    host, guest, _joint = corner(document)
    memento = drag.begin_drag(host)
    drag.resize_part(memento, "Thickness", 25, Vec3(0, 0, 0))
    drag.restore(memento)
    assert guest.Placement.Base.z == pytest.approx(18)
    assert host.Thickness.Value == 18


def test_apercu_recalcule_les_pieces_usinees(document: Any) -> None:
    """Pendant le glissement, les pièces usinées (celle de H, allongée, comprise) sont
    recalculées avec leurs assemblages : la vue 3D montre les usinages à leur place."""
    host, guest, _joint = corner(document)
    machined_host = machined.machined_part_of(host)
    machined_guest = machined.machined_part_of(guest)
    assert machined_host is not None and machined_guest is not None
    memento = drag.begin_drag(guest)
    drag.resize_part(memento, "Thickness", 30, Vec3(0, 0, 0))
    assert machined_host.Shape.BoundBox.XLength == pytest.approx(412)
    assert machined_host.Shape.BoundBox.XMin == pytest.approx(-12)
    assert machined_guest.Shape.BoundBox.XLength == pytest.approx(30)
    drag.restore(memento)
    assert machined_host.Shape.BoundBox.XLength == pytest.approx(400)
