# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sonde (provisoire) : le nommage topologique de FreeCAD ≥ 1.0 suit-il une arête désignée
d'une pièce en bois à forme dessinée quand l'esquisse de son corps change ?

Ne vérifie rien : chaque test rapporte ses constats par un avertissement « SONDE » (résumé des
avertissements de pytest), pour décider comment étendre les profils d'arête aux formes
quelconques (issue #5). À retirer une fois la décision prise.
"""

from __future__ import annotations

import warnings
from itertools import pairwise
from typing import Any

import pytest

pytestmark = pytest.mark.integration

App = pytest.importorskip("FreeCAD")
Part = pytest.importorskip("Part")
api = pytest.importorskip("freecad.menuiserie.api")

L_SHAPE = ((0, 0), (400, 0), (400, 80), (150, 80), (150, 200), (0, 200))
NOTCHED_LEFT = ((0, 200), (0, 120), (30, 120), (30, 60), (0, 60), (0, 0))


def _report(text: str) -> None:
    warnings.warn(f"SONDE {text}", UserWarning, stacklevel=2)


def _segment(start: tuple[int, int], end: tuple[int, int]) -> Any:
    return Part.LineSegment(App.Vector(*start, 0), App.Vector(*end, 0))


def _body(doc: Any, points: tuple[tuple[int, int], ...]) -> tuple[Any, Any]:
    """Corps PartDesign : esquisse fermée ``points`` (sans contrainte), protrusion de 20 mm."""
    body = doc.addObject("PartDesign::Body", "Corps")
    sketch = body.newObject("Sketcher::SketchObject", "Esquisse")
    for index, start in enumerate(points):
        sketch.addGeometry(_segment(start, points[(index + 1) % len(points)]), False)
    pad = body.newObject("PartDesign::Pad", "Protrusion")
    pad.Profile = sketch
    pad.Length = 20.0
    doc.recompute()
    return body, sketch


def _map_size(shape: Any) -> object:
    return getattr(shape, "ElementMapSize", "absent")


def _mapped(shape: Any, name: str) -> object:
    getter = getattr(shape, "getElementMappedName", None)
    if getter is None:
        return "absent"
    try:
        return getter(name)
    except (RuntimeError, ValueError, TypeError) as error:
        return f"erreur {error}"


def _target(shape: Any) -> int:
    """Indice (1..n) de la plus longue arête droite du dessus de ``shape``."""
    top = shape.BoundBox.ZMax
    candidates = [
        (edge.Length, index)
        for index, edge in enumerate(shape.Edges, start=1)
        if all(abs(v.Point.z - top) < 1e-6 for v in edge.Vertexes)
    ]
    return max(candidates)[1]


def test_sonde_arete_suivie_apres_changement_de_topologie(document: Any) -> None:
    """Un lien vers l'arête la plus longue du dessus, puis une encoche ajoutée à l'esquisse
    (nouvelles faces, arêtes renumérotées) : le lien désigne-t-il encore la même arête ?"""
    body, sketch = _body(document, L_SHAPE)
    shaped = api.make_shaped_part(body)
    document.recompute()
    before = _target(shaped.Shape)
    name = f"Edge{before}"
    holder = document.addObject("App::FeaturePython", "Sonde")
    holder.addProperty("App::PropertyLinkSub", "Arete")
    holder.Arete = (shaped, [name])
    document.recompute()
    _report(
        f"cartes d'éléments : corps={_map_size(body.Shape)} "
        f"pièce={_map_size(shaped.Shape)} ; nom mappé de {name} sur la pièce = "
        f"{_mapped(shaped.Shape, name)!r} ; sur le corps = {_mapped(body.Shape, name)!r}"
    )
    sketch.delGeometry(len(L_SHAPE) - 1)  # côté gauche x = 0, remplacé par une encoche
    for start, end in pairwise(NOTCHED_LEFT):
        sketch.addGeometry(_segment(start, end), False)
    document.recompute()
    after = _target(shaped.Shape)
    linked = holder.Arete[1][0] if holder.Arete else None
    _report(
        f"après encoche : faces {len(shaped.Shape.Faces)}, arête visée Edge{before} → "
        f"Edge{after} (renumérotée : {before != after}) ; le lien désigne {linked} "
        f"(suivi correct : {linked == f'Edge{after}'}) ; pièce valide : {shaped.isValid()}"
    )


def test_sonde_carte_d_elements_de_la_piece_usinee(document: Any) -> None:
    """Pièce en bois en boîte tirée d'un corps, chanfreinée : la pièce usinée garde-t-elle une
    carte d'éléments (sans elle, aucun nommage topologique en aval) ?"""
    body, _sketch = _body(document, ((0, 0), (300, 0), (300, 100), (0, 100)))
    shaped = api.make_shaped_part(body)
    document.recompute()
    api.add_edge_profile(shaped, ["Z+Y-"], "Chamfer", 2.0)
    document.recompute()
    machined = api.machined_part_of(shaped)
    _report(
        f"carte d'éléments : corps={_map_size(body.Shape)} pièce={_map_size(shaped.Shape)} "
        f"pièce usinée={_map_size(machined.Shape)} ; Edge1 usinée = "
        f"{_mapped(machined.Shape, 'Edge1')!r}"
    )
