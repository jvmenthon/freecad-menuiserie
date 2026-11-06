# SPDX-License-Identifier: LGPL-2.1-or-later
"""Onglet entre pièces tournées autour de l'arête du coin (ADR 0034, lot S-b). Module privé.

Dans le plan perpendiculaire à l'arête, les longues faces des deux pièces forment un
parallélogramme ; le plan d'onglet contient l'arête et les deux sommets extrêmes de ce
parallélogramme le long de a + b (a, b : sens où l'hôte et l'invitée s'éloignent du coin).
Chaque pièce perd le demi-espace situé du côté de l'autre. À 90° c'est le plan du cas d'équerre.
"""

from __future__ import annotations

import math
from typing import Final, NamedTuple

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron, clipped_box
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    CUT_OVERRUN_MM,
    MAX_OBLIQUE_DEG,
    Box,
    JointError,
    PlacedBlock,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._overlap import oblique_overlap
from freecad.menuiserie.core.vectors import dot, norm, unit

__all__ = ["ObliqueMiter", "oblique_miter"]

ANGLE_DECIMALS: Final = 2
_PARALLEL: Final = 1e-6
_IDENTITY: Final = RigidTransform.identity()

MITER_COMPOUND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Onglet en biais : les deux pièces doivent pivoter autour de l'arête du coin et y être à "
    "fleur, avec des longueurs et des largeurs différentes.",
)
MITER_TOO_OBLIQUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Onglet : l'angle entre les pièces s'écarte de {angle}° de l'équerre ; {maximum}° au plus.",
)


class ObliqueMiter(NamedTuple):
    """Angles de coupe (degrés, au centième) et enlèvements (repère de chaque pièce)."""

    host_angle: float
    guest_angle: float
    host_cut: Polyhedron
    guest_cut: Polyhedron


def _fixed_axis(transform: RigidTransform) -> int:
    """Axe de l'hôte autour duquel tourne l'invitée (colonne de la rotation sur un axe) ;
    :class:`JointError` ``MITER_COMPOUND`` s'il n'y en a pas."""
    for index in range(3):
        unit_axis = Vec3(0.0, 0.0, 0.0).with_component(index, 1.0)
        turned = transform.inverse().rotate(unit_axis)
        if any(abs(abs(turned.component(j)) - 1.0) < _PARALLEL for j in range(3)):
            return index
    raise JointError(MITER_COMPOUND, {})


def _long_axis(box: Box, axes: tuple[int, int]) -> int:
    first, second = axes
    return first if box.size(first) >= box.size(second) else second


def _line_crossing(
    point_a: Vec3, direction_a: Vec3, point_b: Vec3, direction_b: Vec3, plane: tuple[int, int]
) -> Vec3:
    """Croisement de deux droites du plan (axes ``plane``), à la cote 0 sur le troisième axe."""
    i, j = plane
    determinant = direction_a.component(i) * direction_b.component(j) - direction_a.component(
        j
    ) * direction_b.component(i)
    if abs(determinant) < _PARALLEL:
        raise JointError(MITER_COMPOUND, {})
    delta_i = point_b.component(i) - point_a.component(i)
    delta_j = point_b.component(j) - point_a.component(j)
    t = (delta_i * direction_b.component(j) - delta_j * direction_b.component(i)) / determinant
    return point_a + direction_a.scaled(t)


def _grown(box: Box) -> Box:
    return Box.from_ranges(
        [(box.lo(i) - CUT_OVERRUN_MM, box.hi(i) + CUT_OVERRUN_MM) for i in range(3)]
    )


def oblique_miter(host: PlacedBlock, guest: PlacedBlock) -> ObliqueMiter:
    """Onglet de deux pièces qui se chevauchent et pivotent autour de l'arête du coin."""
    overlap = oblique_overlap(host, guest)
    to_host = overlap.to_host
    edge = _fixed_axis(to_host)
    plane = tuple(i for i in range(3) if i != edge)
    host_box, guest_box = overlap.host_box, overlap.guest_box
    guest_edge = next(
        j
        for j in range(3)
        if abs(
            abs(to_host.rotate(Vec3(0.0, 0.0, 0.0).with_component(j, 1.0)).component(edge)) - 1.0
        )
        < _PARALLEL
    )
    along = [
        to_host.apply(Vec3(0.0, 0.0, 0.0).with_component(guest_edge, v)).component(edge)
        for v in (guest_box.lo(guest_edge), guest_box.hi(guest_edge))
    ]
    if (
        abs(min(along) - host_box.lo(edge)) > CONTACT_TOLERANCE_MM
        or abs(max(along) - host_box.hi(edge)) > CONTACT_TOLERANCE_MM
    ):
        raise JointError(MITER_COMPOUND, {})
    host_long = _long_axis(host_box, (plane[0], plane[1]))
    guest_axes = tuple(j for j in range(3) if j != guest_edge)
    guest_long = _long_axis(guest_box, (guest_axes[0], guest_axes[1]))
    e_host = Vec3(0.0, 0.0, 0.0).with_component(host_long, 1.0)
    e_guest = to_host.rotate(Vec3(0.0, 0.0, 0.0).with_component(guest_long, 1.0))
    n_host = Vec3(0.0, 0.0, 0.0).with_component(next(i for i in plane if i != host_long), 1.0)
    n_guest = to_host.rotate(
        Vec3(0.0, 0.0, 0.0).with_component(next(j for j in guest_axes if j != guest_long), 1.0)
    )
    deviation = abs(90.0 - math.degrees(math.acos(min(1.0, abs(dot(e_host, e_guest))))))
    if deviation > MAX_OBLIQUE_DEG:
        values = {"angle": f"{deviation:.1f}", "maximum": f"{MAX_OBLIQUE_DEG:g}"}
        raise JointError(MITER_TOO_OBLIQUE, values)
    centre_host = Vec3(*(host_box.center(i) for i in range(3)))
    centre_guest = to_host.apply(Vec3(*(guest_box.center(i) for i in range(3))))
    away_host = e_host.scaled(-1.0 if dot(centre_guest - centre_host, e_host) > 0 else 1.0)
    away_guest = e_guest.scaled(-1.0 if dot(centre_host - centre_guest, e_guest) > 0 else 1.0)
    # Longues faces : droites parallèles à l'axe long, sur les deux bords de l'autre axe.
    host_n_index = next(i for i in plane if i != host_long)
    guest_n_index = next(j for j in guest_axes if j != guest_long)
    host_lines = [
        centre_host.with_component(host_n_index, bound)
        for bound in (host_box.lo(host_n_index), host_box.hi(host_n_index))
    ]
    guest_lines = [
        to_host.apply(
            Vec3(*(guest_box.center(i) for i in range(3))).with_component(guest_n_index, bound)
        )
        for bound in (guest_box.lo(guest_n_index), guest_box.hi(guest_n_index))
    ]
    corners = [
        _line_crossing(a, e_host, b, e_guest, (plane[0], plane[1]))
        for a in host_lines
        for b in guest_lines
    ]
    run = away_host + away_guest
    outer = min(corners, key=lambda c: dot(c, run))
    inner = max(corners, key=lambda c: dot(c, run))
    diagonal = unit(inner - outer)
    normal = Vec3(0.0, 0.0, 0.0).with_component(plane[0], -diagonal.component(plane[1]))
    normal = normal.with_component(plane[1], diagonal.component(plane[0]))
    toward_host = normal if dot(centre_host - outer, normal) > 0 else normal.scaled(-1.0)
    if norm(toward_host) < _PARALLEL:
        raise JointError(MITER_COMPOUND, {})
    host_plane = Plane(outer, toward_host)
    guest_plane = Plane(outer, toward_host.scaled(-1.0))
    host_cut = clipped_box(_grown(host_box), _IDENTITY, (host_plane,))
    guest_cut = clipped_box(_grown(guest_box), _IDENTITY, (guest_plane.moved(to_host.inverse()),))
    if host_cut is None or guest_cut is None:
        raise JointError(MITER_COMPOUND, {})
    host_angle = math.degrees(math.acos(min(1.0, abs(dot(diagonal, n_host)))))
    guest_angle = math.degrees(math.acos(min(1.0, abs(dot(diagonal, n_guest)))))
    return ObliqueMiter(
        round(host_angle, ANGLE_DECIMALS), round(guest_angle, ANGLE_DECIMALS), host_cut, guest_cut
    )
