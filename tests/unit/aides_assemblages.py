# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces placées partagées par les tests de géométrie et d'assemblage (cadre de référence J3)."""

from __future__ import annotations

import math

from freecad.menuiserie.core.geometry import PlacedBlock, RigidTransform
from freecad.menuiserie.core.part_model import Dimensions

Point = tuple[float, float, float]


def rotation_z(degrees: float) -> list[list[float]]:
    """Rotation autour de Z, par lignes."""
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    return [[cos, -sin, 0.0], [sin, cos, 0.0], [0.0, 0.0, 1.0]]


def matrix(rotation: list[list[float]], base: Point) -> list[list[float]]:
    """Matrice 4 x 4 (lignes) d'un placement, comme ``Placement.toMatrix()``."""
    return [[*rotation[i], base[i]] for i in range(3)] + [[0.0, 0.0, 0.0, 1.0]]


def block(size: Point, base: Point = (0.0, 0.0, 0.0), degrees_z: float = 0.0) -> PlacedBlock:
    """Pièce de cotes L x l x e placée en ``base``, tournée de ``degrees_z`` autour de Z."""
    placement = RigidTransform.from_matrix(matrix(rotation_z(degrees_z), base))
    return PlacedBlock(Dimensions(*size), placement)


def stile(width: float = 60.0) -> PlacedBlock:
    """Montant M1 du cadre de référence."""
    return block((600.0, width, 22.0))


def rail(width: float = 60.0, thickness: float = 22.0, y: float = 60.0) -> PlacedBlock:
    """Traverse T1 : bout contre le chant intérieur de M1 (y = ``y``)."""
    return block((280.0, width, thickness), (width, y, 0.0), 90.0)
