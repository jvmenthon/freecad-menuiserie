# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance entre deux éléments (face, arête, sommet) de deux pièces (DI-a, ADR 0022).

Les neuf paires de cibles de ``core/snap`` sont ramenées à quatre calculs : plan-plan,
plan-point, droite-droite et point-point (une arête parallèle à un plan est représentée par un
de ses points ; une droite et un point se mesurent perpendiculairement à la droite). Un registre
associe à chaque paire de primitives son calcul (Strategy) ; ajouter une variante n'ajoute pas
de ``if``. Convention : ``measure(fixed, moving)`` — le premier élément est la référence, le
second celui de la pièce qui bouge.

Les arêtes (:class:`EdgeTarget`) sont droites par construction : une arête courbe n'a pas de
cible (``features/`` ne produit pas d'``EdgeTarget`` pour elle) et ne parvient donc pas jusqu'ici.
Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.snap import EdgeTarget, FaceTarget, Frame, Target, VertexTarget
from freecad.menuiserie.core.snap._vec import cross, dot, is_finite, norm, scale, sub, unit

NOT_PARALLEL: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les éléments ne sont pas parallèles : la distance n'est pas définie."
)
INVALID_VALUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La distance doit être un nombre fini, positif ou nul (reçu : {value} mm)."
)
INVALID_AXIS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'axe de mesure doit être un vecteur fini et non nul."
)

_ZERO_MM: Final = 1e-9  # en deçà, la distance est nulle : le sens vient de l'élément mobile
_X: Final = Vec3(1.0, 0.0, 0.0)


class DistanceError(TemplatedError):
    """Distance non définie ; message = gabarit français (``QT_TRANSLATE_NOOP``) rempli."""


@dataclass(frozen=True)
class Gap:
    """Distance ``value`` (mm, ≥ 0) et ``direction`` (vecteur unitaire global) dans laquelle la
    pièce mobile s'éloigne de l'élément de référence."""

    value: float
    direction: Vec3

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or self.value < 0:
            raise ValueError("Gap.value : nombre fini positif ou nul attendu")
        if not is_finite(self.direction) or abs(norm(self.direction) - 1.0) > ANGLE_TOLERANCE:
            raise ValueError("Gap.direction : vecteur unitaire attendu")


class FrameAxis(Enum):
    """Axe X, Y ou Z d'un repère (celui d'un ensemble, du conteneur)."""

    X = "X"
    Y = "Y"
    Z = "Z"

    def of(self, frame: Frame) -> Vec3:
        """Vecteur unitaire de cet axe dans ``frame``."""
        return {FrameAxis.X: frame.x, FrameAxis.Y: frame.y, FrameAxis.Z: frame.z}[self]


@dataclass(frozen=True)
class _Plane:
    point: Vec3
    normal: Vec3


@dataclass(frozen=True)
class _Line:
    point: Vec3
    direction: Vec3


@dataclass(frozen=True)
class _Point:
    point: Vec3


_Primitive = _Plane | _Line | _Point
# Calcul d'une paire (référence, mobile, sens de repli si distance nulle, axe imposé).
_Strategy = Callable[[_Primitive, _Primitive, Vec3, Vec3 | None], Gap]


def _reduce(target: Target) -> tuple[_Primitive, Vec3 | None]:
    """Primitive de la cible et sens de repli propre à l'élément (``None`` pour un sommet) :
    normale sortante d'une face, face d'appui d'une arête."""
    if isinstance(target, FaceTarget):
        if not target.planar:
            raise DistanceError(NOT_PARALLEL, {})
        return _Plane(target.frame.origin, target.frame.z), target.frame.z
    if isinstance(target, EdgeTarget):
        return _Line(target.start, unit(sub(target.end, target.start))), target.support
    return _Point(target.point), None


def _is_parallel(a: Vec3, b: Vec3) -> bool:
    return norm(cross(a, b)) <= ANGLE_TOLERANCE


def _along(axis: Vec3, delta: Vec3, fallback: Vec3) -> Gap:
    """Distance de ``delta`` mesurée le long de l'axe unitaire ``axis`` (signée → sens)."""
    offset = dot(delta, axis)
    if abs(offset) <= _ZERO_MM:
        return Gap(0.0, fallback)
    return Gap(abs(offset), axis if offset > 0 else scale(axis, -1.0))


def _across(line: Vec3, delta: Vec3, fallback: Vec3) -> Gap:
    """Distance de ``delta`` perpendiculairement à la droite unitaire ``line``."""
    transverse = sub(delta, scale(line, dot(delta, line)))
    length = norm(transverse)
    if length <= _ZERO_MM:
        return Gap(0.0, fallback)
    return Gap(length, scale(transverse, 1.0 / length))


def _plane_plane(fixed: _Primitive, moving: _Primitive, fallback: Vec3, _axis: Vec3 | None) -> Gap:
    if not (isinstance(fixed, _Plane) and isinstance(moving, _Plane)):
        raise TypeError("plan-plan attendu")
    if not _is_parallel(fixed.normal, moving.normal):
        raise DistanceError(NOT_PARALLEL, {})
    return _along(fixed.normal, sub(moving.point, fixed.point), fallback)


def _plane_other(fixed: _Primitive, moving: _Primitive, fallback: Vec3, _axis: Vec3 | None) -> Gap:
    """Plan (référence ou mobile) contre un point ou une arête parallèle à ce plan."""
    plane, other = (fixed, moving) if isinstance(fixed, _Plane) else (moving, fixed)
    if not isinstance(plane, _Plane):
        raise TypeError("plan attendu")
    if isinstance(other, _Line) and abs(dot(plane.normal, other.direction)) > ANGLE_TOLERANCE:
        raise DistanceError(NOT_PARALLEL, {})
    return _along(plane.normal, sub(_point(moving), _point(fixed)), fallback)


def _point(primitive: _Primitive) -> Vec3:
    return primitive.point


def _line_line(fixed: _Primitive, moving: _Primitive, fallback: Vec3, _axis: Vec3 | None) -> Gap:
    if not (isinstance(fixed, _Line) and isinstance(moving, _Line)):
        raise TypeError("droite-droite attendu")
    if not _is_parallel(fixed.direction, moving.direction):
        raise DistanceError(NOT_PARALLEL, {})
    return _across(fixed.direction, sub(moving.point, fixed.point), fallback)


def _line_point(fixed: _Primitive, moving: _Primitive, fallback: Vec3, _axis: Vec3 | None) -> Gap:
    line = fixed if isinstance(fixed, _Line) else moving
    if not isinstance(line, _Line):
        raise TypeError("droite attendue")
    return _across(line.direction, sub(_point(moving), _point(fixed)), fallback)


def _point_point(fixed: _Primitive, moving: _Primitive, fallback: Vec3, axis: Vec3 | None) -> Gap:
    delta = sub(_point(moving), _point(fixed))
    if axis is not None:
        return _along(axis, delta, axis)
    length = norm(delta)
    if length <= _ZERO_MM:
        return Gap(0.0, fallback)
    return Gap(length, scale(delta, 1.0 / length))


# Registre : (primitive de référence, primitive mobile) → calcul. Neuf paires, quatre calculs.
_STRATEGIES: Final[Mapping[tuple[type, type], _Strategy]] = MappingProxyType(
    {
        (_Plane, _Plane): _plane_plane,
        (_Plane, _Line): _plane_other,
        (_Line, _Plane): _plane_other,
        (_Plane, _Point): _plane_other,
        (_Point, _Plane): _plane_other,
        (_Line, _Line): _line_line,
        (_Line, _Point): _line_point,
        (_Point, _Line): _line_point,
        (_Point, _Point): _point_point,
    }
)


def _unit_axis(axis: Vec3 | None) -> Vec3 | None:
    if axis is None:
        return None
    if not is_finite(axis) or norm(axis) <= ANGLE_TOLERANCE:
        raise DistanceError(INVALID_AXIS, {})
    return unit(axis)


def _fallback(own: Vec3 | None, reference: Vec3 | None, moving: Target) -> Vec3:
    """Sens quand la distance est nulle : la pièce mobile s'écarte de la référence, donc à
    l'opposé de la normale sortante (ou de l'appui) de l'élément mobile, qui regarde la
    référence au contact ; pour un sommet, la normale sortante de la référence ; sommet contre
    sommet : axe X du repère du sommet."""
    if own is not None:
        return scale(own, -1.0)
    if reference is not None:
        return reference
    return moving.axes.x if isinstance(moving, VertexTarget) else _X


def measure(fixed: Target, moving: Target, axis: Vec3 | None = None) -> Gap:
    """Distance de ``moving`` (élément de la pièce qui bouge) à ``fixed`` (référence), et sens
    dans lequel ``moving`` s'éloigne. Les neuf paires de faces, arêtes et sommets sont
    traitées (D1) ; éléments non parallèles ou face non plane : :class:`DistanceError` (D2).
    Distance nulle : la pièce mobile s'écarte de la référence, à l'opposé de la normale sortante
    de l'élément mobile (D3).
    ``axis`` (axe du conteneur, global) ne sert que pour sommet-sommet (D4) : la distance et le
    sens sont alors ceux de la projection sur cet axe seul."""
    unit_axis = _unit_axis(axis)
    fixed_primitive, fixed_side = _reduce(fixed)
    moving_primitive, moving_side = _reduce(moving)
    strategy = _STRATEGIES[(type(fixed_primitive), type(moving_primitive))]
    fallback = _fallback(moving_side, fixed_side, moving)
    return strategy(fixed_primitive, moving_primitive, fallback, unit_axis)


def moved_by(gap: Gap, value: float) -> Vec3:
    """Translation de la pièce mobile qui amène la distance à ``value`` (≥ 0) le long de
    ``gap.direction`` : la pièce reste de son côté, même si la distance actuelle est nulle (D3)."""
    if not math.isfinite(value) or value < 0:
        raise DistanceError(INVALID_VALUE, {"value": f"{value:g}"})
    return scale(gap.direction, value - gap.value)


def ensemble_axis(gap: Gap, frame: Frame) -> FrameAxis | None:
    """Axe (X, Y ou Z) du repère ``frame`` de l'ensemble auquel ``gap.direction`` est parallèle,
    ou ``None`` : la distance ne peut alors pas être gardée (D5)."""
    for axis in FrameAxis:
        if _is_parallel(gap.direction, axis.of(frame)):
            return axis
    return None
