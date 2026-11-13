# SPDX-License-Identifier: LGPL-2.1-or-later
"""``api.align_faces`` : tourner puis plaquer une pièce sur la face d'une autre (AL-b, ADR 0054)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.elements_choisis import element_name

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
api = pytest.importorskip("freecad.menuiserie.api")

TOLERANCE = 1e-4


def _part(doc: Any, base: tuple[float, float, float], tilt: float = 0.0) -> Any:
    obj = api.make_wood_part(200, 100, 20, "chene", doc=doc)
    obj.Placement = App.Placement(App.Vector(*base), App.Rotation(App.Vector(0, 1, 0), tilt))
    doc.recompute()
    return obj


def _face(obj: Any, local: tuple[float, float, float]) -> Any:
    near = obj.Placement.multVec(App.Vector(*local))
    return api.PickedElement(obj, element_name(obj, "Face", (near.x, near.y, near.z)))


def test_dessus_incline_ramene_au_ras_du_dessus_de_la_reference() -> None:
    doc = App.newDocument("Alignement")
    try:
        reference = _part(doc, (0, 0, 0))
        tilted = _part(doc, (0, 0, 100), tilt=30.0)
        api.align_faces(_face(reference, (100, 50, 20)), _face(tilted, (100, 50, 20)))
        doc.recompute()
        box = tilted.Shape.BoundBox
        assert box.ZMax == pytest.approx(20.0, abs=TOLERANCE)  # même plan que le dessus
        assert box.ZMin == pytest.approx(0.0, abs=TOLERANCE)  # la pièce est redressée
    finally:
        App.closeDocument(doc.Name)


def test_face_contre_face_pose_la_piece_sous_la_reference() -> None:
    doc = App.newDocument("AlignementContre")
    try:
        reference = _part(doc, (0, 0, 0))
        other = _part(doc, (0, 0, 300))
        api.align_faces(_face(reference, (100, 50, 0)), _face(other, (100, 50, 20)), mode="facing")
        doc.recompute()
        assert other.Shape.BoundBox.ZMax == pytest.approx(0.0, abs=TOLERANCE)
    finally:
        App.closeDocument(doc.Name)


def test_deux_faces_du_meme_objet_refusees() -> None:
    doc = App.newDocument("AlignementMeme")
    try:
        part = _part(doc, (0, 0, 0))
        with pytest.raises(ValueError):
            api.align_faces(_face(part, (100, 50, 20)), _face(part, (100, 50, 0)))
    finally:
        App.closeDocument(doc.Name)


def test_mode_inconnu_refuse() -> None:
    doc = App.newDocument("AlignementMode")
    try:
        first, second = _part(doc, (0, 0, 0)), _part(doc, (0, 0, 100))
        with pytest.raises(ValueError):
            api.align_faces(_face(first, (100, 50, 20)), _face(second, (100, 50, 20)), mode="x")
    finally:
        App.closeDocument(doc.Name)
