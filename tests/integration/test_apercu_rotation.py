# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aperçu et rotation de la pièce (J6c, critères V3 à V6) côté document, dans ``freecadcmd``.

Le panneau écrit le ``Placement`` par :func:`snap_part` et :func:`rotate_part`, recalcule la
pièce, puis valide ou abandonne la transaction : ces tests rejouent cette suite d'appels.
"""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.snap import FaceTarget, Frame, Turn
from freecad.menuiserie.features.freecad_types import placement_expression
from tests.integration.cadre import Cadre

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
placement_module = pytest.importorskip("freecad.menuiserie.features.placement")

CREATE = "Créer une pièce de bois"
SnapSession = placement_module.SnapSession
X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)


def face(name: str, origin: Vec3, x: Vec3, z: Vec3) -> FaceTarget:
    """Face plane de 600 x 300 mm, repère d'appui d'origine ``origin``, d'axe x et de normale z."""
    y = Vec3(z.y * x.z - z.z * x.y, z.z * x.x - z.x * x.z, z.x * x.y - z.y * x.x)
    return FaceTarget(name, Frame(origin, x, y, z), (600.0, 300.0), planar=True)


def created(doc: Any, session: Any = None) -> Any:
    """Pièce créée comme par la commande, dans la transaction de création restée ouverte."""
    doc.UndoMode = 1
    doc.openTransaction(CREATE)
    obj = wood_part.create_wood_part(doc)
    if session is not None:
        placement_module.snap_part(obj, session)
    obj.recompute()
    return obj


def bounds(obj: Any) -> tuple[float, ...]:
    box = obj.Shape.BoundBox
    return tuple(round(v, 6) for v in (box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax))


def assert_same_placement(left: Any, right: Any) -> None:
    assert left.Base.isEqual(right.Base, 1e-9)
    assert left.Rotation.isSame(right.Rotation, 1e-9)


# --- Conversions ---------------------------------------------------------------------------


def test_placement_d_equerre_sans_bruit_numerique() -> None:
    rotation = ((0.0, -1.0 + 1e-12, 0.0), (1.0, 1e-13, 0.0), (0.0, 0.0, 1.0))
    placement = placement_module.to_placement(RigidTransform(rotation, Vec3(1.0, 2.0, 3.0)))
    assert placement.Rotation.isSame(App.Rotation(App.Vector(0, 0, 1), 90), 1e-14)
    assert placement.Base.isEqual(App.Vector(1, 2, 3), 1e-12)


def test_placement_local_d_un_conteneur_tourne(document: Any) -> None:
    container = App.Placement(App.Vector(1000, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    wanted = App.Placement(App.Vector(1000, 50, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    local = placement_module.local_placement(wanted, container)
    assert_same_placement(container.multiply(local), wanted)
    assert local.Base.isEqual(App.Vector(50, 0, 0), 1e-9)


def test_pose_dans_un_std_part(document: Any) -> None:
    part = document.addObject("App::Part", "Meuble")
    obj = wood_part.create_wood_part(document)
    placement_module.add_to_container(obj, part)
    placement_module.add_to_container(obj, None)
    assert obj in part.Group
    assert obj.getParentGeoFeatureGroup() == part


# --- V3 : annuler, rétablir ----------------------------------------------------------------


def test_annuler_la_creation_pivotee_ne_laisse_rien(document: Any) -> None:
    session = SnapSession()
    obj = created(document, session)
    placement_module.rotate_part(obj, Turn.X, session)
    obj.recompute()
    document.abortTransaction()
    assert document.Objects == []
    assert document.UndoCount == 0


def test_ok_une_seule_entree_avec_le_placement(document: Any) -> None:
    session = SnapSession()
    obj = created(document, session)
    placement_module.rotate_part(obj, Turn.Z, session)
    obj.recompute()
    turned = obj.Placement.copy()
    document.commitTransaction()
    document.recompute()
    assert document.UndoNames == [CREATE]
    assert_same_placement(obj.Placement, turned)
    document.undo()
    assert document.Objects == []
    document.redo()
    assert_same_placement(document.Objects[0].Placement, turned)


def test_annuler_la_modification_retablit_le_placement(document: Any) -> None:
    obj = created(document)
    document.commitTransaction()
    before = obj.Placement.copy()
    document.openTransaction("Modifier une pièce de bois")
    placement_module.rotate_part(obj, Turn.Y)
    obj.recompute()
    assert not obj.Placement.Rotation.isSame(before.Rotation, 1e-9)
    document.abortTransaction()
    document.recompute()
    assert_same_placement(obj.Placement, before)


# --- V4 : boutons X, Y, Z ------------------------------------------------------------------


@pytest.mark.parametrize("turn", list(Turn))
def test_quatre_quarts_de_tour_en_creation_reviennent_au_depart(document: Any, turn: Turn) -> None:
    session = SnapSession(targets=(face("dessus", Vec3(0, 0, 100), X, Z),))
    obj = created(document, session)
    start = obj.Placement.copy()
    assert bounds(obj) == (0, 800, 0, 200, 100, 122)
    for _ in range(4):
        assert placement_module.rotate_part(obj, turn, session)
        obj.recompute()
        assert obj.Shape.BoundBox.ZMin == pytest.approx(100)  # reste posée sur la face
        assert obj.Shape.BoundBox.XMin == pytest.approx(0)
        assert obj.Shape.BoundBox.YMin == pytest.approx(0)
    assert_same_placement(obj.Placement, start)


def test_quart_de_tour_x_met_la_piece_sur_chant(document: Any) -> None:
    session = SnapSession(targets=(face("dessus", Vec3(0, 0, 100), X, Z),))
    obj = created(document, session)
    placement_module.rotate_part(obj, Turn.X, session)
    obj.recompute()
    assert bounds(obj) == (0, 800, 0, 22, 100, 300)


@pytest.mark.parametrize("turn", list(Turn))
def test_rotation_sur_place_centre_fixe(document: Any, turn: Turn) -> None:
    obj = created(document)
    obj.Placement = App.Placement(App.Vector(10, 20, 30), App.Rotation(App.Vector(0, 0, 1), 30))
    obj.recompute()
    center = obj.Shape.BoundBox.Center
    start = obj.Placement.copy()
    for count in range(1, 5):
        placement_module.rotate_part(obj, turn)
        obj.recompute()
        local_center = obj.Placement.multVec(App.Vector(400, 100, 11))
        assert local_center.isEqual(start.multVec(App.Vector(400, 100, 11)), 1e-6)
        if count == 1:
            assert not obj.Placement.Rotation.isSame(start.Rotation, 1e-9)
    assert_same_placement(obj.Placement, start)
    assert obj.Shape.BoundBox.Center.isEqual(center, 1e-6)


def test_rotation_autour_des_axes_du_document(document: Any) -> None:
    obj = created(document)
    obj.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    placement_module.rotate_part(obj, Turn.X)
    # Quart de tour direct autour de X du document, appliqué après le placement existant.
    expected = App.Rotation(App.Vector(1, 0, 0), 90).multiply(App.Rotation(App.Vector(0, 0, 1), 90))
    assert obj.Placement.Rotation.isSame(expected, 1e-9)


def test_sens_du_fil_inchange_par_la_rotation(document: Any) -> None:
    obj = created(document)
    grain = (obj.GrainDirection, obj.PreferredGrainDirection)
    session = SnapSession()
    for turn in Turn:
        placement_module.rotate_part(obj, turn, session)
        obj.recompute()
    assert (obj.GrainDirection, obj.PreferredGrainDirection) == grain


def test_la_piece_usinee_suit_la_rotation(cadre: Cadre) -> None:
    cadre.assemble((("M1", "T1"),))
    blank = cadre.parts["T1"]
    # Demi-tour autour de la longueur de la traverse (axe Y du document) : même encombrement,
    # le tenon reste valide et la pièce usinée est recalculée à la nouvelle orientation. (Une
    # rotation qui sort la traverse du montant rend le tenon invalide : la pièce usinée n'est
    # alors pas recalculée, comme pour toute brute déplacée hors de son assemblage.)
    before = blank.Placement
    placement_module.rotate_part(blank, Turn.Y)
    placement_module.rotate_part(blank, Turn.Y)
    assert blank.Placement != before
    machined = cadre.machined("T1")
    cadre.doc.recompute()
    assert machined.Placement == blank.Placement
    assert machined.isValid()
    assert len(machined.Shape.Solids) == 1


# --- V6 : placement piloté ------------------------------------------------------------------


def test_placement_pilote_par_expression_refuse_la_rotation(document: Any) -> None:
    obj = created(document)
    assert placement_expression(obj) is None
    obj.setExpression("Placement.Base.x", "10 mm")
    obj.recompute()
    assert placement_expression(obj) == "Placement.Base.x"
    before = obj.Placement.copy()
    assert placement_module.rotate_part(obj, Turn.Z) is False
    assert placement_module.rotate_part(obj, Turn.Z, SnapSession()) is False
    assert_same_placement(obj.Placement, before)


# --- Q2 : la saisie du menuisier l'emporte ---------------------------------------------------


def test_etirement_initial_puis_saisie_conservee(document: Any) -> None:
    top = face("dessus", Vec3(0, 0, 0), X, Z)
    left = face("gauche", Vec3(22, 0, 0), Y, X)
    right = face("droite", Vec3(578, 0, 0), Y, Vec3(-1, 0, 0))
    session = SnapSession(targets=(top, left, right))
    obj = wood_part.create_wood_part(document)
    assert placement_module.snap_part(obj, session) is True
    assert (obj.Length.Value, obj.Width.Value) == (556, 200)  # valeur initiale (Q2)
    assert obj.Placement.Base.x == pytest.approx(22)
    obj.Length = 700  # la saisie du menuisier l'emporte
    assert placement_module.snap_part(obj, session) is False
    assert (obj.Length.Value, obj.Width.Value, obj.Thickness.Value) == (700, 200, 22)
    assert obj.Placement.Base.x == pytest.approx(22)  # reste contre la première joue
