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
from collections.abc import Iterable, Iterator, Sequence
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
SEARCH_VERTICES: Final = 400  # sommets du contour allégé pour la recherche, environ
SHRINK_STEPS: Final = (0.25, 0.5, 0.7, 0.85, 1.0)  # demi-largeurs recoupées, part de la trouvée
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


Edge = tuple[float, float, float, float]  # cote et abscisse de chaque bout (cote croissante)


def _edges(loops: Sequence[Loop], axis: int) -> list[Edge]:
    """Arêtes non parallèles au fil des boucles d'au moins trois points, triées par cote basse."""
    other = 1 - axis
    found: list[Edge] = []
    for loop in (loop for loop in loops if len(loop) >= 3):
        for a, b in zip(loop, [*loop[1:], loop[0]], strict=True):
            if a[other] != b[other]:
                low, high = (a, b) if a[other] < b[other] else (b, a)
                found.append((low[other], low[axis], high[other], high[axis]))
    return sorted(found)


def _cut(edges: Iterable[Edge], across: float) -> list[Segment]:
    """Segments de bois (pair-impair : les trous sont exclus) de la droite de cote ``across``,
    d'après les arêtes ``edges`` qui peuvent la couper."""
    found = sorted(
        x0 + (across - y0) / (y1 - y0) * (x1 - x0) for y0, x0, y1, x1 in edges if y0 <= across < y1
    )
    return [(found[i], found[i + 1]) for i in range(0, len(found) - 1, 2)]


def _segments(loops: Sequence[Loop], axis: int, across: float) -> list[Segment]:
    """Segments de bois de la droite de cote ``across`` parallèle à l'axe ``axis``."""
    return _cut(_edges(loops, axis), across)


class _Slices:
    """Coupes du contour aux droites de sommets, juste au-dessous et juste au-dessus, triées.
    Chaque tranche garde les seules arêtes qui la traversent (balayage) : une coupe ne lit
    qu'elles, ce qui reste rapide sur un contour courbe très discrétisé."""

    def __init__(self, loops: Sequence[Loop], axis: int) -> None:
        edges = _edges(loops, axis)
        self.levels = sorted({edge[0] for edge in edges} | {edge[2] for edge in edges})
        self.low, self.high = self.levels[0], self.levels[-1]
        self.epsilon = _EPSILON * max(self.high - self.low, 1.0)
        self.slab_edges: list[list[Edge]] = []
        active: list[Edge] = []
        waiting = iter(edges)
        pending = next(waiting, None)
        for low, high in zip(self.levels, self.levels[1:], strict=False):
            while pending is not None and pending[0] <= low:
                active.append(pending)
                pending = next(waiting, None)
            active = [edge for edge in active if edge[2] >= high]
            self.slab_edges.append(active)
        self.positions = [level + side * self.epsilon for level in self.levels for side in (-1, 1)]
        self.rows = [self.cut(position) for position in self.positions]

    def cut(self, across: float) -> list[Segment]:
        """Segments de bois de la droite de cote ``across`` (vide hors du contour)."""
        slab = bisect_right(self.levels, across) - 1
        if slab < 0 or slab >= len(self.slab_edges):
            return []
        return _cut(self.slab_edges[slab], across)

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
            edges = (self.cut(low), self.cut(high))
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


def _decimated(loops: Sequence[Loop]) -> list[Loop] | None:
    """Contour allégé pour la recherche (au plus :data:`SEARCH_VERTICES` sommets environ) : un
    sommet sur ``k`` de chaque boucle assez longue, les petites boucles restent entières ;
    ``None`` si le contour est déjà assez léger."""
    total = sum(len(loop) for loop in loops)
    step = -(-total // SEARCH_VERTICES)
    if step <= 1:
        return None
    return [loop[::step] if len(loop) >= 3 * step else loop for loop in loops]


_Found = tuple[float, float, float, float]  # score, milieu de bande, abscisse, demi-largeur


def _search(slices: _Slices) -> _Found | None:
    """Bande où la marque est la plus grande (à égalité, la plus proche du milieu)."""
    best: _Found | None = None
    for center in slices.centers():
        for segment in slices.cut(center):
            point = (segment[0] + segment[1]) / 2
            for half, common in slices.widening(center, point, slices.halves(center)):
                score = _score(common, half)
                if common[1] - common[0] > slices.epsilon and (
                    best is None or score > best[0] * (1 + 1e-9)
                ):
                    best = (score, center, (common[0] + common[1]) / 2, half)
    return best


def grain_band(loops: Sequence[Loop], axis: int) -> GrainBand | None:
    """Bande de bois le long de l'axe ``axis`` (0 = X, 1 = Y) du contour ``loops`` où la marque
    du fil est la plus grande (à égalité, la plus proche du milieu) ; le segment rendu est le bois
    commun à toute la bande, lu sur le contour complet. La recherche se fait sur un contour
    allégé quand il est très discrétisé (rafraîchissement en direct), puis la bande trouvée est
    recoupée sur le contour complet (rétrécie si besoin). ``None`` si le contour est vide ou
    plat."""
    if axis not in (0, 1):
        raise ValueError(f"axe du fil inconnu : {axis!r}")
    if not _edges(loops, axis):
        return None
    slices = _Slices(loops, axis)
    if not slices.high - slices.low > 4 * slices.epsilon:  # aussi faux pour NaN
        return None
    coarse = _decimated(loops)
    found = _search(slices if coarse is None else _Slices(coarse, axis))
    if found is None:
        return None
    _, center, point, half = found
    exact = list(slices.widening(center, point, [half * ratio for ratio in SHRINK_STEPS]))
    if not exact or exact[-1][1][1] - exact[-1][1][0] <= slices.epsilon:
        return None
    half, common = exact[-1]
    return GrainBand(common[0], common[1], center, 2 * half)
