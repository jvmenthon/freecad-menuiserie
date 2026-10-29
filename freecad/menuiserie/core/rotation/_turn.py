# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rotation autour d'un axe fixe du document et aimantation de l'angle (A2, A3, ADR 0025)."""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import Matrix3, RigidTransform, Vec3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.rotation._angles import matrix_of

_DEFAULT_STEP_DEGREES = 15.0


def check_axis(owner: str, axis: int) -> None:
    """``ValueError`` si ``axis`` n'est pas 0 (X), 1 (Y) ou 2 (Z)."""
    if axis not in (0, 1, 2):
        raise ValueError(f"{owner}.axis : 0 (X), 1 (Y) ou 2 (Z) attendu")


def axis_rotation(axis: int, angle: float) -> Matrix3:
    """Matrice de la rotation de ``angle`` degrés autour de l'axe X, Y ou Z du repère."""
    check_axis("axis_rotation", axis)
    angles = [0.0, 0.0, 0.0]
    angles[axis] = angle
    return matrix_of((angles[0], angles[1], angles[2]))


def turned_about(
    transform: RigidTransform, dimensions: Dimensions, axis: int, angle: float
) -> RigidTransform:
    """Placement après une rotation de ``angle`` degrés autour de l'axe fixe ``axis`` (0 = X,
    1 = Y, 2 = Z) du repère de ``transform``, passant par le centre de la boîte L x l x e.

    R' = R(axe, Δ) · R ; le centre ne bouge pas. Angle non fini : ``ValueError``.
    """
    check_axis("turned_about", axis)
    if not math.isfinite(angle):
        raise ValueError("turned_about.angle : angle fini attendu")
    center = Vec3(dimensions.length / 2, dimensions.width / 2, dimensions.thickness / 2)
    spin = RigidTransform(axis_rotation(axis, angle), Vec3(0.0, 0.0, 0.0))
    rotation = spin.compose(transform).rotation
    held = transform.apply(center)
    carried = RigidTransform(rotation, Vec3(0.0, 0.0, 0.0)).rotate(center)
    return RigidTransform(
        rotation, Vec3(held.x - carried.x, held.y - carried.y, held.z - carried.z)
    )


def snapped_angle(angle: float, step: float = _DEFAULT_STEP_DEGREES, free: bool = False) -> float:
    """Angle (degrés) arrondi au multiple de ``step`` le plus proche ; ``free`` : au dixième.

    Les demi-pas s'arrondissent vers le haut. ``ValueError`` si ``angle`` ou ``step`` n'est pas
    fini, ou si ``step`` n'est pas strictement positif.
    """
    if not math.isfinite(angle):
        raise ValueError("snapped_angle.angle : angle fini attendu")
    if not math.isfinite(step) or step <= 0:
        raise ValueError("snapped_angle.step : pas fini strictement positif attendu")
    unit = 0.1 if free else step
    count = angle / unit
    if not math.isfinite(count):  # angle immense ou pas minuscule : le quotient déborde
        raise ValueError("snapped_angle : angle ou pas hors des valeurs admises")
    return math.floor(count + 0.5) * unit + 0.0
