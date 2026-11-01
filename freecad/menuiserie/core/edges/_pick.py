# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arête de la boîte d'une pièce la plus proche d'un point cliqué (ADR 0029, § 4.5).

Module privé. Le clic en 3D donne un point (milieu du morceau d'arête cliqué), pas un code :
on le rapproche des 12 segments d'arête de la boîte brute, dans le repère local. Une arête qui
n'est plus sur la boîte (déjà profilée, coupée par un assemblage) se rapproche de la plus
proche. Seul le code est conservé.
"""

from __future__ import annotations

from freecad.menuiserie.core.edges._ids import EdgeId, all_edges
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.vectors import dot, norm

__all__ = ["nearest_edge"]


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
