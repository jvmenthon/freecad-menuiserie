# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bande de bois où poser la marque du sens du fil, dans le plan XY local d'une pièce.

Le contour réel (boucles : extérieure puis trous, polygones) est coupé par des droites parallèles
au fil. Entre deux cotes de sommets consécutives (une « tranche »), les mêmes arêtes sont coupées
et les bouts des segments de bois varient linéairement : il suffit donc de lire chaque droite de
sommet, juste au-dessus et juste au-dessous, et les deux bords d'une bande pour connaître
exactement le bois commun à toute la bande. La bande retenue est celle où la marque est la plus
grande : longueur de ce bois commun, fois la demi-largeur de la marque (bornée par sa longueur).
Rien ne passe au-dessus d'un trou ni d'un bord, même fin. Pur : ni FreeCAD, ni Qt.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Final

__all__ = ["MARK_LENGTH_RATIO", "MARK_WIDTH_RATIO", "GrainBand", "grain_band", "rectangle"]

Point2 = tuple[float, float]
Loop = Sequence[Point2]
Segment = tuple[float, float]
Band = tuple[float, Segment]  # demi-largeur, bois commun
MARK_WIDTH_RATIO: Final = 0.34  # demi-largeur de la marque, part de la largeur de la bande
MARK_LENGTH_RATIO: Final = 0.09  # demi-largeur maximale de la marque, part de sa longueur
MAX_SLICES: Final = 32  # tranches (les plus larges) où un milieu de bande est essayé
GRID: Final = 16  # milieux de bande essayés en plus, répartis sur l'étendue
MAX_HALVES: Final = 24  # demi-largeurs essayées jusqu'aux droites de sommets, au plus
WIDTH_STEPS: Final = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5)  # demi-largeurs essayées, part de l'étendue
_EPSILON: Final = 1e-7  # écart relatif à une droite de sommet pour lire la tranche voisine


@dataclass(frozen=True)
class GrainBand:
    """Segment de bois le long de l'axe du fil (``start`` à ``end``), à la cote ``across`` de
    l'autre axe, et largeur ``width`` de la bande autour de lui où ce segment reste dans le bois."""

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


def _segments(loops: Sequence[Loop], axis: int, across: float) -> list[Segment]:
    """Segments de bois (pair-impair : les trous sont exclus) de la droite de cote ``across``
    parallèle à l'axe ``axis``."""
    other = 1 - axis
    found: list[float] = []
    for loop in loops:
        for a, b in zip(loop, [*loop[1:], loop[0]], strict=True):
            if (a[other] <= across < b[other]) or (b[other] <= across < a[other]):
                ratio = (across - a[other]) / (b[other] - a[other])
                found.append(a[axis] + ratio * (b[axis] - a[axis]))
    found.sort()
    return [(found[i], found[i + 1]) for i in range(0, len(found) - 1, 2)]


class _Slices:
    """Coupes du contour aux droites de sommets, juste au-dessous et juste au-dessus, triées."""

    def __init__(self, loops: Sequence[Loop], axis: int) -> None:
        self.loops, self.axis = loops, axis
        self.levels = sorted({point[1 - axis] for loop in loops for point in loop})
        self.low, self.high = self.levels[0], self.levels[-1]
        self.epsilon = _EPSILON * max(self.high - self.low, 1.0)
        self.positions = [level + side * self.epsilon for level in self.levels for side in (-1, 1)]
        self.rows = [_segments(loops, axis, position) for position in self.positions]

    def widening(self, center: float, point: float, halves: Sequence[float]) -> Iterator[Band]:
        """Pour chaque demi-largeur de ``halves`` (croissantes), le bois commun autour de
        l'abscisse ``point`` à toutes les droites de la bande ``center`` ± demi-largeur, jusqu'à
        la première qui sort du bois. Exact : coupes aux deux bords de la bande et aux droites de
        sommets entre eux (les bouts des segments varient linéairement entre deux droites)."""
        below = bisect_right(self.positions, center)  # premières coupes hors de la bande
        above = below - 1
        inner: Segment | None = (float("-inf"), float("inf"))
        for half in halves:
            low, high = center - half, center + half
            if low < self.low or high > self.high:
                return
            while inner is not None and below > 0 and self.positions[below - 1] > low:
                below -= 1
                inner = _narrowed(inner, self.rows[below], point)
            while (
                inner is not None
                and above + 1 < len(self.rows)
                and (self.positions[above + 1] < high)
            ):
                above += 1
                inner = _narrowed(inner, self.rows[above], point)
            edges = (_segments(self.loops, self.axis, low), _segments(self.loops, self.axis, high))
            common = _narrowed(_narrowed(inner, edges[0], point), edges[1], point)
            if common is None:
                return
            yield half, common

    def centers(self) -> list[float]:
        """Milieux de bande essayés (quart, milieu et trois quarts des tranches les plus larges,
        et une grille), du plus proche au plus éloigné du milieu du contour."""
        slices = sorted(zip(self.levels, self.levels[1:], strict=False), key=lambda s: s[0] - s[1])
        extent = self.high - self.low
        found = [
            lo + ratio * (hi - lo)
            for lo, hi in slices[:MAX_SLICES]
            if hi - lo > 4 * self.epsilon
            for ratio in (0.25, 0.5, 0.75)
        ]
        found += [self.low + extent * (k + 0.5) / GRID for k in range(GRID)]
        middle = (self.low + self.high) / 2
        return sorted(found, key=lambda center: abs(center - middle))

    def halves(self, center: float) -> list[float]:
        """Demi-largeurs essayées, croissantes : jusqu'aux droites de sommets (au plus
        :data:`MAX_HALVES`, réparties) et une grille."""
        extent = self.high - self.low
        to_levels = sorted(abs(center - level) - 2 * self.epsilon for level in self.levels)
        stride = max(len(to_levels) // MAX_HALVES, 1)
        found = set(to_levels[::stride]) | {ratio * extent for ratio in WIDTH_STEPS}
        return sorted(half for half in found if half > self.epsilon)


def _narrowed(common: Segment | None, segments: list[Segment], point: float) -> Segment | None:
    """``common`` réduit au segment de ``segments`` qui contient ``point`` (``None`` sans)."""
    hit = next((s for s in segments if s[0] <= point <= s[1]), None)
    if common is None or hit is None:
        return None
    return (max(common[0], hit[0]), min(common[1], hit[1]))


def _score(segment: Segment, half: float) -> float:
    """Taille de la marque posée sur ``segment`` dans une bande de demi-largeur ``half``."""
    length = segment[1] - segment[0]
    return length * min(MARK_WIDTH_RATIO * 2 * half, MARK_LENGTH_RATIO * length)


def grain_band(loops: Sequence[Loop], axis: int) -> GrainBand | None:
    """Bande de bois le long de l'axe ``axis`` (0 = X, 1 = Y) du contour ``loops`` où la marque
    du fil est la plus grande (à égalité, la plus proche du milieu) ; le segment rendu est le bois
    commun à toute la bande. ``None`` si le contour est vide ou plat."""
    if sum(len(loop) for loop in loops) < 3:
        return None
    slices = _Slices(loops, axis)
    if slices.high - slices.low <= 4 * slices.epsilon:
        return None
    best: tuple[float, GrainBand] | None = None
    for center in slices.centers():
        for segment in _segments(loops, axis, center):
            point = (segment[0] + segment[1]) / 2
            for half, common in slices.widening(center, point, slices.halves(center)):
                score = _score(common, half)
                if common[1] - common[0] > slices.epsilon and (
                    best is None or score > best[0] * (1 + 1e-9)
                ):
                    best = (score, GrainBand(common[0], common[1], center, 2 * half))
    return best[1] if best is not None else None
