# SPDX-License-Identifier: LGPL-2.1-or-later
"""Angles X, Y, Z du ``Placement`` de FreeCAD et matrice de rotation (A1, ADR 0025)."""

from __future__ import annotations

import math
from typing import Final

from freecad.menuiserie.core.geometry import Matrix3

Angles = tuple[float, float, float]

# En dessous, cos(tangage) est nul à la précision des flottants : blocage de cardan.
_GIMBAL: Final = 1e-9


def _clean(degrees: float) -> float:
    """Degrés sans zéro négatif (``-0.0``)."""
    return degrees + 0.0


def angles_of(matrix: Matrix3) -> Angles:
    """Angles (X, Y, Z) en degrés tels que ``matrix`` = Rz · Ry · Rx (convention du ``Placement``).

    Tangage Y dans [-90, 90]. À ±90° (blocage de cardan), X est ramené à 0 et Z porte tout ;
    jamais de ``nan``.
    """
    flat = [value for row in matrix for value in row]
    if not all(math.isfinite(value) for value in flat):
        raise ValueError("angles_of : matrice non finie")
    horizontal = math.hypot(matrix[0][0], matrix[1][0])
    pitch = math.atan2(-matrix[2][0], horizontal)
    if horizontal < _GIMBAL:
        roll = 0.0
        yaw = math.atan2(-matrix[0][1], matrix[1][1])
    else:
        roll = math.atan2(matrix[2][1], matrix[2][2])
        yaw = math.atan2(matrix[1][0], matrix[0][0])
    return (
        _clean(math.degrees(roll)),
        _clean(math.degrees(pitch)),
        _clean(math.degrees(yaw)),
    )


def matrix_of(angles: Angles) -> Matrix3:
    """Matrice de rotation Rz · Ry · Rx pour les angles (X, Y, Z) en degrés."""
    if len(angles) != 3 or not all(math.isfinite(value) for value in angles):
        raise ValueError("matrix_of : trois angles finis attendus")
    ca, cb, cc = (math.cos(math.radians(value)) for value in angles)
    sa, sb, sc = (math.sin(math.radians(value)) for value in angles)
    return (
        (cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa),
        (sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa),
        (-sb, cb * sa, cb * ca),
    )
