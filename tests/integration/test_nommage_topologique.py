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

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron
from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from tests.integration.cadre import build_frame

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")
cache = pytest.importorskip("freecad.menuiserie.features.machined_cache")
shaped_part = pytest.importorskip("freecad.menuiserie.features.shaped_part")
solids = pytest.importorskip("freecad.menuiserie.features.solids")

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
    """Fige un comportement de FreeCAD 1.1 (motif de l'ADR 0056) : à revoir s'il change."""
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
    """Nom (``FaceN``) de la face plane de dessous (normale -Z, z minimal) de ``shape``."""
    low = shape.BoundBox.ZMin
    for index, face in enumerate(shape.Faces, start=1):
        normal = face.normalAt(*face.Surface.parameter(face.CenterOfMass))
        if normal.z < -0.999 and abs(face.CenterOfMass.z - low) < 1e-6:
            return f"Face{index}"
    raise AssertionError("face de dessous introuvable")


def _linked_frame(document: Any) -> tuple[Any, Any, str]:
    """Cadre où M1 a un tenon-mortaise (T1) et un lien vers la face de dessous de sa pièce
    usinée : (pièce usinée, porteur du lien, nom cartographié de la face)."""
    cadre = build_frame(document)
    cadre.assemble((("M1", "T1"),))
    document.recompute()
    machined = cadre.machined("M1")
    face = _bottom_face(machined.Shape)
    return machined, _holder(document, machined, face), machined.Shape.getElementMappedName(face)


def _assert_follows(machined: Any, holder: Any, mapped: str) -> None:
    """Le lien vise toujours la face de dessous, sous le même nom cartographié."""
    linked = holder.Lien[1][0]
    assert linked == _bottom_face(machined.Shape)
    assert machined.Shape.getElementMappedName(linked) == mapped


def test_piece_usinee_a_une_carte_et_le_lien_suit(document: Any) -> None:
    """ADR 0056 : la pièce usinée a une carte des éléments ; un lien vers sa face de dessous la
    suit, sous le même nom cartographié, quand un second assemblage ajoute des faces."""
    machined, holder, mapped = _linked_frame(document)
    assert machined.Shape.ElementMapSize > 0 and mapped
    faces_before = len(machined.Shape.Faces)
    api.make_mortise_tenon(machined.Base, document.getObjectsByLabel("T2")[0])
    document.recompute()
    assert len(machined.Shape.Faces) > faces_before
    _assert_follows(machined, holder, mapped)


def test_carte_et_lien_apres_reouverture(document: Any, rouvrir: Any) -> None:
    """La carte est enregistrée avec la forme : après réouverture et recalcul, le lien suit
    encore un nouvel assemblage."""
    machined, holder, mapped = _linked_frame(document)
    reopened = rouvrir(document)
    machined, holder = (reopened.getObject(o.Name) for o in (machined, holder))
    assert machined.Shape.ElementMapSize > 0
    reopened.recompute()
    _assert_follows(machined, holder, mapped)
    api.make_mortise_tenon(machined.Base, reopened.getObjectsByLabel("T2")[0])
    reopened.recompute()
    _assert_follows(machined, holder, mapped)


def test_annuler_un_assemblage_garde_le_lien(document: Any) -> None:
    document.UndoMode = 1
    machined, holder, mapped = _linked_frame(document)
    document.openTransaction("Assemblage")
    api.make_mortise_tenon(machined.Base, document.getObjectsByLabel("T2")[0])
    document.commitTransaction()
    document.recompute()
    document.undo()
    document.recompute()
    assert machined.Shape.ElementMapSize > 0
    _assert_follows(machined, holder, mapped)


def test_usinages_egaux_memes_noms(document: Any) -> None:
    """Deux traverses usinées de la même façon (même cote, mêmes enlèvements dans leur repère :
    même clé de cache) ont les mêmes noms d'éléments."""
    cadre = build_frame(document)
    cadre.assemble()
    document.recompute()
    first, second = (cadre.machined(mark).Shape for mark in ("T1", "T2"))
    assert first.Volume == pytest.approx(second.Volume)
    assert first.ElementMapSize == second.ElementMapSize > 0
    name = _bottom_face(first)
    assert first.getElementMappedName(name) == second.getElementMappedName(name)


CORNER = Box(Vec3(0.0, 0.0, 0.0), Vec3(10.0, 10.0, THICKNESS))


def test_cache_rend_une_copie_avec_la_meme_carte() -> None:
    cache.reset_machined_cache()
    key = ("carte", CORNER)
    first = cache.cached_machined_shape(Part.makeBox(LENGTH, WIDTH, THICKNESS), key, [], [CORNER])
    second = cache.cached_machined_shape(Part.makeBox(LENGTH, WIDTH, THICKNESS), key, [], [CORNER])
    cache.reset_machined_cache()
    assert second is not first
    assert second.ElementMapSize == first.ElementMapSize > 0
    face = _plus_x_face(first)
    assert first.getElementMappedName(face) == second.getElementMappedName(face)


def test_la_forme_recue_n_est_pas_modifiee() -> None:
    base = Part.makeBox(LENGTH, WIDTH, THICKNESS)
    solids.machined_shape(base, [], [CORNER])
    assert base.Tag == 0 and base.ElementMapSize == 0


def test_sans_usinage_la_boite_garde_six_faces_et_une_carte() -> None:
    shape = solids.machined_shape(Part.makeBox(LENGTH, WIDTH, THICKNESS), [], [])
    assert shape.isValid() and len(shape.Faces) == 6
    assert shape.ElementMapSize > 0


def test_enlevement_en_biais_a_une_carte() -> None:
    """Coin abattu par un polyèdre (plan à 45°) : un seul solide valide, avec carte."""
    corner = Polyhedron(
        Box(Vec3(0.0, 0.0, 0.0), Vec3(30.0, 30.0, THICKNESS)),
        RigidTransform.identity(),
        (Plane(Vec3(30.0, 0.0, 0.0), Vec3(1.0, 1.0, 0.0)),),
    )
    shape = solids.machined_shape(Part.makeBox(LENGTH, WIDTH, THICKNESS), [], [corner])
    assert shape.isValid() and len(shape.Solids) == 1
    assert shape.Volume == pytest.approx(LENGTH * WIDTH * THICKNESS - 450.0 * THICKNESS)
    assert shape.ElementMapSize > 0


def test_echec_occ_d_un_outil_devient_une_erreur_traduite(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(_solid: object) -> Any:
        raise Part.OCCError("échec simulé")

    monkeypatch.setattr(solids, "solid_shape", failing)
    with pytest.raises(ValueError, match="Usinage impossible"):
        solids.machined_shape(Part.makeBox(LENGTH, WIDTH, THICKNESS), [], [CORNER])


def test_piece_en_bois_et_sa_piece_usinee_ont_une_carte(document: Any) -> None:
    """Un corps PartDesign a une carte ; la pièce en bois qui le recopie la garde, et sa pièce
    usinée (base déjà étiquetée) en a une aussi."""
    galbees = pytest.importorskip("tests.integration.pieces_galbees")
    body = galbees.curved_rail(document)
    assert body.Shape.ElementMapSize > 0
    piece = galbees.shaped(body)
    assert piece.Shape.ElementMapSize > 0
    base = shaped_part.base_shape_of(piece)
    tag = base.Tag
    shape = solids.machined_shape(base, [], [CORNER])
    assert base.Tag == tag != 0
    assert shape.isValid() and shape.ElementMapSize > 0


def test_trop_d_outils_dans_un_groupe_est_refuse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deux outils n'ont jamais la même étiquette : un groupe qui dépasse sa plage est refusé."""
    monkeypatch.setattr(solids, "_GROUP_TAGS", 2)
    with pytest.raises(ValueError, match="trop d'usinages"):
        solids.machined_shape(Part.makeBox(LENGTH, WIDTH, THICKNESS), [], [CORNER, CORNER])
