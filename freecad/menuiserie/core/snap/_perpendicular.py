# SPDX-License-Identifier: LGPL-2.1-or-later
"""Orientation d'une pièce posée perpendiculairement à la face d'une autre pièce (issue #136).

La nouvelle pièce est toujours perpendiculaire à la pièce qui porte la face, et ses axes restent
parallèles aux siens : contre une grande face (épaisseur), la longueur part de la face (normale
sortante) et la largeur reste parallèle à celle de l'autre ; contre un chant (largeur), la
longueur part du chant et l'épaisseur reste parallèle ; contre une extrémité, la longueur suit
l'épaisseur de l'autre pièce (angle droit), la largeur reste parallèle et l'épaisseur de la
nouvelle pièce s'appuie sur la face.
"""

from __future__ import annotations

from freecad.menuiserie.core.geometry import Matrix3, Vec3, squared_rotation
from freecad.menuiserie.core.snap._model import Orientation, product
from freecad.menuiserie.core.vectors import cross

__all__ = ["face_section", "perpendicular_orientation"]

_LENGTH, _WIDTH, _THICKNESS = 0, 1, 2
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
    if normal_axis == _LENGTH:  # extrémité : angle droit, largeur parallèle à l'autre
        length = _column(seen, _THICKNESS)
        width = _column(seen, _WIDTH)
        thickness = cross(length, width)
    elif normal_axis == _THICKNESS:  # grande face : la largeur reste parallèle à l'autre
        width = _column(seen, _WIDTH)
        thickness = cross(length, width)
    else:  # chant : l'épaisseur reste parallèle à l'autre
        thickness = _column(seen, _THICKNESS)
        width = cross(thickness, length)
    axes = (length, width, thickness)
    rows = [[axis.component(row) for axis in axes] for row in range(3)]
    x, y, z = (Vec3.of(row) for row in rows)
    return Orientation(((x.x, x.y, x.z), (y.x, y.y, y.z), (z.x, z.y, z.z)))


def face_section(
    support: Matrix3, owner: Matrix3, extent: tuple[float, float], section: tuple[float, float]
) -> tuple[float, float]:
    """Section (largeur, épaisseur) de la nouvelle pièce posée contre une face d'étendue ``extent``
    (selon les deux premiers axes du repère d'appui ``support``), portée par une pièce de rotation
    ``owner`` et de section ``section``.

    Une cote dont l'axe est dans le plan de la face prend l'étendue de la face selon cet axe : sur
    une pièce dessinée (corps converti), la face peut être plus petite que l'encombrement. Une cote
    dont l'axe est la normale de la face garde celle de la pièce. ``section`` est rendue telle
    quelle si la pièce n'est pas d'équerre avec la face."""
    seen = squared_rotation(product(_transposed(support), owner))
    if any(value not in (-1.0, 0.0, 1.0) for row in seen for value in row):
        return section

    def along(axis: int, fallback: float) -> float:
        for row in (0, 1):
            if seen[row][axis] != 0.0 and extent[row] > 0.0:
                return extent[row]
        return fallback

    return along(_WIDTH, section[0]), along(_THICKNESS, section[1])
