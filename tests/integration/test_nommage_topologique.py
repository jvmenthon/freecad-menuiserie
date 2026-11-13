# SPDX-License-Identifier: LGPL-2.1-or-later
"""Nommage topologique de FreeCAD 1.1 : ce qui s'applique aux formes de l'atelier (ADR 0056).

Ces tests fixent le comportement de FreeCAD sur lequel s'appuient les décisions de l'atelier :
une forme construite en Python sans étiquette (``Tag``) n'a pas de carte des éléments, et un lien
vers un de ses éléments (``Face3``) garde son numéro ; une forme qui a une carte voit ses liens
suivre l'élément quand sa numérotation change. La pièce usinée étiquette ses entrées pour avoir
une carte (ADR 0056).
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.cadre import build_frame

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")

LENGTH, WIDTH, THICKNESS = 100.0, 50.0, 20.0


def _plus_x_face(shape: Any) -> str:
    """Nom (``FaceN``) de la face plane de normale +X en x = LENGTH."""
    for index, face in enumerate(shape.Faces, start=1):
        normal = face.normalAt(*face.Surface.parameter(face.CenterOfMass))
        if normal.x > 0.999 and abs(face.CenterOfMass.x - LENGTH) < 1e-6:
            return f"Face{index}"
    raise AssertionError("face +X introuvable")


def _cut(tag: int, tools_tag: int, notches: int) -> Any:
    """Bloc entaillé de ``notches`` encoches (1 ou 2) côté x = 0 ; ``tag`` 0 : sans étiquette."""
    base = Part.makeBox(LENGTH, WIDTH, THICKNESS)
    tools = [Part.makeBox(10, 10, THICKNESS), Part.makeBox(10, 10, THICKNESS, App.Vector(0, 40, 0))]
    base.Tag = tag
    for tool in tools:
        tool.Tag = tools_tag
    return base.cut(tools[:notches])


def test_booleen_python_sans_etiquette_n_a_pas_de_carte() -> None:
    assert _cut(0, 0, 2).ElementMapSize == 0


def test_booleen_python_etiquete_a_une_carte() -> None:
    shape = _cut(1, 2, 2)
    assert shape.ElementMapSize > 0
    one, two = _cut(1, 2, 1), shape
    assert one.getElementMappedName(_plus_x_face(one)) == two.getElementMappedName(
        _plus_x_face(two)
    )


def _holder(doc: Any, target: Any, sub: str) -> Any:
    holder = doc.addObject("App::FeaturePython", "Porteur")
    holder.addProperty("App::PropertyLinkSubGlobal", "Lien")
    holder.Lien = (target, [sub])
    doc.recompute()
    return holder


@pytest.mark.parametrize("tagged", [False, True])
def test_lien_vers_une_face_selon_la_carte(document: Any, tagged: bool) -> None:
    """Sans carte, le lien garde son numéro ; avec carte, il suit la face +X."""
    source = document.addObject("Part::Feature", "Source")
    other = document.addObject("Part::Feature", "Outil")
    tag, tools_tag = (source.ID, other.ID) if tagged else (0, 0)
    first = _cut(tag, tools_tag, 1)
    source.Shape = first
    document.recompute()
    before = _plus_x_face(source.Shape)
    holder = _holder(document, source, before)
    second = _cut(tag, tools_tag, 2)
    source.Shape = second
    document.recompute()
    after = _plus_x_face(source.Shape)
    kept = holder.Lien[1][0]
    report = f"avant {before}, après {after}, lien {kept}, carte {source.Shape.ElementMapSize}"
    assert kept == (after if tagged else before), report


def _bottom_face(shape: Any) -> str:
    """Nom (``FaceN``) de la face de dessous (normale -Z, z minimal) de ``shape``."""
    low = shape.BoundBox.ZMin
    for index, face in enumerate(shape.Faces, start=1):
        normal = face.normalAt(*face.Surface.parameter(face.CenterOfMass))
        if normal.z < -0.999 and abs(face.CenterOfMass.z - low) < 1e-6:
            return f"Face{index}"
    raise AssertionError("face de dessous introuvable")


def test_piece_usinee_a_une_carte_et_le_lien_suit(document: Any) -> None:
    """ADR 0056 : la pièce usinée a une carte des éléments ; un lien vers sa face de dessous la
    suit quand un second assemblage renumérote ses faces."""
    cadre = build_frame(document)
    cadre.assemble((("M1", "T1"),))
    document.recompute()
    machined = cadre.machined("M1")
    assert machined.Shape.ElementMapSize > 0
    holder = _holder(document, machined, _bottom_face(machined.Shape))
    faces_before = len(machined.Shape.Faces)
    cadre.assemble((("M1", "T2"),))
    document.recompute()
    assert len(machined.Shape.Faces) > faces_before
    assert holder.Lien[1][0] == _bottom_face(machined.Shape)


def test_usinages_egaux_memes_noms(document: Any) -> None:
    """Le cache rend une forme dont les noms ne dépendent que de l'usinage : deux traverses
    usinées de la même façon ont les mêmes noms d'éléments."""
    cadre = build_frame(document)
    cadre.assemble()
    document.recompute()
    first, second = (cadre.machined(mark).Shape for mark in ("T1", "T2"))
    assert first.ElementMapSize == second.ElementMapSize > 0
    name = _bottom_face(first)
    assert first.getElementMappedName(name) == second.getElementMappedName(name)


def test_corps_partdesign_et_piece_en_bois(document: Any) -> None:
    """Un corps PartDesign a une carte ; la pièce en bois qui le recopie la garde-t-elle ?"""
    galbees = pytest.importorskip("tests.integration.pieces_galbees")
    body = galbees.curved_rail(document)
    assert body.Shape.ElementMapSize > 0
    piece = galbees.shaped(body)
    assert piece.Shape.ElementMapSize > 0, piece.Shape.ElementMapSize
