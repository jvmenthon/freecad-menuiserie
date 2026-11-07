# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arêtes de la boîte d'une pièce désignées par un élément cliqué (ADR 0029, § 4.5).

Module privé. Le clic en 3D donne un point (centre de la face, milieu du morceau d'arête ou
sommet cliqué), pas un code : on le rapproche des faces, des 12 segments d'arête ou des 8 coins
de la boîte brute, dans le repère local. Un élément qui n'est plus sur la boîte (déjà profilé,
coupé par un assemblage) se rapproche du plus proche. Seuls les codes sont conservés.
"""

from __future__ import annotations

from freecad.menuiserie.core.edges._ids import EdgeId, all_edges, loop_edges
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.vectors import dot, norm

__all__ = ["edges_at", "nearest_edge"]


def _ends(dimensions: Dimensions, edge: EdgeId) -> tuple[Vec3, Vec3]:
    """Bouts de l'arête de la boîte, dans le repère local."""
    sizes = (dimensions.length, dimensions.width, dimensions.thickness)
    values = [0.0, 0.0, 0.0]
    for face in (edge.first, edge.second):
        values[face.index] = sizes[face.index] if face.sign > 0 else 0.0
    low, high = list(values), list(values)
    high[edge.along] = sizes[edge.along]
    return Vec3.of(low), Vec3.of(high)


def _distance(dimensions: Dimensions, edge: EdgeId, point: Vec3) -> float:
    """Distance de ``point`` au segment de l'arête (pas à son milieu : un morceau d'arête coupé
    par un assemblage reste proche de son arête)."""
    start, end = _ends(dimensions, edge)
    along = end - start
    t = max(0.0, min(1.0, dot(point - start, along) / dot(along, along)))
    return norm(point - (start + along.scaled(t)))


def nearest_edge(dimensions: Dimensions, point: Vec3) -> EdgeId:
    """Arête de la boîte ``dimensions`` la plus proche de ``point`` (repère local, mm), mesurée
    jusqu'au segment de l'arête. À égalité, la première des douze (ordre de :func:`all_edges`)."""
    return min(all_edges(), key=lambda edge: _distance(dimensions, edge, point))


def _sizes(dimensions: Dimensions) -> tuple[float, float, float]:
    return (dimensions.length, dimensions.width, dimensions.thickness)


def _nearest_face(dimensions: Dimensions, point: Vec3) -> str:
    """Code de la face de la boîte la plus proche de ``point`` (``"Z+"``…)."""
    sizes = _sizes(dimensions)
    candidates = [
        (abs(point.component(index) - (sizes[index] if sign == "+" else 0.0)), f"{letter}{sign}")
        for index, letter in enumerate("XYZ")
        for sign in "+-"
    ]
    return min(candidates)[1]


def _corner_edges(dimensions: Dimensions, point: Vec3) -> tuple[EdgeId, ...]:
    """Les trois arêtes qui se rejoignent au coin de la boîte le plus proche de ``point``."""
    ends = [(edge, end) for edge in all_edges() for end in _ends(dimensions, edge)]
    corner = min((end for _, end in ends), key=lambda end: norm(point - end))
    return tuple(edge for edge, end in ends if norm(end - corner) < 1e-6)


def edges_at(dimensions: Dimensions, kind: str, point: Vec3) -> tuple[EdgeId, ...]:
    """Arêtes désignées par un élément cliqué : ``kind`` est ``"Face"`` (ses 4 arêtes),
    ``"Edge"`` (cette arête) ou ``"Vertex"`` (les 3 arêtes du coin) ; ``point`` est son centre
    dans le repère local (mm). Autre ``kind`` : ``ValueError``."""
    if kind == "Face":
        return loop_edges(_nearest_face(dimensions, point))
    if kind == "Edge":
        return (nearest_edge(dimensions, point),)
    if kind == "Vertex":
        return _corner_edges(dimensions, point)
    raise ValueError(f"élément inconnu : {kind}")
