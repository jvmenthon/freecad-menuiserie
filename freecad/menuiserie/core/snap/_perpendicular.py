# SPDX-License-Identifier: LGPL-2.1-or-later
"""Orientation d'une pièce posée perpendiculairement à la face d'une autre pièce (issue #136).

La longueur de la nouvelle pièce part de la face (le long de sa normale sortante) ; ses deux
autres axes suivent ceux de la pièce qui porte la face, pour que les largeurs et épaisseurs
restent parallèles : contre une extrémité, la pièce prolonge l'autre ; contre une grande face
(épaisseur), sa largeur reste parallèle à celle de l'autre ; contre un chant (largeur), son
épaisseur reste parallèle à celle de l'autre.
"""

from __future__ import annotations

from freecad.menuiserie.core.geometry import Matrix3, Vec3, squared_rotation
from freecad.menuiserie.core.snap._model import Orientation, product
from freecad.menuiserie.core.vectors import cross

__all__ = ["perpendicular_orientation"]

_WIDTH, _THICKNESS = 1, 2
_NORMAL_ROW = 2  # ligne « normale sortante » du repère d'appui


def _transposed(matrix: Matrix3) -> Matrix3:
    columns = tuple(zip(*matrix, strict=True))
    return (columns[0], columns[1], columns[2])


def _column(matrix: Matrix3, index: int) -> Vec3:
    return Vec3(matrix[0][index], matrix[1][index], matrix[2][index])


def perpendicular_orientation(support: Matrix3, owner: Matrix3) -> Orientation | None:
    """Orientation (repère local de la nouvelle pièce → repère d'appui) d'une pièce perpendiculaire
    à la face de repère d'appui ``support`` (rotation repère d'appui → document), portée par une
    pièce de rotation ``owner`` (repère local → document).

    ``None`` si la pièce qui porte la face n'est pas d'équerre avec la face (rotation oblique) :
    l'appelant garde alors l'orientation habituelle."""
    seen = squared_rotation(product(_transposed(support), owner))
    if any(value not in (-1.0, 0.0, 1.0) for row in seen for value in row):
        return None
    normal_axis = next(i for i in range(3) if seen[_NORMAL_ROW][i] != 0.0)
    length = Vec3(0.0, 0.0, 1.0)
    if normal_axis == _THICKNESS:  # grande face : la largeur reste parallèle à l'autre
        width = _column(seen, _WIDTH)
        thickness = cross(length, width)
    else:  # extrémité ou chant : l'épaisseur reste parallèle à l'autre
        thickness = _column(seen, _THICKNESS)
        width = cross(thickness, length)
    axes = (length, width, thickness)
    rows = [[axis.component(row) for axis in axes] for row in range(3)]
    x, y, z = (Vec3.of(row) for row in rows)
    return Orientation(((x.x, x.y, x.z), (y.x, y.y, y.z), (z.x, z.y, z.z)))
