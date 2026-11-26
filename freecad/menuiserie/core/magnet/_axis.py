# SPDX-License-Identifier: LGPL-2.1-or-later
"""Flèches et poignées de la pièce, rayon de la souris et point de l'axe le plus proche de ce
rayon (A1, A2 ; ADR 0021, point 2)."""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Box, Vec3
from freecad.menuiserie.core.magnet._model import Arrow, Handle, Ray
from freecad.menuiserie.core.snap import Frame
from freecad.menuiserie.core.vectors import dot

MAGNET_PX = 10.0  # tolérance de l'aimant à l'écran (pixels)


def mouse_ray(focal: Vec3, direction: Vec3, camera: Vec3 | None) -> Ray:
    """Rayon de la souris : ``focal`` est le point du plan focal sous le curseur ; caméra
    orthogonale (``camera`` absent) : direction de vue ; perspective : caméra vers ``focal``."""
    if camera is None:
        return Ray(focal, direction)
    return Ray(camera, focal - camera)


def handle_point(box: Box, handle: Handle) -> Vec3:
    """Point de la poignée ``handle`` de ``box`` (repère de la pièce) : sur sa face, décalé du
    milieu d'un quart de la longueur (de la largeur pour les faces de bout, axe X), l'une vers
    chaque bout : le milieu tombe sur le tracé de la flèche de son axe, qui part du centre."""
    values = [box.center(i) for i in range(3)]
    values[handle.axis] = box.hi(handle.axis) if handle.at_end else box.lo(handle.axis)
    side = 1 if handle.axis == 0 else 0
    quarter = (box.hi(side) - box.lo(side)) / 4
    values[side] += -quarter if handle.at_end else quarter
    return Vec3.of(values)


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
    return Arrow(axis, center, center + direction.scaled(size))


def axis_param(ray: Ray, axis_line: Ray) -> float | None:
    """Paramètre ``t`` du point ``axis_line.origin + t · direction`` le plus proche de la droite du
    rayon ; ``None`` si le rayon est parallèle à l'axe à ``ANGLE_TOLERANCE`` près (A2).

    Le déplacement est la différence avec le paramètre relevé au début du glissement.
    """
    d1, d2 = ray.direction, axis_line.direction
    cosine = dot(d1, d2)
    if math.sqrt(max(0.0, 1.0 - cosine * cosine)) <= ANGLE_TOLERANCE:
        return None
    o1, o2 = ray.origin, axis_line.origin
    w = o1 - o2
    return (dot(d2, w) - cosine * dot(d1, w)) / (1.0 - cosine * cosine)
