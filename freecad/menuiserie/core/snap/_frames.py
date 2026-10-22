# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère d'appui de chaque type de cible (Strategy + registre) et rotation de la pièce (J6a)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from freecad.menuiserie.core.geometry import (
    ANGLE_TOLERANCE,
    Matrix3,
    PlacedBlock,
    RigidTransform,
    Vec3,
    relative_axes,
)
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap._model import (
    EdgeTarget,
    FaceTarget,
    Frame,
    Target,
    Turn,
    VertexTarget,
)
from freecad.menuiserie.core.snap._vec import add, cross, dot, norm, scale, sub, unit

# Côté de l'origine où s'étend la pièce sur x, y et z : +1 vers l'axe, -1 à l'opposé.
Sides = tuple[int, int, int]
# Les huit octants d'un sommet, dans l'ordre figé de la spécification (S6).
OCTANTS: Final[tuple[Sides, ...]] = (
    (1, 1, 1),
    (-1, 1, 1),
    (1, -1, 1),
    (-1, -1, 1),
    (1, 1, -1),
    (-1, 1, -1),
    (1, -1, -1),
    (-1, -1, -1),
)
WORLD_FRAME: Final = Frame(Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1))
_ZERO: Final = Vec3(0.0, 0.0, 0.0)
_DOCUMENT_XY: Final = (Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0))


@dataclass(frozen=True)
class Anchor:
    """Repère d'appui d'une cible et côtés possibles de la pièce (plusieurs pour un sommet)."""

    frame: Frame
    candidates: tuple[Sides, ...]


def tangent_frame(point: Vec3, normal: Vec3) -> Frame:
    """Repère tangent en ``point`` à une surface de normale sortante ``normal`` (S4).

    ``x`` est la projection de l'axe X du document sur le plan tangent, ou celle de Y quand X est
    normal au plan.
    """
    z = unit(normal)
    for hint in _DOCUMENT_XY:
        projected = sub(hint, scale(z, dot(hint, z)))
        if norm(projected) > ANGLE_TOLERANCE:
            x = unit(projected)
            return Frame(point, x, cross(z, x), z)
    raise ValueError("tangent_frame : direction de référence nulle")  # pragma: no cover


def _face_anchor(target: FaceTarget) -> Anchor:
    return Anchor(target.frame, (OCTANTS[0],))


def _edge_anchor(target: EdgeTarget) -> Anchor:
    x = unit(sub(target.end, target.start))
    y = cross(target.support, x)
    side_y = 1 if dot(target.inward, y) >= 0 else -1
    return Anchor(Frame(target.start, x, y, target.support), ((1, side_y, 1),))


def _vertex_anchor(target: VertexTarget) -> Anchor:
    axes = target.axes
    return Anchor(Frame(target.point, axes.x, axes.y, axes.z), OCTANTS)


FRAME_BUILDERS: Final[Mapping[type, Callable[[Any], Anchor]]] = MappingProxyType(
    {FaceTarget: _face_anchor, EdgeTarget: _edge_anchor, VertexTarget: _vertex_anchor}
)


def anchor_of(target: Target) -> Anchor:
    """Repère d'appui de ``target`` (stratégie choisie par type)."""
    return FRAME_BUILDERS[type(target)](target)


def local_axes(rotation: Matrix3, dimensions: Dimensions) -> tuple[int, int, int]:
    """Pour chaque axe x, y, z du repère d'appui, l'axe local de la pièce (0 L, 1 l, 2 e) qui s'y
    aligne, d'après ``relative_axes`` de ``core.geometry``."""
    host = PlacedBlock(dimensions, RigidTransform.identity())
    guest = PlacedBlock(dimensions, RigidTransform(rotation, _ZERO))
    images = relative_axes(host, guest)
    by_frame_axis = {axis.index: local for local, axis in enumerate(images)}
    return (by_frame_axis[0], by_frame_axis[1], by_frame_axis[2])


def lowest_corner(rotation: Matrix3, sizes: tuple[float, float, float]) -> Vec3:
    """Coin de coordonnées minimales de la boîte [0, L] x [0, l] x [0, e] une fois tournée."""
    return Vec3.of([sum(min(0.0, row[j] * sizes[j]) for j in range(3)) for row in rotation])


def turned_in_place(
    placement: RigidTransform, dimensions: Dimensions, turn: Turn
) -> RigidTransform:
    """Placement après un quart de tour sur place (modification, sans accrochage).

    La rotation se fait autour de l'axe ``X``, ``Y`` ou ``Z`` du repère dans lequel ``placement``
    est exprimé (celui du document, ou de son conteneur) ; le centre de la boîte ne bouge pas.
    """
    center = Vec3(dimensions.length / 2, dimensions.width / 2, dimensions.thickness / 2)
    spun = RigidTransform(turn.matrix, _ZERO).compose(placement)
    shift = sub(placement.apply(center), spun.apply(center))
    return RigidTransform(spun.rotation, add(spun.translation, shift))
