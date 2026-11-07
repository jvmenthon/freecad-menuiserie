# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tourillons entre pièces en biais (ADR 0034, lot S-c). Module privé.

Les tourillons suivent l'axe de l'invitée ; chaque axe traverse le plan d'épaulement (la face de
l'hôte) au point ``q``, d'où partent le perçage de l'hôte et ceux de l'invitée. Le coin ajouté
ou retiré par le contact en biais (ADR 0024) ramène l'invitée sur ce plan.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from freecad.menuiserie.core._polyhedron import SlantedCylinder
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, JointError, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import Bevel, JointPlan
from freecad.menuiserie.core.joints._oblique_frame import ObliqueFrame
from freecad.menuiserie.core.joints._profile import THICKNESS_AXIS
from freecad.menuiserie.core.vectors import dot

if TYPE_CHECKING:
    from freecad.menuiserie.core.joints.dowels import DowelValues

__all__ = ["oblique_dowel_plan", "oblique_reach"]

_BEVEL_MIN_DEG: Final = 1e-3
OFF_HOST_FACE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Un tourillon sortirait de la face de la pièce qui le reçoit : décalez la pièce, réduisez le "
    "nombre de tourillons ou leur distance au bord.",
)


def oblique_reach(frame: ObliqueFrame, depth: float, radius: float) -> float:
    """Profondeur, mesurée perpendiculairement à la face de l'hôte, du point le plus profond d'un
    perçage de ``depth`` (sur l'axe) et de rayon ``radius``."""
    cosine = frame.cosine
    return depth * cosine + radius * math.sqrt(max(0.0, 1.0 - cosine * cosine))


def _centre(frame: ObliqueFrame, values: DowelValues, position: float) -> Vec3:
    """Centre du tourillon sur la face de l'invitée."""
    face = frame.face
    bound = face.hi(frame.normal) if frame.sign > 0 else face.lo(frame.normal)
    point = Vec3(0.0, 0.0, 0.0).with_component(frame.normal, bound)
    point = point.with_component(frame.width_axis, face.lo(frame.width_axis) + position)
    return point.with_component(
        THICKNESS_AXIS, face.center(THICKNESS_AXIS) + values.thickness_offset
    )


def oblique_dowel_plan(frame: ObliqueFrame, values: DowelValues) -> JointPlan:
    """Perçages des deux pièces et tourillons rapportés (repère de l'hôte) entre pièces en biais."""
    contact, axis, outward = frame.contact, frame.fibre, frame.outward
    radius = values.diameter / 2
    margin = radius / frame.cosine + CONTACT_TOLERANCE_MM
    host_box = frame.host_box
    other = [i for i in range(3) if i != contact.host_face.index]
    transform = contact.transform
    inserts, host_holes, guest_holes = [], [], []
    for position in values.positions:
        centre = _centre(frame, values, position)
        travel = dot(contact.shoulder.point - centre, outward) / dot(axis, outward)
        hit = centre + axis.scaled(travel)  # axe ∩ plan d'épaulement
        in_host = transform.apply(hit)
        if any(
            in_host.component(i) < host_box.lo(i) + margin
            or in_host.component(i) > host_box.hi(i) - margin
            for i in other
        ):
            raise JointError(OFF_HOST_FACE, {})
        start = hit - axis.scaled(values.guest_depth)
        inserts.append(SlantedCylinder(start, axis, radius, values.dowel_length).moved(transform))
        hole = values.host_depth + values.hole_clearance
        host_holes.append(SlantedCylinder(hit, axis, radius, hole).moved(transform))
        deep = values.guest_depth + values.hole_clearance
        guest_holes.append(SlantedCylinder(hit, axis.scaled(-1.0), radius, deep))
    wedge = () if contact.added is None else (contact.added,)
    trims = () if contact.removed is None else (contact.removed,)
    bevels: tuple[Bevel, ...] = (frame.bevel(),) if contact.angle > _BEVEL_MIN_DEG else ()
    return JointPlan(
        host_cuts=tuple(host_holes),
        guest_cuts=tuple(guest_holes),
        guest_additions=wedge,
        guest_trims=trims,
        inserts=tuple(inserts),
        guest_bevels=bevels,
    )
