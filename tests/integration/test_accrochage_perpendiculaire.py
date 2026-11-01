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
api = pytest.importorskip("freecad.menuiserie.api")
picked = pytest.importorskip("freecad.menuiserie.features.picked")
perpendicular = pytest.importorskip("freecad.menuiserie.features.perpendicular")
placement_module = pytest.importorskip("freecad.menuiserie.features.placement")
geometry = pytest.importorskip("freecad.menuiserie.features.snap_geometry")
targets = pytest.importorskip("freecad.menuiserie.features.snap_targets")
wood_part = pytest.importorskip("freecad.menuiserie.features.wood_part")

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


def create_against(document: Any, root: Any, subname: str) -> tuple[Any, Any]:
    """(pièce créée, départ perpendiculaire) comme le fait la commande."""
    reading = targets.read_targets([picked.PickedElement(root, subname, None)], ABOVE)
    start = perpendicular.perpendicular_start(reading)
    assert start is not None
    part = api.make_wood_part(width=start.width, thickness=start.thickness, doc=document)
    session = targets.new_session(reading, wood_part.dimensions_of(part), start.orientation)
    placement_module.snap_part(part, session)
    document.recompute()
    return part, start


def test_extremite_angle_droit_avec_la_piece(document: Any, board: Any) -> None:
    part, start = create_against(document, board, face_at(board, (1, 0, 0), 800))
    assert (start.width, start.thickness) == (100, 30)
    box = geometry.global_shape(part).BoundBox
    assert round(box.XMin, 6) == 800  # appuyée sur l'extrémité
    assert round(box.XMax - box.XMin, 6) == 100  # sa largeur part de la face
    assert round(box.YMax - box.YMin, 6) == 800  # longueur selon la largeur de l'autre pièce
    assert (round(box.ZMin, 6), round(box.ZMax, 6)) == (0, 30)  # épaisseur parallèle


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
