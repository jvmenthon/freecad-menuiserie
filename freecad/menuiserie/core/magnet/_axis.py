# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flèches de la pièce et point de l'axe le plus proche du rayon de la souris (A1, A2)."""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Box, Vec3
from freecad.menuiserie.core.magnet._model import Arrow, Ray
from freecad.menuiserie.core.snap import Frame


def arrows(frame: Frame, box: Box, size: float) -> tuple[Arrow, Arrow, Arrow]:
    """Trois flèches X, Y, Z du repère ``frame`` de la pièce, du centre de ``box`` (repère de la
    pièce) vers le sens positif de l'axe, de longueur ``size`` mm (A1)."""
    if not math.isfinite(size) or size <= 0:
        raise ValueError("arrows.size : longueur strictement positive attendue")
    local_center = Vec3(box.center(0), box.center(1), box.center(2))
    center = frame.to_transform().apply(local_center)
    return (
        _arrow(0, center, frame.x, size),
        _arrow(1, center, frame.y, size),
        _arrow(2, center, frame.z, size),
    )


def _arrow(axis: int, center: Vec3, direction: Vec3, size: float) -> Arrow:
    end = Vec3(
        center.x + direction.x * size, center.y + direction.y * size, center.z + direction.z * size
    )
    return Arrow(axis, center, end)


def _dot(a: Vec3, b: Vec3) -> float:
    return a.x * b.x + a.y * b.y + a.z * b.z


def axis_param(ray: Ray, axis_line: Ray) -> float | None:
    """Paramètre ``t`` du point ``axis_line.origin + t · direction`` le plus proche de la droite du
    rayon ; ``None`` si le rayon est parallèle à l'axe à ``ANGLE_TOLERANCE`` près (A2).

    Le déplacement est la différence avec le paramètre relevé au début du glissement.
    """
    d1, d2 = ray.direction, axis_line.direction
    cosine = _dot(d1, d2)
    if math.sqrt(max(0.0, 1.0 - cosine * cosine)) <= ANGLE_TOLERANCE:
        return None
    o1, o2 = ray.origin, axis_line.origin
    w = Vec3(o1.x - o2.x, o1.y - o2.y, o1.z - o2.z)
    return (_dot(d2, w) - cosine * _dot(d1, w)) / (1.0 - cosine * cosine)
