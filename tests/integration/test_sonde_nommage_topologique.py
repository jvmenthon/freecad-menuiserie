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


def _edge_keys(shape: Any) -> dict[tuple[tuple[float, ...], ...], str]:
    """Arêtes de ``shape`` repérées par leurs bouts arrondis : clé → nom ``EdgeN``."""
    keys: dict[tuple[tuple[float, ...], ...], str] = {}
    for index, edge in enumerate(shape.Edges, start=1):
        ends = sorted(
            tuple(round(c, 3) for c in (v.Point.x, v.Point.y, v.Point.z)) for v in edge.Vertexes
        )
        keys[tuple(ends)] = f"Edge{index}"
    return keys


# Côté remplacé par une encoche : indice du segment dans L_SHAPE, nouveaux segments.
NOTCHES = {
    "gauche": (5, ((0, 200), (0, 120), (30, 120), (30, 60), (0, 60), (0, 0))),
    "droite": (1, ((400, 0), (400, 20), (370, 20), (370, 60), (400, 60), (400, 80))),
}


@pytest.mark.parametrize("side", sorted(NOTCHES))
def test_sonde_aretes_suivies_apres_changement_de_topologie(document: Any, side: str) -> None:
    """Un lien vers chaque arête de la pièce, puis une encoche ajoutée à l'esquisse (nouvelles
    faces) : chaque arête restée en place est-elle encore désignée, même renumérotée ?"""
    body, sketch = _body(document, L_SHAPE)
    shaped = api.make_shaped_part(body)
    document.recompute()
    before = _edge_keys(shaped.Shape)
    keys = list(before)
    holder = document.addObject("App::FeaturePython", "Sonde")
    holder.addProperty("App::PropertyLinkSub", "Aretes")
    holder.Aretes = (shaped, [before[key] for key in keys])
    document.recompute()
    _report(
        f"[{side}] cartes d'éléments : corps={_map_size(body.Shape)} "
        f"pièce={_map_size(shaped.Shape)} ; Edge4 pièce = {_mapped(shaped.Shape, 'Edge4')!r}"
    )
    index, notch = NOTCHES[side]
    sketch.delGeometry(index)
    for start, end in pairwise(notch):
        sketch.addGeometry(_segment(start, end), False)
    document.recompute()
    after = _edge_keys(shaped.Shape)
    linked = list(holder.Aretes[1]) if holder.Aretes else []
    kept = [k for k in keys if k in after]
    moved = [k for k in kept if after[k] != before[k]]
    followed = [
        k for k in kept if keys.index(k) < len(linked) and linked[keys.index(k)] == after[k]
    ]
    wrong = [
        f"{before[k]}→{after[k]} lien {linked[keys.index(k)]}"
        for k in moved
        if keys.index(k) < len(linked) and linked[keys.index(k)] != after[k]
    ]
    _report(
        f"[{side}] pièce valide {shaped.isValid()}, faces {len(shaped.Shape.Faces)} ; arêtes "
        f"restées en place {len(kept)}/{len(keys)}, renumérotées {len(moved)}, liens justes "
        f"{len(followed)}/{len(kept)}, liens {len(linked)} ; erreurs : {wrong[:6]}"
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
