# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bande de bois où poser la marque du sens du fil, dans le plan XY local d'une pièce.

Le contour réel (boucles : extérieure puis trous) est coupé par des droites parallèles au fil ; la
bande retenue est le plus long segment de bois dans le sens du fil, centré dans la largeur où ce
segment reste entièrement dans le bois. Une pièce rectangulaire donne sa ligne médiane. Pur : ni
FreeCAD, ni Qt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

__all__ = ["GrainBand", "grain_band", "rectangle"]

Point2 = tuple[float, float]
Loop = Sequence[Point2]
SAMPLES: Final = 64  # droites essayées dans la largeur du contour
_TOLERANCE: Final = 1e-6


@dataclass(frozen=True)
class GrainBand:
    """Segment de bois le long de l'axe du fil (``start`` à ``end``), à la cote ``across`` de
    l'autre axe, et largeur ``width`` de bois autour de lui (le segment y reste dans le bois)."""

    start: float
    end: float
    across: float
    width: float

    @property
    def length(self) -> float:
        """Longueur du segment."""
        return self.end - self.start


def rectangle(length: float, width: float) -> tuple[tuple[Point2, ...], ...]:
    """Contour d'une pièce rectangulaire ``length`` sur ``width`` à l'origine."""
    return (((0.0, 0.0), (length, 0.0), (length, width), (0.0, width)),)


def _crossings(loops: Sequence[Loop], axis: int, across: float) -> list[float]:
    """Abscisses (le long de ``axis``) où la droite de cote ``across`` coupe les boucles, triées."""
    other = 1 - axis
    found: list[float] = []
    for loop in loops:
        for a, b in zip(loop, [*loop[1:], loop[0]], strict=True):
            if (a[other] <= across < b[other]) or (b[other] <= across < a[other]):
                ratio = (across - a[other]) / (b[other] - a[other])
                found.append(a[axis] + ratio * (b[axis] - a[axis]))
    return sorted(found)


def _segments(loops: Sequence[Loop], axis: int, across: float) -> list[tuple[float, float]]:
    """Segments de bois (pair-impair : les trous sont exclus) de la droite de cote ``across``."""
    xs = _crossings(loops, axis, across)
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def _covers(loops: Sequence[Loop], axis: int, across: float, segment: tuple[float, float]) -> bool:
    start, end = segment
    return any(
        a <= start + _TOLERANCE and b >= end - _TOLERANCE for a, b in _segments(loops, axis, across)
    )


def grain_band(loops: Sequence[Loop], axis: int) -> GrainBand | None:
    """Plus long segment de bois le long de l'axe ``axis`` (0 = X, 1 = Y) dans le contour
    ``loops`` (à égalité, le plus proche du milieu), recentré dans la largeur où il reste dans le
    bois ; ``None`` si le contour est vide ou plat."""
    other = 1 - axis
    values = [point[other] for loop in loops for point in loop]
    if not values or max(values) - min(values) <= _TOLERANCE:
        return None
    low, high = min(values), max(values)
    step = (high - low) / SAMPLES
    middle = (low + high) / 2
    best: tuple[tuple[float, float], float, tuple[float, float]] | None = None
    for index in range(1, SAMPLES):
        across = low + index * step
        for segment in _segments(loops, axis, across):
            key = (round(segment[1] - segment[0], 6), -abs(across - middle))
            if best is None or key > best[0]:
                best = (key, across, segment)
    if best is None or best[2][1] - best[2][0] <= _TOLERANCE:
        return None
    _, across, segment = best
    below = _edge(loops, axis, segment, (across, -step, low))
    above = _edge(loops, axis, segment, (across, step, high))
    return GrainBand(segment[0], segment[1], (below + above) / 2, above - below)


def _edge(
    loops: Sequence[Loop], axis: int, segment: tuple[float, float], walk: tuple[float, float, float]
) -> float:
    """Bord du bois autour de ``segment``, en partant de la cote ``walk[0]`` par pas ``walk[1]``
    jusqu'à la borne ``walk[2]`` du contour : la borne si elle est atteinte, sinon le milieu du
    dernier pas (le bord exact est entre deux droites essayées)."""
    across, step, bound = walk
    while (across + step - bound) * step < 0 and _covers(loops, axis, across + step, segment):
        across += step
    if (across + step - bound) * step >= 0:
        return bound
    return across + step / 2
