# SPDX-License-Identifier: LGPL-2.1-or-later
"""Queue d'aronde entre pièces en biais (ADR 0034, lot S-c). Module privé.

Chaque queue (ou chaque griffe, quand les queues sont sur l'hôte) est une boîte du repère de
l'invitée coupée par quatre plans : le plan d'épaulement (face de l'hôte vue par l'invitée), la
face opposée de l'hôte et deux flancs inclinés de l'angle choisi. Le logement de l'hôte est le même
solide prolongé de ``CUT_OVERRUN_MM`` hors de la matière. Les flancs sont repérés sur le plan de la
face opposée, à l'axe de la face de l'invitée ; leur pente est mesurée par rapport à son axe.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron, clipped_box
from freecad.menuiserie.core.geometry import (
    CUT_OVERRUN_MM,
    Box,
    JointError,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import Bevel, JointPlan
from freecad.menuiserie.core.joints._oblique_frame import ObliqueFrame
from freecad.menuiserie.core.vectors import dot, unit

if TYPE_CHECKING:
    from freecad.menuiserie.core.joints.dovetail import DovetailValues

__all__ = ["oblique_dovetail_plan"]

_IDENTITY: Final = RigidTransform.identity()
_EMPTY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Queue d'aronde en biais : une queue ne laisse aucune matière."
)
_BEVEL_MIN_DEG: Final = 1e-3
_SLACK_MM: Final = 1.0


class _Layout:
    """Repères de la queue : axes de l'invitée, plans de l'hôte et niveaux de référence."""

    def __init__(self, frame: ObliqueFrame, outer_side: int, values: DovetailValues) -> None:
        self.frame, self.outer_side, self.values = frame, outer_side, values
        contact = frame.contact
        self.width_axis, self.normal_axis, self.sign = frame.width_axis, frame.normal, frame.sign
        self.thickness = frame.contact_thickness
        face = frame.face
        self.origin = face.lo(self.width_axis)
        self.centre = Vec3(face.center(0), face.center(1), face.center(2))
        self.shoulder, self.opposite = contact.shoulder, contact.opposite
        self.level = self._cross(self.opposite).component(self.normal_axis)  # n_O
        self.slope = math.tan(math.radians(values.angle))
        # Étendue de l'hôte selon la normale de l'invitée, pour dimensionner la boîte.
        to_guest = contact.transform.inverse()
        host = frame.host_box
        reaches = [
            to_guest.apply(Vec3(x, y, z)).component(self.normal_axis)
            for x in (host.lo(0), host.hi(0))
            for y in (host.lo(1), host.hi(1))
            for z in (host.lo(2), host.hi(2))
        ]
        self.low_n, self.high_n = min(reaches) - 10.0, max(reaches) + 10.0
        self.reach = self.high_n - self.low_n

    def _cross(self, plane: Plane) -> Vec3:
        """Point où l'axe de la face de l'invitée traverse ``plane``."""
        axis = self.frame.fibre
        travel = dot(plane.point - self.centre, plane.normal) / dot(axis, plane.normal)
        return self.centre + axis.scaled(travel)

    def vec(self, across: float, along: float, level: float) -> Vec3:
        """Point (largeur du contact, normale de l'invitée, épaisseur)."""
        point = Vec3(0.0, 0.0, level).with_component(self.width_axis, across)
        return point.with_component(self.normal_axis, along)

    def push(self, plane: Plane, overrun: float) -> Plane:
        """``plane`` repoussé de ``overrun`` hors de la matière de l'hôte."""
        return Plane(plane.point + unit(plane.normal).scaled(overrun), plane.normal)

    def planes(self, overrun: float) -> tuple[Plane, Plane]:
        """Plan d'épaulement et face opposée, repoussés de ``overrun``."""
        return self.push(self.shoulder, overrun), self.push(self.opposite, overrun)

    def solid(self, box: Box, planes: tuple[Plane, ...]) -> Polyhedron:
        solid = clipped_box(box, _IDENTITY, planes)
        if solid is None:
            raise JointError(_EMPTY, {})
        return solid


def _tail(layout: _Layout, span: tuple[float, float], overrun: float) -> Polyhedron:
    first, last = span
    slope, sign = layout.slope, layout.sign
    left = Plane(
        layout.vec(layout.origin + first, layout.level, 0.0),
        layout.vec(-1.0, -sign * slope, 0.0),
    )
    right = Plane(
        layout.vec(layout.origin + last, layout.level, 0.0),
        layout.vec(1.0, -sign * slope, 0.0),
    )
    slack = slope * (layout.reach + 2 * overrun) + _SLACK_MM
    outer = layout.outer_side > 0
    low = 0.0 if outer else -overrun
    high = layout.thickness + (overrun if outer else 0.0)
    ranges = [(0.0, 0.0)] * 3
    ranges[layout.width_axis] = (layout.origin + first - slack, layout.origin + last + slack)
    ranges[layout.normal_axis] = (layout.low_n, layout.high_n)
    ranges[2] = (low, high)
    return layout.solid(Box.from_ranges(ranges), (*layout.planes(overrun), left, right))


def _pin(layout: _Layout, span: tuple[float, float], overrun: float, width: float) -> Polyhedron:
    first, last = span
    flank = layout.slope
    thickness = layout.thickness
    inward = 1.0 if layout.outer_side < 0 else -1.0  # de la face extérieure vers l'intérieure
    outer = 0.0 if layout.outer_side < 0 else thickness
    inner = thickness if layout.outer_side < 0 else 0.0
    edge_first, edge_last = first == 0.0, last == width
    reach = thickness * flank
    planes = list(layout.planes(overrun))
    if not edge_first:
        planes.append(
            Plane(
                layout.vec(layout.origin + first, layout.level, outer),
                layout.vec(-1.0, 0.0, -flank * inward),
            )
        )
    if not edge_last:
        planes.append(
            Plane(
                layout.vec(layout.origin + last, layout.level, outer),
                layout.vec(1.0, 0.0, -flank * inward),
            )
        )
    ranges = [(0.0, 0.0)] * 3
    left = layout.origin + first - (0.0 if edge_first else reach + _SLACK_MM)
    right = layout.origin + last + (0.0 if edge_last else reach + _SLACK_MM)
    ranges[layout.width_axis] = (left, right)
    ranges[layout.normal_axis] = (layout.low_n, layout.high_n)
    z_ends = (outer - inward * overrun, inner)
    ranges[2] = (min(z_ends), max(z_ends))
    return layout.solid(Box.from_ranges(ranges), tuple(planes))


def oblique_dovetail_plan(
    frame: ObliqueFrame,
    outer_side: int,
    values: DovetailValues,
    pin_spans: tuple[tuple[float, float], ...] | None,
) -> JointPlan:
    """Queues (ou griffes si ``pin_spans`` est donné) ajoutées à l'invitée, logements enlevés à
    l'hôte, coin ajouté ou retiré par le contact en biais."""
    layout = _Layout(frame, outer_side, values)
    contact = frame.contact
    if pin_spans is None:
        parts = [_tail(layout, span, 0.0) for span in values.tails]
        sockets = [_tail(layout, span, CUT_OVERRUN_MM) for span in values.tails]
    else:
        width = frame.contact_width
        parts = [_pin(layout, span, 0.0, width) for span in pin_spans]
        sockets = [_pin(layout, span, CUT_OVERRUN_MM, width) for span in pin_spans]
    wedge = () if contact.added is None else (contact.added,)
    trims = () if contact.removed is None else (contact.removed,)
    bevels: tuple[Bevel, ...] = (frame.bevel(),) if contact.angle > _BEVEL_MIN_DEG else ()
    return JointPlan(
        host_cuts=tuple(socket.moved(contact.transform) for socket in sockets),
        guest_additions=(*wedge, *parts),
        guest_trims=trims,
        guest_bevels=bevels,
    )
