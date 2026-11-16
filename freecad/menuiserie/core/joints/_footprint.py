# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pose de points (pieds) dans le contour réel d'une pièce non rectangulaire.

Les contours sont des boucles de sommets (x, y) dans le plan de la pièce ; les trous comptent
(règle pair-impair). Longueurs en mm.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

__all__ = ["fit_centers", "inside", "margin"]

Point = tuple[float, float]
Loops = Sequence[Sequence[Point]]
_EPS: Final = 1e-6
SPACING_FACTOR: Final = 2.0  # écart minimal entre deux pieds : 2 embases (centre à centre)


def _segments(loops: Loops) -> list[tuple[Point, Point]]:
    return [(loop[i], loop[(i + 1) % len(loop)]) for loop in loops for i in range(len(loop))]


def inside(point: Point, loops: Loops) -> bool:
    """Vrai si ``point`` est dans la matière (règle pair-impair sur toutes les boucles)."""
    x, y = point
    odd = False
    for (ax, ay), (bx, by) in _segments(loops):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            odd = not odd
    return odd


def _distance(point: Point, segment: tuple[Point, Point]) -> float:
    (ax, ay), (bx, by) = segment
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = (
        0.0
        if length2 == 0.0
        else max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / length2))
    )
    return math.hypot(point[0] - (ax + t * dx), point[1] - (ay + t * dy))


def margin(point: Point, loops: Loops) -> float:
    """Distance de ``point`` au bord le plus proche s'il est dans la matière, sinon 0."""
    if not inside(point, loops):
        return 0.0
    return min(_distance(point, segment) for segment in _segments(loops))


def _candidates(point: Point, loops: Loops, clearance: float) -> list[Point]:
    """Points à ``clearance`` du bord, les plus proches de ``point`` d'abord : projections sur
    chaque côté, décalées vers la matière."""
    found = []
    for (ax, ay), (bx, by) in _segments(loops):
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        if length == 0.0:
            continue
        t = max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / length**2))
        foot = (ax + t * dx, ay + t * dy)
        for sign in (1.0, -1.0):
            moved = (
                foot[0] - sign * dy / length * clearance,
                foot[1] + sign * dx / length * clearance,
            )
            if margin(moved, loops) >= clearance - _EPS:
                found.append(moved)
    found.sort(key=lambda c: math.hypot(c[0] - point[0], c[1] - point[1]))
    return found


def fit_centers(
    wanted: Sequence[Point], loops: Loops, edge: float, radius: float
) -> tuple[Point, ...] | None:
    """Centres de pieds dans le contour : un centre voulu déjà à ``edge`` du bord reste en
    place, les autres sont ramenés au point le plus proche à ``edge`` du bord (``radius`` au
    moins si la pièce est trop étroite pour ``edge``). Deux pieds ne sont jamais collés : à moins
    de deux embases d'écart (centre à centre), le second est supprimé. ``None`` si un pied n'a
    aucune place."""
    placed: list[Point] = []
    for point in wanted:
        chosen = None
        for clearance in (edge, radius):
            if margin(point, loops) >= clearance - _EPS:
                chosen = point
            else:
                near = _candidates(point, loops, clearance)
                chosen = near[0] if near else None
            if chosen is not None:
                break
        if chosen is None:
            return None
        if all(
            math.hypot(chosen[0] - p[0], chosen[1] - p[1]) >= SPACING_FACTOR * 2 * radius - _EPS
            for p in placed
        ):
            placed.append(chosen)
    return tuple(placed)
