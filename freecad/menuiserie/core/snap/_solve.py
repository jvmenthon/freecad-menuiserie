# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contraintes des éléments suivants, étirement d'une cote et notices (J6a, § 4.3).

Tous les calculs se font dans le repère d'appui du premier élément : la pièce, orientée, occupe
sur chaque axe un intervalle ; chaque élément suivant impose la position d'une de ses faces
(``LO`` : face de plus petite coordonnée, ``HI`` : de plus grande) ou de la plus proche
(``NEAREST``). Deux faces opposées sur un même axe étirent la cote locale qui s'y trouve.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Final

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.geometry import (
    ANGLE_TOLERANCE,
    CONTACT_TOLERANCE_MM,
    Matrix3,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap._frames import (
    WORLD_FRAME,
    Anchor,
    Sides,
    anchor_of,
    local_axes,
    lowest_corner,
)
from freecad.menuiserie.core.snap._model import (
    EdgeTarget,
    FaceTarget,
    FreeTest,
    Orientation,
    SnapNotice,
    SnapNoticeKind,
    SnapResult,
    Target,
    VertexTarget,
)
from freecad.menuiserie.core.snap._vec import sub, unit

MAX_TARGETS: Final = 3
_LOCAL_THICKNESS: Final = 2


class Side(Enum):
    """Face de la pièce qui vient sur la valeur demandée."""

    LO = "lo"
    HI = "hi"
    NEAREST = "nearest"


@dataclass(frozen=True)
class AxisConstraint:
    """Une face de la pièce (``side``) vient à la coordonnée ``value`` de l'axe ``axis``."""

    axis: int
    side: Side
    value: float


def _axis_aligned(vector: Vec3) -> tuple[int, int] | None:
    """(indice d'axe, signe) si ``vector`` unitaire est un axe du repère à la tolérance près."""
    major = max(range(3), key=lambda i: abs(vector.component(i)))
    for index in range(3):
        expected = 1.0 if index == major else 0.0
        if abs(abs(vector.component(index)) - expected) > ANGLE_TOLERANCE:
            return None
    return major, 1 if vector.component(major) > 0 else -1


def _face_constraints(target: FaceTarget, to_frame: RigidTransform) -> tuple[AxisConstraint, ...]:
    aligned = _axis_aligned(to_frame.rotate(target.frame.z))
    if aligned is None:
        return ()
    axis, sign = aligned
    value = to_frame.apply(target.frame.origin).component(axis)
    return (AxisConstraint(axis, Side.LO if sign > 0 else Side.HI, value),)


def _edge_constraints(target: EdgeTarget, to_frame: RigidTransform) -> tuple[AxisConstraint, ...]:
    start = to_frame.apply(target.start)
    direction = unit(to_frame.rotate(sub(target.end, target.start)))
    return tuple(
        AxisConstraint(axis, Side.NEAREST, start.component(axis))
        for axis in (0, 1)
        if abs(direction.component(axis)) <= ANGLE_TOLERANCE
    )


def _vertex_constraints(
    target: VertexTarget, to_frame: RigidTransform
) -> tuple[AxisConstraint, ...]:
    point = to_frame.apply(target.point)
    return tuple(AxisConstraint(axis, Side.NEAREST, point.component(axis)) for axis in (0, 1))


# Strategy par type d'élément suivant : contraintes d'axe, vide si l'élément n'est pas d'équerre.
CONSTRAINT_BUILDERS: Final[
    Mapping[type, Callable[[Any, RigidTransform], tuple[AxisConstraint, ...]]]
] = MappingProxyType(
    {
        FaceTarget: _face_constraints,
        EdgeTarget: _edge_constraints,
        VertexTarget: _vertex_constraints,
    }
)


@dataclass
class _Solver:
    """Cumul des contraintes d'un accrochage, pour une orientation et des côtés donnés."""

    rotation: Matrix3
    dimensions: Dimensions
    sides: Sides
    stretch: bool
    local_of: tuple[int, int, int] = (0, 1, 2)
    entries: list[dict[Side, float]] = field(default_factory=lambda: [{}, {}, {}])
    locked: set[tuple[int, Side]] = field(default_factory=set)
    notices: list[SnapNotice] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.local_of = local_axes(self.rotation, self.dimensions)
        support = Side.LO if self.sides[2] > 0 else Side.HI
        self.entries[2][support] = 0.0
        self.locked.add((2, support))

    def sizes(self, dimensions: Dimensions) -> tuple[float, float, float]:
        """Étendues de la boîte tournée sur x, y, z."""
        local = (dimensions.length, dimensions.width, dimensions.thickness)
        return (
            abs_sum(self.rotation[0], local),
            abs_sum(self.rotation[1], local),
            abs_sum(self.rotation[2], local),
        )

    def _resolved(self, constraint: AxisConstraint) -> Side:
        if constraint.side is not Side.NEAREST:
            return constraint.side
        axis = constraint.axis
        size = self.sizes(self.dimensions)[axis]
        low = 0.0 if self.sides[axis] > 0 else -size
        near_low = abs(constraint.value - low) <= abs(constraint.value - (low + size))
        return Side.LO if near_low else Side.HI

    def _gap_notice(self, axis: int, gap: float) -> SnapNoticeKind | None:
        if self.local_of[axis] == _LOCAL_THICKNESS:
            current = self.sizes(self.dimensions)[axis]
            return (
                None
                if abs(gap - current) <= CONTACT_TOLERANCE_MM
                else (SnapNoticeKind.THICKNESS_GAP)
            )
        in_range = MIN_DIMENSION_MM <= gap <= MAX_DIMENSION_MM
        return None if in_range else SnapNoticeKind.GAP_OUT_OF_RANGE

    def add(self, constraint: AxisConstraint, name: str) -> bool:
        """Ajoute la contrainte ; faux (avec notice éventuelle) si l'élément est ignoré."""
        side = self._resolved(constraint)
        axis, entries = constraint.axis, self.entries[constraint.axis]
        replaced = side in entries
        if replaced and (axis, side) in self.locked:
            self.notices.append(SnapNotice(SnapNoticeKind.CONFLICT, name))
            return False
        other = Side.HI if side is Side.LO else Side.LO
        if other in entries:
            if not self.stretch:
                return False
            low, high = (constraint.value, entries[other])[:: 1 if side is Side.LO else -1]
            problem = self._gap_notice(axis, high - low)
            if problem is not None:
                self.notices.append(SnapNotice(problem, name))
                return False
        if replaced:
            self.notices.append(SnapNotice(SnapNoticeKind.CONFLICT, name))
        entries[side] = constraint.value
        return True

    def stretched(self) -> Dimensions:
        """Cotes après étirement : la cote locale d'un axe contraint des deux côtés."""
        values = [self.dimensions.length, self.dimensions.width, self.dimensions.thickness]
        for axis, entries in enumerate(self.entries):
            local = self.local_of[axis]
            if len(entries) == 2 and local != _LOCAL_THICKNESS:
                values[local] = entries[Side.HI] - entries[Side.LO]
        return Dimensions(values[0], values[1], values[2])

    def placement(self, dimensions: Dimensions) -> RigidTransform:
        """Transformation repère local de la pièce → repère d'appui."""
        sizes = self.sizes(dimensions)
        local = (dimensions.length, dimensions.width, dimensions.thickness)
        corner = lowest_corner(self.rotation, local)
        offset = [self._low(axis, sizes[axis]) - corner.component(axis) for axis in range(3)]
        return RigidTransform(self.rotation, Vec3.of(offset))

    def _low(self, axis: int, size: float) -> float:
        entries = self.entries[axis]
        if Side.LO in entries:
            return entries[Side.LO]
        if Side.HI in entries:
            return entries[Side.HI] - size
        return 0.0 if self.sides[axis] > 0 else -size


def abs_sum(row: Sequence[float], values: tuple[float, float, float]) -> float:
    """Somme des ``|coefficient| x valeur`` (étendue d'une boîte tournée sur un axe)."""
    return sum(abs(coefficient) * value for coefficient, value in zip(row, values, strict=True))


def _solve(
    anchor: Anchor,
    sides: Sides,
    request: tuple[Dimensions, Orientation, bool],
    followers: Sequence[Target],
) -> tuple[RigidTransform, Dimensions, list[str], list[SnapNotice]]:
    dimensions, orientation, stretch = request
    solver = _Solver(orientation.rotation(), dimensions, sides, stretch)
    to_frame = anchor.frame.to_transform().inverse()
    used: list[str] = []
    for target in followers:
        constraints = CONSTRAINT_BUILDERS[type(target)](target, to_frame)
        if not constraints:
            solver.notices.append(SnapNotice(SnapNoticeKind.NOT_SQUARE, target.name))
        elif [solver.add(c, target.name) for c in constraints].count(True):
            used.append(target.name)
    final = solver.stretched()
    placement = anchor.frame.to_transform().compose(solver.placement(final))
    return placement, final, used, solver.notices


def _best(
    anchor: Anchor,
    request: tuple[Dimensions, Orientation, bool],
    followers: Sequence[Target],
    is_free: FreeTest | None,
) -> tuple[RigidTransform, Dimensions, list[str], list[SnapNotice]]:
    """Premier côté (octant) libre selon ``is_free`` ; à défaut, le premier."""
    first = _solve(anchor, anchor.candidates[0], request, followers)
    if is_free is None or is_free(first[0], first[1]):
        return first
    for sides in anchor.candidates[1:]:
        outcome = _solve(anchor, sides, request, followers)
        if is_free(outcome[0], outcome[1]):
            return outcome
    return first


def snap(
    dimensions: Dimensions,
    orientation: Orientation,
    targets: Sequence[Target],
    *,
    stretch: bool = True,
    is_free: FreeTest | None = None,
) -> SnapResult:
    """Placement de la pièce contre les ``targets`` (trois au plus), sans exception.

    Sans cible : placement identité (boîte tournée dans l'octant positif). ``stretch`` : deux
    faces en vis-à-vis étirent la cote correspondante (jamais l'épaisseur). ``is_free`` départage
    les huit octants d'un sommet.
    """
    kept = tuple(targets[:MAX_TARGETS])
    notices: list[SnapNotice] = []
    if len(targets) > MAX_TARGETS:
        notices.append(SnapNotice(SnapNoticeKind.TOO_MANY, targets[MAX_TARGETS].name))
    anchor = anchor_of(kept[0]) if kept else Anchor(WORLD_FRAME, ((1, 1, 1),))
    request = (dimensions, orientation, stretch)
    placement, final, used, found = _best(anchor, request, kept[1:], is_free)
    names = (kept[0].name, *used) if kept else ()
    return SnapResult(placement, final, names, (*notices, *found))
