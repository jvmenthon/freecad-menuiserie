# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profils d'arête sur une pièce dessinée, arêtes natives suivies (ADR 0063, lots P-0 et P-b).

Faits de FreeCAD 1.1 vérifiés ici (spécification § 1) : un lien vers une arête de la pièce suit
cette arête quand l'esquisse du corps change ; une arête coupée en deux est perdue (``?EdgeN``).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import pairwise
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
pytest.importorskip("Sketcher")
api = pytest.importorskip("freecad.menuiserie.api")
edge_profile = pytest.importorskip("freecad.menuiserie.features.edge_profile")
edge_frames = pytest.importorskip("freecad.menuiserie.features.edge_frames")

Point = tuple[float, float]
L_SHAPE: tuple[Point, ...] = ((0, 0), (400, 0), (400, 80), (150, 80), (150, 200), (0, 200))
THICKNESS = 20.0
# Côté gauche (x = 0) remplacé par une encoche : les arêtes de ce côté sont coupées en deux.
NOTCH_LEFT: tuple[Point, ...] = ((0, 200), (0, 120), (30, 120), (30, 60), (0, 60), (0, 0))


def _body(doc: Any, points: Iterable[Point], length: float = THICKNESS) -> tuple[Any, Any]:
    """Corps PartDesign : contour fermé ``points`` dans le plan XY, protrusion de ``length``."""
    points = tuple(points)
    body = doc.addObject("PartDesign::Body", "Corps")
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        sketch.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = length
    doc.recompute()
    return body, sketch


def _edge(shape: Any, a: tuple[float, ...], b: tuple[float, ...]) -> str:
    """Nom de l'arête de ``shape`` dont les bouts sont ``a`` et ``b`` (repère global)."""
    wanted = sorted((App.Vector(*a), App.Vector(*b)), key=tuple)
    for index, edge in enumerate(shape.Edges, start=1):
        ends = sorted((v.Point for v in edge.Vertexes), key=tuple)
        if len(ends) == 2 and all((p - q).Length < 1e-6 for p, q in zip(ends, wanted, strict=True)):
            return f"Edge{index}"
    raise AssertionError(f"arête {a} - {b} absente")


def _shaped(doc: Any, points: Iterable[Point] = L_SHAPE) -> tuple[Any, Any]:
    body, sketch = _body(doc, points)
    shaped = api.make_shaped_part(body)
    doc.recompute()
    return shaped, sketch


def _notch(doc: Any, sketch: Any, index: int, points: tuple[Point, ...]) -> None:
    sketch.delGeometry(index)
    for start, end in pairwise(points):
        sketch.addGeometry(Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0)), False)
    doc.recompute()


def _round_area(radius: float) -> float:
    return (1 - math.pi / 4) * radius**2


FRONT_TOP = ((0, 0, THICKNESS), (400, 0, THICKNESS))  # long bord avant du dessus
INNER_TOP = ((150, 80, THICKNESS), (400, 80, THICKNESS))  # bord intérieur, finit au coin rentrant
LEFT_TOP = ((0, 0, THICKNESS), (0, 200, THICKNESS))  # côté gauche, coupé par l'encoche
INNER_CORNER = ((150, 80, 0), (150, 80, THICKNESS))  # arête verticale rentrante


def test_quart_de_rond_sur_arete_native(document: Any) -> None:
    shaped, _sketch = _shaped(document)
    volume = shaped.Shape.Volume
    name = _edge(shaped.Shape, *FRONT_TOP)
    profile, _messages = api.add_edge_profile(shaped, [name], "Round", 3.0)
    machined = api.machined_part_of(shaped)
    assert profile.EdgeRefs[0] == shaped
    assert list(profile.EdgeRefs[1]) == [name]
    assert list(profile.Edges) == []
    assert machined.Shape.isValid()
    removed = volume - machined.Shape.Volume
    assert removed == pytest.approx(_round_area(3.0) * 400.0, rel=1e-3)


def test_le_profil_suit_son_arete_quand_l_esquisse_change(document: Any) -> None:
    shaped, sketch = _shaped(document)
    name = _edge(shaped.Shape, *FRONT_TOP)
    api.add_edge_profile(shaped, [name], "Chamfer", 2.0)
    _notch(document, sketch, 5, NOTCH_LEFT)
    profile = api.edge_profiles_of(shaped)[0]
    followed = list(profile.EdgeRefs[1])[0]
    assert followed == _edge(shaped.Shape, *FRONT_TOP)
    machined = api.machined_part_of(shaped)
    assert machined.Shape.isValid()
    assert shaped.Shape.Volume - machined.Shape.Volume == pytest.approx(2.0 * 400.0, rel=1e-3)
    assert "Invalid" not in profile.State


def test_arete_perdue_signalee_le_reste_de_la_piece_suit(document: Any, vue_rapport: Any) -> None:
    shaped, sketch = _shaped(document)
    front, left = _edge(shaped.Shape, *FRONT_TOP), _edge(shaped.Shape, *LEFT_TOP)
    api.add_edge_profile(shaped, [front, left], "Chamfer", 2.0)
    _notch(document, sketch, 5, NOTCH_LEFT)
    profile = api.edge_profiles_of(shaped)[0]
    assert edge_profile.lost_edges(profile)
    # signalée sans mettre le profil en erreur, sinon FreeCAD ne recalculerait plus la pièce
    assert "Invalid" not in profile.State
    assert any("perdues" in text for text in vue_rapport.de_niveau("Warning"))
    machined = api.machined_part_of(shaped)
    assert "Invalid" not in machined.State
    assert machined.Shape.isValid()
    # la pièce suit l'encoche, et l'arête encore suivie garde son chanfrein
    removed = shaped.Shape.Volume - machined.Shape.Volume
    assert removed == pytest.approx(2.0 * 400.0, rel=1e-2)


def test_arete_rentrante_refusee_avant_toute_creation(document: Any) -> None:
    shaped, _sketch = _shaped(document)
    count = len(document.Objects)
    with pytest.raises(ValueError, match="rentrante"):
        api.add_edge_profile(shaped, [_edge(shaped.Shape, *INNER_CORNER)], "Round", 2.0)
    assert len(document.Objects) == count


def test_bouts_d_une_arete_qui_finit_au_coin_rentrant(document: Any) -> None:
    shaped, _sketch = _shaped(document)
    shape = edge_profile.native_shape(shaped)
    index = edge_frames.edge_index(_edge(shaped.Shape, *INNER_TOP))
    frame = edge_frames.native_edge(shape, index).frame
    assert frame is not None and frame.convex
    end_x = frame.start.x + frame.direction.x * frame.length
    ends = {round(frame.start.x): frame.extend_start, round(end_x): frame.extend_end}
    assert ends == {150: False, 400: True}  # vers le coin rentrant : pas d'entaille


def test_chanfrein_sur_arete_oblique(document: Any) -> None:
    # Trapèze : le côté droit fait 60° avec le dessous (angle de matière au pied : 60°).
    rise = 100.0 * math.tan(math.radians(60))
    shaped, _sketch = _shaped(document, ((0, 0), (300, 0), (200, rise), (0, rise)))
    name = _edge(shaped.Shape, (300, 0, 0), (200, rise, 0))
    volume = shaped.Shape.Volume
    api.add_edge_profile(shaped, [name], "Chamfer", 3.0, 3.0)
    machined = api.machined_part_of(shaped)
    assert machined.Shape.isValid()
    angle = math.radians(90)  # entre le dessous (Z-) et le côté oblique, toujours d'équerre
    length = math.hypot(100.0, rise)
    expected = 0.5 * 9.0 * math.sin(angle) * length
    assert volume - machined.Shape.Volume == pytest.approx(expected, rel=1e-2)
    # Arête verticale au pied du côté oblique : 60° entre le dessous du trapèze et ce côté.
    foot = _edge(shaped.Shape, (300, 0, 0), (300, 0, THICKNESS))
    with pytest.raises(ValueError, match="angle droit"):
        api.add_edge_profile(shaped, [foot], "Ogee", 4.0, 3.0)
    api.add_edge_profile(shaped, [foot], "Round", 2.0)
    assert api.machined_part_of(shaped).Shape.isValid()


def test_pieces_en_boite_gardent_leurs_codes(document: Any) -> None:
    part = api.make_wood_part(600.0, 300.0, 20.0, doc=document)
    document.recompute()
    with pytest.raises(ValueError, match="dessus-avant"):
        api.add_edge_profile(part, ["Edge1"], "Round", 2.0)
    profile, _messages = api.add_edge_profile(part, ["Z+Y-"], "Round", 2.0)
    assert list(profile.Edges) == ["Z+Y-"]
    assert not profile.EdgeRefs


def test_noms_melanges_ou_inconnus_refuses(document: Any) -> None:
    shaped, _sketch = _shaped(document)
    with pytest.raises(ValueError, match="pas les deux"):
        api.add_edge_profile(shaped, ["Edge1", "Z+Y-"], "Round", 2.0)
    with pytest.raises(ValueError):
        api.add_edge_profile(shaped, ["Edge999"], "Round", 2.0)


def test_contour_d_une_face_et_chaine_tangente(document: Any) -> None:
    shaped, _sketch = _shaped(document)
    shape = shaped.Shape
    top = next(
        f"Face{i}"
        for i, face in enumerate(shape.Faces, start=1)
        if abs(face.CenterOfMass.z - THICKNESS) < 1e-6
    )
    names = edge_frames.face_edge_names(shape, top)
    assert len(names) == 6
    index = edge_frames.edge_index(_edge(shape, *FRONT_TOP))
    assert edge_frames.tangent_chain(shape, index) == [index]  # coins vifs : l'arête seule


def test_le_profil_se_relit_apres_enregistrement(document: Any, tmp_path: Any) -> None:
    shaped, _sketch = _shaped(document)
    name = _edge(shaped.Shape, *FRONT_TOP)
    api.add_edge_profile(shaped, [name], "Round", 2.0)
    path = str(tmp_path / "profil.FCStd")
    document.saveAs(path)
    reopened = App.openDocument(path)
    try:
        reopened.recompute()
        profile = next(o for o in reopened.Objects if edge_profile.is_edge_profile(o))
        assert profile.Version == edge_profile.MODEL_VERSION
        assert list(profile.EdgeRefs[1]) == [name]
        machined = next(o for o in reopened.Objects if o.Name.startswith("MachinedPart"))
        assert machined.Shape.isValid()
    finally:
        App.closeDocument(reopened.Name)


def test_forme_sans_noms_stables_refusee(document: Any) -> None:
    """Une primitive ``Part`` n'a pas de carte d'éléments : ses arêtes ne seraient pas suivies."""
    wedge = document.addObject("Part::Wedge", "Coin")
    document.recompute()
    shaped = api.make_shaped_part(wedge)
    document.recompute()
    with pytest.raises(ValueError, match="noms d'éléments stables"):
        api.add_edge_profile(shaped, ["Edge1"], "Chamfer", 1.0)
