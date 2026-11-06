# SPDX-License-Identifier: LGPL-2.1-or-later
"""Polyèdre convexe : boîte posée dans un repère quelconque, coupée par des demi-espaces
(ADR 0024, AB-a).

Les assemblages entre pièces en biais ne se ramènent pas à des boîtes alignées : le coin retiré
ou ajouté contre un plan d'épaulement oblique, le tenon incliné et la mortaise sont des solides
convexes. ``core/`` en calcule les sommets, les faces et le volume en Python pur, ce qui garde
les contrôles de matière et les tests hors de FreeCAD. ``features/`` en tire le solide ``Part``.

Un polyèdre est l'intersection de demi-espaces : les six faces de la boîte, plus les plans de
coupe. Les sommets sont les intersections de trois plans qui respectent tous les autres ; les
faces regroupent les sommets d'un même plan. Aucune dépendance externe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from itertools import combinations, pairwise
from typing import Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Box,
    RigidTransform,
    Solid,
    Vec3,
)
from freecad.menuiserie.core.vectors import cross, dot, norm, unit

__all__ = ["PlanSolid", "Plane", "Polyhedron", "SlantedCylinder", "clipped_box"]

_MERGE_MM: Final = 1e-6  # sommets plus proches : un seul ; plan : « sur » ce plan
_PARALLEL: Final = 1e-9  # déterminant sous lequel trois plans n'ont pas de point commun unique
MAX_PLANES: Final = 6  # plans de coupe d'un polyèdre (§ 4.9 de la spécification)


@dataclass(frozen=True)
class SlantedCylinder:
    """Cylindre d'axe quelconque (tourillon entre pièces en biais, ADR 0034) : base au centre
    d'une face, direction unitaire de l'axe, rayon et hauteur > 0."""

    base: Vec3
    direction: Vec3
    radius: float
    height: float

    def __post_init__(self) -> None:
        values = (*(c for c in (self.base.x, self.base.y, self.base.z)), self.radius, self.height)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("cylindre : valeurs finies attendues")
        if self.radius <= 0 or self.height <= 0 or abs(norm(self.direction) - 1.0) > 1e-6:
            raise ValueError("cylindre : rayon, hauteur > 0 et direction unitaire attendus")

    def moved(self, transform: RigidTransform) -> SlantedCylinder:
        """Même cylindre exprimé dans un autre repère (toute rotation)."""
        return SlantedCylinder(
            transform.apply(self.base), transform.rotate(self.direction), self.radius, self.height
        )


@dataclass(frozen=True)
class Plane:
    """Demi-espace gardé : les points ``p`` tels que ``(p - point) · normal <= 0``.

    La normale (non nulle, finie) pointe vers la matière **retirée**.
    """

    point: Vec3
    normal: Vec3

    def __post_init__(self) -> None:
        values = (
            *(c for c in (self.point.x, self.point.y, self.point.z)),
            self.normal.x,
            self.normal.y,
            self.normal.z,
        )
        if not all(math.isfinite(value) for value in values) or norm(self.normal) < _PARALLEL:
            raise ValueError("plan : point fini et normale non nulle attendus")

    def distance(self, point: Vec3) -> float:
        """Distance signée de ``point`` au plan : positive du côté retiré."""
        return dot(point - self.point, unit(self.normal))

    def moved(self, transform: RigidTransform) -> Plane:
        """Même plan exprimé dans un autre repère."""
        return Plane(transform.apply(self.point), transform.rotate(self.normal))


@dataclass(frozen=True)
class _HalfSpace:
    """``normal · x <= offset``, normale unitaire."""

    normal: Vec3
    offset: float

    @classmethod
    def of(cls, plane: Plane) -> _HalfSpace:
        normal = unit(plane.normal)
        return cls(normal, dot(normal, plane.point))

    def holds(self, point: Vec3, tolerance: float = _MERGE_MM) -> bool:
        return dot(self.normal, point) <= self.offset + tolerance

    def contains_on_boundary(self, point: Vec3) -> bool:
        return abs(dot(self.normal, point) - self.offset) <= _MERGE_MM


def _solve(a: _HalfSpace, b: _HalfSpace, c: _HalfSpace) -> Vec3 | None:
    """Point commun aux trois plans, ``None`` si le système est (presque) singulier."""
    n1, n2, n3 = a.normal, b.normal, c.normal
    denominator = dot(n1, cross(n2, n3))
    if abs(denominator) < _PARALLEL:
        return None
    point = (
        cross(n2, n3).scaled(a.offset)
        + cross(n3, n1).scaled(b.offset)
        + cross(n1, n2).scaled(c.offset)
    )
    return point.scaled(1.0 / denominator)


def _unique(spaces: list[_HalfSpace]) -> list[_HalfSpace]:
    kept: list[_HalfSpace] = []
    for space in spaces:
        same = (
            norm(space.normal - other.normal) < _MERGE_MM
            and abs(space.offset - other.offset) < _MERGE_MM
            for other in kept
        )
        if not any(same):
            kept.append(space)
    return kept


def _merged(points: list[Vec3]) -> list[Vec3]:
    kept: list[Vec3] = []
    for point in points:
        if all(norm(point - other) > _MERGE_MM for other in kept):
            kept.append(point)
    return kept


def _ordered(points: list[Vec3], normal: Vec3) -> tuple[Vec3, ...]:
    """Sommets d'une face rangés autour de son centre (sens trigonométrique vu de la normale)."""
    centre = Vec3(
        sum(p.x for p in points) / len(points),
        sum(p.y for p in points) / len(points),
        sum(p.z for p in points) / len(points),
    )
    helper = Vec3(1.0, 0.0, 0.0) if abs(normal.x) < 0.9 else Vec3(0.0, 1.0, 0.0)
    first = unit(cross(normal, helper))
    second = cross(normal, first)

    def angle(point: Vec3) -> float:
        offset = point - centre
        return math.atan2(dot(offset, second), dot(offset, first))

    return tuple(sorted(points, key=angle))


@dataclass(frozen=True)
class Polyhedron:
    """Boîte ``box`` (aplatie permise) posée dans le repère ``frame``, coupée par ``planes``.

    Les plans sont exprimés dans le repère **où vit** le polyèdre (celui dans lequel ``frame``
    place la boîte), pas dans le repère de la boîte.
    """

    box: Box
    frame: RigidTransform
    planes: tuple[Plane, ...] = ()

    def __post_init__(self) -> None:
        if len(self.planes) > MAX_PLANES:
            raise ValueError("trop de plans de coupe")

    @cached_property
    def _spaces(self) -> list[_HalfSpace]:
        spaces: list[_HalfSpace] = []
        for index in range(3):
            for sign, bound in ((-1.0, self.box.lo(index)), (1.0, self.box.hi(index))):
                axis = [0.0, 0.0, 0.0]
                axis[index] = sign
                point = [0.0, 0.0, 0.0]
                point[index] = bound
                normal = self.frame.rotate(Vec3.of(axis))
                spaces.append(_HalfSpace.of(Plane(self.frame.apply(Vec3.of(point)), normal)))
        spaces.extend(_HalfSpace.of(plane) for plane in self.planes)
        return _unique(spaces)

    @cached_property
    def _vertices(self) -> tuple[Vec3, ...]:
        spaces = self._spaces
        found: list[Vec3] = []
        for a, b, c in combinations(spaces, 3):
            point = _solve(a, b, c)
            if point is not None and all(space.holds(point) for space in spaces):
                found.append(point)
        return tuple(_merged(found))

    def vertices(self) -> tuple[Vec3, ...]:
        """Sommets du polyèdre (vide si la coupe ne laisse rien)."""
        return self._vertices

    def faces(self) -> tuple[tuple[Vec3, ...], ...]:
        """Faces : sommets rangés autour de chaque face (au moins trois)."""
        faces = []
        for space in self._spaces:
            points = [v for v in self._vertices if space.contains_on_boundary(v)]
            if len(points) >= 3:
                faces.append(_ordered(points, space.normal))
        return tuple(faces)

    def volume(self) -> float:
        """Volume en mm³ (0 pour un polyèdre vide ou plat)."""
        vertices = self._vertices
        if len(vertices) < 4:
            return 0.0
        count = len(vertices)
        centre = Vec3(
            sum(v.x for v in vertices) / count,
            sum(v.y for v in vertices) / count,
            sum(v.z for v in vertices) / count,
        )
        total = 0.0
        for face in self.faces():
            origin = face[0] - centre
            for second, third in pairwise(face[1:]):
                total += abs(dot(origin, cross(second - centre, third - centre))) / 6.0
        return total

    def thickness(self) -> float:
        """Plus petite épaisseur du polyèdre mesurée perpendiculairement à une de ses faces."""
        if len(self._vertices) < 4:
            return 0.0
        widths = []
        for space in self._spaces:
            if sum(1 for v in self._vertices if space.contains_on_boundary(v)) >= 3:
                values = [dot(space.normal, v) for v in self._vertices]
                widths.append(max(values) - min(values))
        return min(widths) if widths else 0.0

    def moved(self, transform: RigidTransform) -> Polyhedron:
        """Même polyèdre exprimé dans un autre repère (toute rotation)."""
        planes = tuple(plane.moved(transform) for plane in self.planes)
        return Polyhedron(self.box, transform.compose(self.frame), planes)

    def bounds(self) -> Box:
        """Boîte alignée sur les axes du repère courant qui contient le polyèdre."""
        ranges = [
            (
                min(v.component(i) for v in self._vertices),
                max(v.component(i) for v in self._vertices),
            )
            for i in range(3)
        ]
        return Box.from_ranges(ranges)

    def contains(self, point: Vec3, tolerance: float = CONTACT_TOLERANCE_MM) -> bool:
        """Vrai si ``point`` est dans le polyèdre, à ``tolerance`` près."""
        return all(space.holds(point, tolerance) for space in self._spaces)


def clipped_box(box: Box, frame: RigidTransform, planes: tuple[Plane, ...]) -> Polyhedron | None:
    """Boîte ``box`` posée dans ``frame`` et coupée par ``planes`` ; ``None`` s'il ne reste rien
    ou une lame plus mince que :data:`~.geometry.CONTACT_TOLERANCE_MM` (rien à usiner)."""
    polyhedron = Polyhedron(box, frame, planes)
    return None if polyhedron.thickness() < CONTACT_TOLERANCE_MM else polyhedron


PlanSolid = Solid | Polyhedron | SlantedCylinder
"""Solide d'un plan d'usinage : forme d'équerre (boîte, cylindre, prisme) ou polyèdre en biais."""
