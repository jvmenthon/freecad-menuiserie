# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces en biais partagées par les tests (ADR 0024) : rotations quelconques et pose d'un
bout contre la face d'un montant."""

from __future__ import annotations

import math
from typing import Literal

from freecad.menuiserie.core.geometry import PlacedBlock
from tests.unit.aides_assemblages import Point, placed, rotation_y, rotation_z

Matrix = list[list[float]]
Mode = Literal["pointe", "hors tout", "cheval"]


def rotation_x(degrees: float) -> Matrix:
    """Rotation autour de X, par lignes."""
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, cos, -sin], [0.0, sin, cos]]


def product(*rotations: Matrix) -> Matrix:
    """Produit de rotations (la dernière s'applique en premier)."""
    result = rotations[0]
    for right in rotations[1:]:
        result = [
            [sum(result[i][k] * right[k][j] for k in range(3)) for j in range(3)] for i in range(3)
        ]
    return result


def turn(rotation: Matrix, point: Point) -> Point:
    """Point tourné."""
    return (
        sum(rotation[0][j] * point[j] for j in range(3)),
        sum(rotation[1][j] * point[j] for j in range(3)),
        sum(rotation[2][j] * point[j] for j in range(3)),
    )


def stile_block(width: float = 60.0, thickness: float = 22.0) -> PlacedBlock:
    """Montant à l'origine : x = longueur (600), y = largeur, z = épaisseur."""
    return placed((600.0, width, thickness), rotation_z(0.0), (0.0, 0.0, 0.0))


def rail_against_stile(
    rotation: Matrix,
    mode: Mode = "cheval",
    centre_x: float = 300.0,
    centre_z: float = 11.0,
    size: Point = (280.0, 60.0, 22.0),
) -> PlacedBlock:
    """Traverse de rotation ``rotation`` dont le bout (-X local) rencontre la face y = 60 du
    montant (``stile_block()``), son centre en (``centre_x``, 60, ``centre_z``).

    ``pointe`` : le coin le plus bas du bout est sur la face ; ``hors tout`` : le plus haut y est ;
    ``cheval`` : le centre du bout est sur la face."""
    _, width, thickness = size
    corners = [turn(rotation, (0.0, y, z)) for y in (0.0, width) for z in (0.0, thickness)]
    centre = turn(rotation, (0.0, width / 2, thickness / 2))
    heights = [corner[1] for corner in corners]
    level = {"pointe": min(heights), "hors tout": max(heights), "cheval": centre[1]}[mode]
    base = (centre_x - centre[0], 60.0 - level, centre_z - centre[2])
    return placed(size, rotation, base)


def tilted_rail(
    degrees: float, mode: Mode = "cheval", centre_x: float = 300.0, centre_z: float = 11.0
) -> PlacedBlock:
    """Traverse tournée de ``degrees`` dans le plan du montant autour de Z (biais simple)."""
    return rail_against_stile(rotation_z(90.0 + degrees), mode, centre_x, centre_z)


def leaning_rail(
    degrees: float, mode: Mode = "cheval", centre_x: float = 300.0, centre_z: float = 40.0
) -> PlacedBlock:
    """Traverse inclinée de ``degrees`` autour de sa largeur (le bout penche vers l'épaisseur du
    montant) : pour un montant épais (``stile_block(thickness=80)``)."""
    rotation = product(rotation_z(90.0), rotation_y(degrees))
    return rail_against_stile(rotation, mode, centre_x, centre_z)


def spun_rail(degrees: float) -> PlacedBlock:
    """Traverse d'équerre dont le bout est tourné de ``degrees`` autour de son propre axe."""
    return rail_against_stile(product(rotation_z(90.0), rotation_x(degrees)), "cheval")


__all__ = [
    "Mode",
    "leaning_rail",
    "product",
    "rail_against_stile",
    "rotation_x",
    "rotation_y",
    "spun_rail",
    "stile_block",
    "tilted_rail",
    "turn",
]
