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


def test_sur_l_axe_z_seulement_la_piece_ne_glisse_qu_en_hauteur() -> None:
    doc = App.newDocument("AlignementAxe")
    try:
        reference = _part(doc, (0, 0, 0))
        other = _part(doc, (300, 40, 150))
        api.align_faces(_face(reference, (100, 50, 20)), _face(other, (100, 50, 20)), axis="Z")
        doc.recompute()
        base = other.Placement.Base
        assert (base.x, base.y) == pytest.approx((300.0, 40.0))  # rien en X ni en Y
        assert other.Shape.BoundBox.ZMax == pytest.approx(20.0, abs=TOLERANCE)
    finally:
        App.closeDocument(doc.Name)


def test_sur_un_axe_parallele_aux_faces_refuse() -> None:
    doc = App.newDocument("AlignementAxePlan")
    try:
        first, second = _part(doc, (0, 0, 0)), _part(doc, (0, 0, 100))
        with pytest.raises(ValueError):
            api.align_faces(_face(first, (100, 50, 20)), _face(second, (100, 50, 20)), axis="X")
    finally:
        App.closeDocument(doc.Name)


def test_centres_confondus_sur_les_deux_axes_du_plan() -> None:
    doc = App.newDocument("AlignementCentres")
    try:
        reference = _part(doc, (0, 0, 0))
        other = _part(doc, (500, 300, 100), tilt=30.0)
        api.align_faces(
            _face(reference, (100, 50, 20)),
            _face(other, (100, 50, 20)),
            layout={"X": "center", "Y": "center"},
        )
        doc.recompute()
        box = other.Shape.BoundBox
        assert box.Center.x == pytest.approx(100.0, abs=TOLERANCE)
        assert box.Center.y == pytest.approx(50.0, abs=TOLERANCE)
        assert box.ZMax == pytest.approx(20.0, abs=TOLERANCE)  # au ras, centres confondus
    finally:
        App.closeDocument(doc.Name)


def test_disposition_inconnue_refusee_sans_bouger() -> None:
    doc = App.newDocument("AlignementCentreInconnu")
    try:
        reference = _part(doc, (0, 0, 0))
        other = _part(doc, (500, 300, 100))
        before = other.Placement.copy()
        with pytest.raises(ValueError, match="W=center"):
            api.align_faces(
                _face(reference, (100, 50, 20)),
                _face(other, (100, 50, 20)),
                layout={"X": "center", "W": "center"},
            )
        assert other.Placement.isSame(before, 1e-9)
    finally:
        App.closeDocument(doc.Name)


def test_parallele_a_x_puis_centree() -> None:
    doc = App.newDocument("AlignementParallele")
    try:
        reference = _part(doc, (0, 0, 0))
        other = api.make_wood_part(200, 100, 20, "chene", doc=doc)
        other.Placement = App.Placement(
            App.Vector(300, 200, 0), App.Rotation(App.Vector(0, 0, 1), 30)
        )
        doc.recompute()
        api.align_faces(
            _face(reference, (100, 50, 20)),
            _face(other, (100, 50, 20)),
            layout={"parallel": "X", "X": "center", "Y": "center"},
        )
        doc.recompute()
        box = other.Shape.BoundBox
        assert box.XLength == pytest.approx(200.0, abs=TOLERANCE)  # arêtes parallèles
        assert box.YLength == pytest.approx(100.0, abs=TOLERANCE)
        assert box.Center.x == pytest.approx(100.0, abs=TOLERANCE)
        assert box.Center.y == pytest.approx(50.0, abs=TOLERANCE)
    finally:
        App.closeDocument(doc.Name)


def test_debut_et_fin_bord_a_bord() -> None:
    """Une traverse au ras du bout d'un montant : début sur X, fin sur Y."""
    doc = App.newDocument("AlignementBords")
    try:
        reference = _part(doc, (0, 0, 0))
        other = _part(doc, (500, 300, 100))
        api.align_faces(
            _face(reference, (100, 50, 20)),
            _face(other, (100, 50, 20)),
            layout={"X": "start", "Y": "end"},
        )
        doc.recompute()
        box = other.Shape.BoundBox
        assert box.XMin == pytest.approx(0.0, abs=TOLERANCE)
        assert box.YMax == pytest.approx(100.0, abs=TOLERANCE)
    finally:
        App.closeDocument(doc.Name)


def test_axe_de_la_normale_refuse_sans_bouger() -> None:
    """Doute D9 : Z suit la normale des faces du dessus ; il est refusé avec un message."""
    doc = App.newDocument("AlignementNormale")
    try:
        reference = _part(doc, (0, 0, 0))
        other = _part(doc, (500, 300, 100))
        before = other.Placement.copy()
        with pytest.raises(ValueError, match="traverse les faces"):
            api.align_faces(
                _face(reference, (100, 50, 20)), _face(other, (100, 50, 20)), layout={"Z": "end"}
            )
        assert other.Placement.isSame(before, 1e-9)
    finally:
        App.closeDocument(doc.Name)
