# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arête de la boîte d'une pièce la plus proche d'un point cliqué (ADR 0029, § 4.5).

Module privé. Le clic en 3D donne un point, pas un code : on le rapproche des 12 arêtes de la boîte
brute, dans le repère local. Une arête qui n'est plus sur la boîte (déjà profilée, coupée par un
assemblage) se rapproche de la plus proche. Seul le code est conservé.
"""

from __future__ import annotations

from freecad.menuiserie.core.edges._ids import EdgeId, all_edges
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.vectors import norm

__all__ = ["nearest_edge"]


def _midpoint(dimensions: Dimensions, edge: EdgeId) -> Vec3:
    sizes = (dimensions.length, dimensions.width, dimensions.thickness)
    values = [0.0, 0.0, 0.0]
    for face in (edge.first, edge.second):
        values[face.index] = sizes[face.index] if face.sign > 0 else 0.0
    values[edge.along] = sizes[edge.along] / 2
    return Vec3.of(values)


def nearest_edge(dimensions: Dimensions, point: Vec3) -> EdgeId:
    """Arête de la boîte ``dimensions`` dont le milieu est le plus proche de ``point`` (repère
    local, mm). À égalité, la première des douze (ordre de :func:`all_edges`)."""
    return min(all_edges(), key=lambda edge: norm(point - _midpoint(dimensions, edge)))
