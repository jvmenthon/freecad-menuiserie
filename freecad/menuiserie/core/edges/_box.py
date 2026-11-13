# SPDX-License-Identifier: LGPL-2.1-or-later
"""Géométrie de la boîte d'une pièce dans son repère local (issue #5) : bouts des arêtes, coins
des faces.

Module privé, partagé par la désignation (:mod:`._pick`), les dessins (:mod:`._diagram`) et la
mise en valeur dans la vue 3D. Repère local : origine au coin minimal, ``X`` = longueur, ``Y`` =
largeur, ``Z`` = épaisseur (mm).
"""

from __future__ import annotations

from freecad.menuiserie.core.edges._ids import EdgeId, parse_face
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.part_model import Dimensions

__all__ = ["box_sizes", "edge_ends", "face_corners"]


def box_sizes(dimensions: Dimensions) -> tuple[float, float, float]:
    """Cotes de la boîte le long de ``X``, ``Y`` et ``Z``."""
    return (dimensions.length, dimensions.width, dimensions.thickness)


def edge_ends(dimensions: Dimensions, edge: EdgeId) -> tuple[Vec3, Vec3]:
    """Bouts de l'arête ``edge`` de la boîte ``dimensions``, dans le repère local (mm)."""
    sizes = box_sizes(dimensions)
    values = [0.0, 0.0, 0.0]
    for face in (edge.first, edge.second):
        values[face.index] = sizes[face.index] if face.sign > 0 else 0.0
    low, high = list(values), list(values)
    high[edge.along] = sizes[edge.along]
    return Vec3.of(low), Vec3.of(high)


def face_corners(dimensions: Dimensions, face: str) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Les quatre coins de la face ``face`` (``"Z+"``) de la boîte, dans l'ordre du contour
    (repère local, mm)."""
    axis = parse_face(face)
    sizes = box_sizes(dimensions)
    fixed = sizes[axis.index] if axis.sign > 0 else 0.0
    one, two = (index for index in range(3) if index != axis.index)
    corners = []
    for a, b in ((0.0, 0.0), (sizes[one], 0.0), (sizes[one], sizes[two]), (0.0, sizes[two])):
        values = [0.0, 0.0, 0.0]
        values[axis.index], values[one], values[two] = fixed, a, b
        corners.append(Vec3.of(values))
    return corners[0], corners[1], corners[2], corners[3]
