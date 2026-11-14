# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièce créée contre une face de pièce de bois (#136) : perpendiculaire, mêmes largeur et
épaisseur. Rejoue la suite d'appels de la commande : ``read_targets``, ``perpendicular_start``,
``make_wood_part``, ``new_session``, ``snap_part``."""

from __future__ import annotations

from typing import Any

import pytest

from freecad.menuiserie.core.geometry import Vec3

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
picked = pytest.importorskip("freecad.menuiserie.features.picked")
perpendicular = pytest.importorskip("freecad.menuiserie.features.perpendicular")
placement_module = pytest.importorskip("freecad.menuiserie.features.placement")
geometry = pytest.importorskip("freecad.menuiserie.features.snap_geometry")
targets = pytest.importorskip("freecad.menuiserie.features.snap_targets")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")
pieces_galbees = pytest.importorskip("tests.integration.pieces_galbees")
cadre = pytest.importorskip("tests.integration.cadre")
types_assemblages = pytest.importorskip("tests.integration.types_assemblages")

ABOVE = Vec3(0, 0, 1)


@pytest.fixture
def board(document: Any) -> Any:
    """Pièce de bois 800 x 100 x 30 en (0, 0, 0)."""
    obj = api.make_wood_part(800, 100, 30, doc=document)
    document.recompute()
    return obj


def face_at(obj: Any, normal: tuple[float, float, float], coordinate: float) -> str:
    shape = geometry.global_shape(obj)
    wanted = App.Vector(*normal)
    for index, face in enumerate(shape.Faces, start=1):
        u, v = face.Surface.parameter(face.CenterOfMass)
        if (
            face.normalAt(u, v).getAngle(wanted) < 1e-6
            and abs(face.CenterOfMass.dot(wanted) - coordinate) < 1e-6
        ):
            return f"Face{index}"
    raise AssertionError("face introuvable")


def create_against(
    document: Any, root: Any, subname: str, click: Vec3 | None = None
) -> tuple[Any, Any]:
    """(pièce créée, départ perpendiculaire) comme le fait la commande ; ``click`` : point cliqué
    (coordonnées globales)."""
    reading = targets.read_targets([picked.PickedElement(root, subname, click)], ABOVE)
    start = perpendicular.perpendicular_start(reading)
    assert start is not None
    part = api.make_wood_part(width=start.width, thickness=start.thickness, doc=document)
    session = targets.new_session(start.reading, wood_part.dimensions_of(part), start.orientation)
    placement_module.snap_part(part, session)
    document.recompute()
    return part, start


def test_extremite_angle_droit_avec_la_piece(document: Any, board: Any) -> None:
    part, start = create_against(document, board, face_at(board, (1, 0, 0), 800))
    assert (start.width, start.thickness) == (100, 30)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == 800  # appuyée sur l'extrémité
    assert round(box.XMax - box.XMin, 6) == 30  # son épaisseur part de la face
    assert round(box.ZMax - box.ZMin, 6) == 800  # longueur selon l'épaisseur de l'autre pièce
    assert (round(box.YMin, 6), round(box.YMax, 6)) == (0, 100)  # largeur parallèle


def test_grande_face_dresse_la_piece(document: Any, board: Any) -> None:
    part, _start = create_against(document, board, face_at(board, (0, 0, 1), 30))
    box = geometry.global_shape(part).BoundBox
    assert round(box.ZMin, 6) == 30  # posée sur la face, longueur vers le haut
    assert round(box.ZMax - box.ZMin, 6) == 800
    assert round(box.YMax - box.YMin, 6) == 100  # largeur parallèle à celle de la pièce
    assert round(box.XMax - box.XMin, 6) == 30


def test_largeur_et_epaisseur_restent_modifiables(document: Any, board: Any) -> None:
    part, _start = create_against(document, board, face_at(board, (1, 0, 0), 800))
    part.Width = 60
    document.recompute()
    assert part.Width.Value == 60


def test_aucun_depart_pour_un_objet_d_un_autre_atelier(document: Any) -> None:
    cube = document.addObject("Part::Box", "Bloc")
    document.recompute()
    reading = targets.read_targets([picked.PickedElement(cube, "Face6", None)], ABOVE)
    assert perpendicular.perpendicular_start(reading) is None


def converted_rail(document: Any, placement: Any) -> Any:
    """Pièce en bois (corps converti) de la traverse galbée, posée au ``placement``."""
    rail = pieces_galbees.shaped(pieces_galbees.curved_rail(document))
    rail.Placement = placement
    document.recompute()
    return rail


def test_piece_convertie_extremite_perpendiculaire(document: Any) -> None:
    rail = converted_rail(document, App.Placement(App.Vector(100, 50, 0), App.Rotation()))
    xmax = geometry.global_shape(rail).BoundBox.XMax
    part, start = create_against(document, rail, face_at(rail, (1, 0, 0), xmax))
    assert (round(start.width, 6), round(start.thickness, 6)) == (95, 45)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == round(xmax, 6)
    assert round(box.XMax - box.XMin, 6) == 45  # son épaisseur part de la face
    # longueur (par défaut) selon l'épaisseur de la traverse
    assert round(box.ZMax - box.ZMin, 6) == round(part.Length.Value, 6)


def test_piece_convertie_tournee_perpendiculaire(document: Any) -> None:
    turned = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
    rail = converted_rail(document, turned)
    ymax = geometry.global_shape(rail).BoundBox.YMax
    part, _start = create_against(document, rail, face_at(rail, (0, 1, 0), ymax))
    box = geometry.global_shape(part).BoundBox
    assert round(box.YMin, 6) == round(ymax, 6)  # appuyée sur l'extrémité tournée
    assert round(box.ZMax - box.ZMin, 6) == round(part.Length.Value, 6)


def test_piece_convertie_section_de_la_face_selectionnee(document: Any) -> None:
    """Bout plus étroit que l'encombrement (pièce en L) : la nouvelle pièce prend la largeur de la
    face sélectionnée, pas celle de la pièce, et reste sur la face."""
    solid = Part.makeBox(400, 100, 50).cut(Part.makeBox(200, 60, 50, App.Vector(200, 40, 0)))
    source = document.addObject("Part::Feature", "EnL")
    source.Shape = solid
    document.recompute()
    angle = pieces_galbees.shaped(source)
    assert round(angle.Width.Value, 6) == 100
    xmax = geometry.global_shape(angle).BoundBox.XMax
    part, start = create_against(document, angle, face_at(angle, (1, 0, 0), xmax))
    assert (round(start.width, 6), round(start.thickness, 6)) == (40, 50)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == round(xmax, 6)
    assert round(box.YMax - box.YMin, 6) == 40
    face_box = geometry.global_shape(angle).BoundBox
    assert round(box.YMin - face_box.YMin, 6) == 0  # alignée sur la face étroite (y de 0 à 40)


def test_piece_convertie_largeur_a_l_endroit_du_clic(document: Any) -> None:
    """Dessus d'une pièce en L : cliqué sur le bras étroit (y de 0 à 40), la nouvelle pièce prend
    40 de large et s'y cale ; cliqué sur la partie large, elle prend 100."""
    solid = Part.makeBox(400, 100, 50).cut(Part.makeBox(200, 60, 50, App.Vector(200, 40, 0)))
    source = document.addObject("Part::Feature", "EnL")
    source.Shape = solid
    document.recompute()
    angle = pieces_galbees.shaped(source)
    top = geometry.global_shape(angle).BoundBox
    face = face_at(angle, (0, 0, 1), top.ZMax)
    narrow, _ = create_against(document, angle, face, Vec3(top.XMin + 350, top.YMin + 20, top.ZMax))
    box = geometry.global_shape(narrow).BoundBox
    assert round(box.YMax - box.YMin, 6) == 40
    assert (round(box.YMin - top.YMin, 6), round(box.ZMin - top.ZMax, 6)) == (0, 0)
    wide, _ = create_against(document, angle, face, Vec3(top.XMin + 100, top.YMin + 70, top.ZMax))
    assert round(geometry.global_shape(wide).BoundBox.YMax - top.YMin, 6) == 100


def test_piece_usinee_largeur_mesuree_sur_la_brute(document: Any) -> None:
    """Chant d'un montant mortaisé aux deux bouts : les mortaises coupent la face usinée, mais la
    pièce se cale sur le rectangle de la brute (x de 0 à 600), pas entre les mortaises."""
    frame = cadre.build_frame(document)
    frame.assemble()
    stile = frame.machined("M1")
    chant = face_at(stile, (0, 1, 0), 60)
    part, _start = create_against(document, stile, chant, Vec3(300, 60, 11))
    box = geometry.global_shape(part).BoundBox
    assert round(box.YMin, 6) == 60  # sur le chant
    assert round(box.XMin, 6) == 0  # calée au coin de la brute, pas au bord d'une mortaise


def test_largeur_mesuree_sur_la_face_exterieure_de_la_brute(document: Any) -> None:
    """Feuillure au bord du dessous (y de 290 à 300, 6 mm de profondeur) : cliqué dans la feuillure,
    la largeur est celle de la face extérieure de la brute (300), pas celle de la feuillure (10)."""
    montage = types_assemblages.build(document, types_assemblages.RABBET, App.Placement())
    host = api.machined_part_of(montage.host)
    recessed = face_at(host, (0, 0, -1), -6)
    _part, start = create_against(document, host, recessed, Vec3(300, 295, 6))
    assert round(start.width, 6) == 300
