# SPDX-License-Identifier: LGPL-2.1-or-later
"""Section plane (segments et arcs d'ellipse exacts) balayée en ligne droite (ADR 0029, CH-a).

Un profil d'arête est une section plane enlevée le long d'une arête : ``core/`` la décrit et en
donne l'aire, les bornes et le contrôle de validité en Python pur ; ``features/`` en tire le
solide ``Part``. Les coordonnées de la section sont des couples ``(u, v)`` en mm dans un repère
orthonormé défini par l':class:`Extrusion`. Aucune dépendance externe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.vectors import cross, dot, norm

__all__ = ["Arc", "Extrusion", "Point2", "Section", "Segment"]

Point2 = tuple[float, float]

_CLOSED: Final = 1e-9  # mm : bout d'un élément confondu avec le début du suivant
_SAMPLES: Final = 24  # points par arc pour le contrôle d'auto-intersection
_QUARTER: Final = math.pi / 2


@dataclass(frozen=True)
class Segment:
    """Segment de droite de ``start`` à ``end``."""

    start: Point2
    end: Point2


@dataclass(frozen=True)
class Arc:
    """Arc d'ellipse aux axes parallèles à ceux de la section.

    Le point de paramètre ``t`` est ``centre + (rx cos t, ry sin t)`` ; l'arc va de
    ``first`` à ``last`` (radians), dans le sens croissant si ``last > first``. Cercle si
    ``rx == ry``.
    """

    center: Point2
    rx: float
    ry: float
    first: float
    last: float

    def __post_init__(self) -> None:
        values = (*self.center, self.rx, self.ry, self.first, self.last)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("arc : valeurs non finies")
        if self.rx <= 0 or self.ry <= 0 or self.first == self.last:
            raise ValueError("arc : rayons > 0 et arc non nul attendus")

    def point(self, parameter: float) -> Point2:
        """Point de l'ellipse au paramètre ``parameter`` (radians)."""
        return (
            self.center[0] + self.rx * math.cos(parameter),
            self.center[1] + self.ry * math.sin(parameter),
        )

    @property
    def start(self) -> Point2:
        """Premier point de l'arc."""
        return self.point(self.first)

    @property
    def end(self) -> Point2:
        """Dernier point de l'arc."""
        return self.point(self.last)

    @property
    def middle(self) -> Point2:
        """Point au milieu de l'arc (pour construire l'arc en trois points)."""
        return self.point((self.first + self.last) / 2)


Element = Segment | Arc


def _extremes(arc: Arc) -> list[Point2]:
    """Points de l'arc aux multiples de 90° (extrema de l'ellipse), bouts non compris."""
    low, high = sorted((arc.first, arc.last))
    quarters = range(math.ceil(low / _QUARTER), math.floor(high / _QUARTER) + 1)
    return [arc.point(k * _QUARTER) for k in quarters]


def _sampled(arc: Arc) -> list[Point2]:
    step = (arc.last - arc.first) / _SAMPLES
    return [arc.point(arc.first + step * i) for i in range(_SAMPLES + 1)]


def _crosses(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Vrai si les segments ``ab`` et ``cd`` se coupent ou se touchent."""

    def side(p: Point2, q: Point2, r: Point2) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1, d2, d3, d4 = side(c, d, a), side(c, d, b), side(a, b, c), side(a, b, d)
    return d1 * d2 < -_CLOSED and d3 * d4 < -_CLOSED


@dataclass(frozen=True)
class Section:
    """Contour fermé, simple, de segments et d'arcs mis bout à bout (``ValueError`` sinon)."""

    elements: tuple[Element, ...]

    def __post_init__(self) -> None:
        if len(self.elements) < 2:
            raise ValueError("section : au moins deux éléments")
        for element, following in zip(
            self.elements, (*self.elements[1:], self.elements[0]), strict=True
        ):
            if math.dist(element.end, following.start) > _CLOSED:
                raise ValueError("section : contour non fermé")
        if self._self_intersects():
            raise ValueError("section : contour qui se recoupe")
        if self.area() <= 0:
            raise ValueError("section : aire nulle ou contour orienté à l'envers")

    def area(self) -> float:
        """Aire en mm² (théorème de Green, exacte pour les arcs) ; > 0 si le contour tourne dans
        le sens direct."""
        total = 0.0
        for element in self.elements:
            if isinstance(element, Segment):
                (x0, y0), (x1, y1) = element.start, element.end
                total += x0 * y1 - x1 * y0
            else:
                cx, cy = element.center
                t0, t1 = element.first, element.last
                total += (
                    cx * element.ry * (math.sin(t1) - math.sin(t0))
                    - cy * element.rx * (math.cos(t1) - math.cos(t0))
                    + element.rx * element.ry * (t1 - t0)
                )
        return total / 2

    def bounds(self) -> tuple[Point2, Point2]:
        """Coins ``(min, max)`` du plus petit rectangle aligné qui contient la section."""
        points: list[Point2] = []
        for element in self.elements:
            points += [element.start, element.end]
            if isinstance(element, Arc):
                points += _extremes(element)
        return (
            (min(p[0] for p in points), min(p[1] for p in points)),
            (max(p[0] for p in points), max(p[1] for p in points)),
        )

    def outline(self) -> list[Point2]:
        """Contour échantillonné en polyligne fermée (dernier point = premier non répété)."""
        points: list[Point2] = []
        for element in self.elements:
            points += _sampled(element)[:-1] if isinstance(element, Arc) else [element.start]
        return points

    def _self_intersects(self) -> bool:
        points = self.outline()
        count = len(points)
        edges = [(points[i], points[(i + 1) % count]) for i in range(count)]
        for i, (a, b) in enumerate(edges):
            for j in range(i + 2, count):
                if i == 0 and j == count - 1:
                    continue
                if _crosses(a, b, *edges[j]):
                    return True
        return False


@dataclass(frozen=True)
class Extrusion:
    """Section balayée en ligne droite : solide d'un profil d'arête (ADR 0029).

    Le point de la section ``(u, v)`` est à ``origin + u·u_axis + v·v_axis`` ; le balayage va de
    la section jusqu'à ``length`` mm selon ``direction``. Les trois vecteurs sont unitaires et
    orthogonaux (``ValueError`` sinon).
    """

    section: Section
    origin: Vec3
    u_axis: Vec3
    v_axis: Vec3
    direction: Vec3
    length: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.length) or self.length <= 0:
            raise ValueError("extrusion : longueur finie et > 0 attendue")
        axes = (self.u_axis, self.v_axis, self.direction)
        if any(abs(norm(axis) - 1.0) > 1e-9 for axis in axes):
            raise ValueError("extrusion : axes unitaires attendus")
        if any(abs(dot(a, b)) > 1e-9 for a, b in ((axes[0], axes[1]), (axes[0], axes[2]))):
            raise ValueError("extrusion : axes orthogonaux attendus")
        if abs(dot(cross(self.u_axis, self.v_axis), self.direction)) < 1.0 - 1e-9:
            raise ValueError("extrusion : axes orthogonaux attendus")

    def volume(self) -> float:
        """Volume en mm³."""
        return self.section.area() * self.length

    def point(self, u: float, v: float, along: float = 0.0) -> Vec3:
        """Point de coordonnées ``(u, v)`` dans la section située à ``along`` mm du départ."""
        return (
            self.origin
            + self.u_axis.scaled(u)
            + self.v_axis.scaled(v)
            + self.direction.scaled(along)
        )
