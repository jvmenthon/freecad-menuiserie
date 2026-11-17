# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aimantation de l'angle sur l'orientation des pièces voisines (ADR 0025, complété).

Les arêtes d'une boîte sont à angle droit : l'angle d'une pièce autour d'un axe n'est lu qu'à
90° près. Une pièce tournée s'aimante sur une voisine quand l'une de leurs arêtes devient
parallèle à l'écran de l'anneau, à ``ALIGN_TOLERANCE_DEGREES`` près. Aucun import de FreeCAD.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Final

from freecad.menuiserie.core.geometry import Matrix3, Vec3
from freecad.menuiserie.core.vectors import dot

__all__ = ["ALIGN_TOLERANCE_DEGREES", "align_offsets", "aligned_turn", "edge_angles"]

ALIGN_TOLERANCE_DEGREES: Final = 3.0  # écart d'angle en deçà duquel la pièce s'aligne
_QUARTER: Final = 90.0
# longueur projetée minimale d'une arête pour compter (arête à moins de ~25° du plan) : plus
# inclinée, sa projection n'a plus de sens visuel et deux arêtes ne s'y projettent plus d'équerre
_IN_PLANE: Final = 0.9
_DUPLICATE: Final = 0.01


def edge_angles(rotation: Matrix3, u: Vec3, v: Vec3) -> tuple[float, ...]:
    """Angles (degrés, dans [0, 90[) des arêtes de la boîte de rotation ``rotation`` projetées
    dans le plan de base ``(u, v)`` ; les arêtes presque perpendiculaires au plan sont omises."""
    found: list[float] = []
    for column in range(3):
        edge = Vec3(rotation[0][column], rotation[1][column], rotation[2][column])
        x, y = dot(edge, u), dot(edge, v)
        if math.hypot(x, y) >= _IN_PLANE:
            found.append(math.degrees(math.atan2(y, x)) % _QUARTER)
    return tuple(found)


def align_offsets(
    own: Matrix3, neighbors: Iterable[Matrix3], u: Vec3, v: Vec3
) -> tuple[float, ...]:
    """Rotations (degrés, dans [0, 90[) qui rendent une arête de ``own`` parallèle à une arête
    d'un voisin, dans le plan ``(u, v)``, pour chaque arête de ``own`` proche du plan (deux
    arêtes ne s'y projettent d'équerre que si l'axe est celui de la troisième). Vide si ``own``
    n'a pas d'arête proche du plan."""
    mine = edge_angles(own, u, v)
    offsets: list[float] = []
    for rotation in neighbors:
        for angle in edge_angles(rotation, u, v):
            for own_angle in mine:
                offset = (angle - own_angle) % _QUARTER
                if all(_gap(offset, known) > _DUPLICATE for known in offsets):
                    offsets.append(offset)
    return tuple(offsets)


def _gap(a: float, b: float) -> float:
    """Écart (degrés) entre deux angles lus à 90° près."""
    d = abs(a - b) % _QUARTER
    return min(d, _QUARTER - d)


def aligned_turn(
    travelled: float, offsets: Iterable[float], tolerance: float = ALIGN_TOLERANCE_DEGREES
) -> float | None:
    """Rotation alignée la plus proche de ``travelled`` (``offset`` + multiple de 90°) à
    ``tolerance`` degrés près ; ``None`` si aucune (ou si ``travelled`` n'est pas fini)."""
    if not math.isfinite(travelled):
        return None
    best: float | None = None
    for offset in offsets:
        candidate = offset + _QUARTER * round((travelled - offset) / _QUARTER)
        if abs(candidate - travelled) <= tolerance and (
            best is None or abs(candidate - travelled) < abs(best - travelled)
        ):
            best = candidate
    return best
