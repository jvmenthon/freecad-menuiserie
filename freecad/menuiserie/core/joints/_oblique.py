# SPDX-License-Identifier: LGPL-2.1-or-later
"""Profil en biais du tenon et de la languette entre deux pièces non d'équerre (ADR 0024, AB-b).

Frère de :mod:`._profile` : :class:`ObliqueFrame` regroupe ce que ``ContactFrame`` regroupe
(axe, plans, passage de repère) pour une invitée dont le bout rencontre en biais une face de
l'hôte. Tous les calculs se font dans le repère de l'invitée. Le plan d'épaulement est la face de
l'hôte ; le tenon est une barre de la section voulue, le long de l'axe du tenon, coupée par ce plan
(polyèdre convexe de :mod:`.._polyhedron`) ; la mortaise est la même barre prolongée du jeu de
fond. Module privé.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron, clipped_box
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Axis,
    Box,
    JointError,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.joints._base import (
    Bevel,
    JointPlan,
    mm_text,
)
from freecad.menuiserie.core.joints._oblique_frame import Frame, ObliqueFrame
from freecad.menuiserie.core.joints._profile import (
    OUTSIDE_CONTACT,
    THICKNESS_AXIS,
    TOO_DEEP,
    TOO_SMALL,
    ProfileRules,
    ProfileValues,
    build_profile,
    check_walls,
)
from freecad.menuiserie.core.vectors import cross, dot, unit

__all__ = ["build_any", "build_oblique_profile"]

_MARGIN: Final = 1e-9
_SLACK_MM: Final = 2.0  # marge des barres, hors matière
_BEVEL_MIN_DEG: Final = 1e-4  # sous cet écart, le bout est coupé d'équerre


def build_any(frame: Frame, values: ProfileValues, rules: ProfileRules) -> JointPlan:
    """Plan du profil selon le cadre, d'équerre ou en biais."""
    if isinstance(frame, ObliqueFrame):
        return build_oblique_profile(frame, values, rules)
    return build_profile(frame, values, rules)


@dataclass(frozen=True)
class _Section:
    """Section du tenon : centre, directions de sa largeur (u) et de son épaisseur (v) et axe
    du tenon (d) ; le repère (u, v, d) est direct."""

    origin: Vec3
    u: Vec3
    v: Vec3
    d: Vec3
    width: float
    thickness: float

    def corners(self) -> list[Vec3]:
        """Les quatre coins de la section."""
        half_u, half_v = self.u.scaled(self.width / 2), self.v.scaled(self.thickness / 2)
        return [self.origin + half_u.scaled(a) + half_v.scaled(b) for a in (-1, 1) for b in (-1, 1)]

    def frame(self) -> RigidTransform:
        """Repère de la barre : X = largeur, Y = épaisseur, Z = axe du tenon."""
        rows = tuple(
            (self.u.component(i), self.v.component(i), self.d.component(i)) for i in range(3)
        )
        return RigidTransform((rows[0], rows[1], rows[2]), self.origin)

    def bar(self, start: float, end: float, reach: float = 0.0) -> Box:
        """Barre de la section entre les abscisses ``start`` et ``end`` de l'axe ; ``reach`` > 0
        la prolonge de part et d'autre selon la largeur (rainure filante)."""
        half_u = max(self.width / 2, reach)
        return Box.from_ranges(
            [(-half_u, half_u), (-self.thickness / 2, self.thickness / 2), (start, end)]
        )


def _section(frame: ObliqueFrame, values: ProfileValues) -> _Section:
    face = frame.face
    centre = Vec3(face.center(0), face.center(1), face.center(2))
    origin = centre.with_component(
        frame.width_axis, centre.component(frame.width_axis) + values.width_offset
    ).with_component(THICKNESS_AXIS, centre.component(THICKNESS_AXIS) + values.thickness_offset)
    d = frame.direction
    wide = Axis.of(frame.width_axis, 1).unit()
    u = unit(wide - d.scaled(dot(wide, d)))
    section = _Section(origin, u, cross(d, u), d, values.width, values.thickness)
    _check_footprint(frame, section, values)
    return section


def _check_footprint(frame: ObliqueFrame, section: _Section, values: ProfileValues) -> None:
    """La base du tenon sur le plan d'épaulement (la section projetée le long de l'axe du
    tenon) reste dans l'empreinte du bout de l'invitée sur ce plan (E4)."""
    plane, outward, box = frame.contact.shoulder, frame.outward, frame.guest.local_box()
    for corner in section.corners():
        base = corner + section.d.scaled(dot(corner - plane.point, outward) / frame.cosine)
        for axis in (frame.width_axis, THICKNESS_AXIS):
            if not box.lo(axis) - _MARGIN <= base.component(axis) <= box.hi(axis) + _MARGIN:
                params = {
                    "width": mm_text(values.width),
                    "thickness": mm_text(values.thickness),
                    "contact_width": mm_text(frame.contact_width),
                    "contact_thickness": mm_text(frame.contact_thickness),
                }
                raise JointError(OUTSIDE_CONTACT, params)


def _enter(frame: ObliqueFrame, section: _Section) -> float:
    """Abscisse (sur l'axe du tenon) la plus basse où la barre est entrée dans l'hôte, jusqu'au
    plan d'épaulement décalé de ``offset``, pour les quatre coins de la section."""
    plane = frame.contact.shoulder
    outward = frame.outward
    return min(dot(corner - plane.point, outward) / frame.cosine for corner in section.corners())


def _leave(frame: ObliqueFrame, section: _Section) -> float:
    """Abscisse la plus haute où la barre sort de l'hôte, par la face opposée décalée de
    ``offset``."""
    plane = frame.contact.opposite
    outward = unit(plane.normal)
    return max(-dot(corner - plane.point, outward) / frame.cosine for corner in section.corners())


def _axis_origin(frame: ObliqueFrame, section: _Section) -> float:
    """Abscisse où l'axe du tenon traverse le plan d'épaulement."""
    return dot(section.origin - frame.contact.shoulder.point, frame.outward) / frame.cosine


def _tenon(
    frame: ObliqueFrame, section: _Section, length: float, through: bool
) -> Polyhedron | None:
    """Barre de la section au-delà du plan d'épaulement, de ``length`` sur l'axe (arrêtée à la
    face opposée de l'hôte si ``through``)."""
    start = _enter(frame, section) - _SLACK_MM
    planes = [frame.contact.shoulder]
    if through:
        planes.append(frame.contact.opposite)
        end = _leave(frame, section) + _SLACK_MM
    else:
        end = _axis_origin(frame, section) + length
    return clipped_box(section.bar(start, end), section.frame(), tuple(planes))


def _host_faces(frame: ObliqueFrame) -> dict[Axis, Plane]:
    """Les six faces de l'hôte (repère de l'invitée), normales sortantes."""
    to_guest = frame.contact.transform.inverse()
    box = frame.host_box
    centre = Vec3(box.center(0), box.center(1), box.center(2))
    faces = {}
    for index in range(3):
        for sign in (-1.0, 1.0):
            axis = Axis.of(index, sign)
            bound = box.hi(index) if sign > 0 else box.lo(index)
            point = to_guest.apply(centre.with_component(index, bound))
            faces[axis] = Plane(point, to_guest.rotate(axis.unit()))
    return faces


def _mortise(
    frame: ObliqueFrame,
    section: _Section,
    values: ProfileValues,
    rules: ProfileRules,
    through: bool,
) -> Polyhedron | None:
    """Logement : la barre prolongée du jeu de fond, coupée par le plan d'épaulement (comme le
    logement d'équerre, il part de la face de l'hôte : B4)."""
    if rules.extend_housing:
        return _groove(frame, section, values, through)
    planes = [frame.contact.shoulder]
    start = _enter(frame, section) - _SLACK_MM
    if through:
        planes.append(frame.contact.opposite)
        end = _leave(frame, section) + _SLACK_MM
    else:
        end = _axis_origin(frame, section) + values.housing_depth
    return clipped_box(section.bar(start, end), section.frame(), tuple(planes))


def _groove_bottom(frame: ObliqueFrame, section: _Section, values: ProfileValues) -> Plane:
    """Fond de la rainure : parallèle au plan d'épaulement (profondeur constante sur toute la
    longueur), juste sous le coin le plus profond de la languette, plus le jeu de fond."""
    outward = frame.outward
    tip = _axis_origin(frame, section) + values.length
    deepest = max(
        -dot(corner + section.d.scaled(tip) - frame.contact.shoulder.point, outward)
        for corner in section.corners()
    )
    clearance = values.housing_depth - values.length
    point = frame.contact.shoulder.point - outward.scaled(deepest + clearance)
    return Plane(point, -outward)


def _groove(
    frame: ObliqueFrame, section: _Section, values: ProfileValues, through: bool
) -> Polyhedron | None:
    """Rainure filante : elle suit l'intersection du plan d'épaulement et du plan de la
    languette, pas la largeur de l'invitée, qui sort du plan d'épaulement quand le biais tourne
    la pièce dans sa largeur. Fond : plan normal à l'axe de la languette."""
    shoulder = frame.contact.shoulder
    along = unit(cross(frame.outward, section.v))
    depth = cross(along, section.v)
    rows = tuple((along.component(i), section.v.component(i), depth.component(i)) for i in range(3))
    matrix = (rows[0], rows[1], rows[2])
    reach = _extent(frame) + _SLACK_MM
    box = Box.from_ranges(
        [(-reach, reach), (-section.thickness / 2, section.thickness / 2), (-reach, reach)]
    )
    bottom = frame.contact.opposite if through else _groove_bottom(frame, section, values)
    faces = _host_faces(frame)
    host = frame.contact.host_face
    planes = [shoulder, bottom, *(p for axis, p in faces.items() if axis.index != host.index)]
    return clipped_box(box, RigidTransform(matrix, section.origin), tuple(planes))


def _extent(frame: ObliqueFrame) -> float:
    """Longueur de la diagonale de l'hôte, qui borne toute barre filante."""
    box = frame.host_box
    return math.sqrt(sum(box.size(i) ** 2 for i in range(3)))


def _depth(frame: ObliqueFrame, housing: Polyhedron) -> float:
    """Profondeur du point le plus profond du logement sous le plan d'épaulement."""
    plane = frame.contact.shoulder
    outward = frame.outward
    return max(-dot(vertex - plane.point, outward) for vertex in housing.vertices())


def _walls(frame: ObliqueFrame, housing: Polyhedron, rules: ProfileRules) -> None:
    """Une paroi de matière de chaque côté du logement, sur les axes de l'hôte parallèles au plan
    d'épaulement (celui que suit la rainure filante n'en demande pas)."""
    host_axes = [i for i in range(3) if i != frame.contact.host_face.index]
    along = frame.contact.transform.rotate(Axis.of(frame.width_axis, 1).unit())
    groove = max(host_axes, key=lambda i: abs(along.component(i)))
    axes = tuple(i for i in host_axes if rules.walled_width or i != groove)
    bounds = housing.moved(frame.contact.transform).bounds()
    check_walls(bounds, frame.host_box, axes)


def build_oblique_profile(
    frame: ObliqueFrame, values: ProfileValues, rules: ProfileRules
) -> JointPlan:
    """Plan d'un tenon ou d'une languette en biais : tenon (et coin ajouté) dans l'invitée, coin
    retiré, logement dans l'hôte, contrôles de matière. Mêmes règles qu'``build_profile``."""
    if min(values.width, values.thickness, values.length) <= 0:
        raise JointError(TOO_SMALL, {})
    section = _section(frame, values)
    through = values.housing_depth >= frame.full_depth - _MARGIN
    flush = values.length >= frame.full_depth - _MARGIN  # tenon traversant (B4)
    housing = _mortise(frame, section, values, rules, through)
    tenon = _tenon(frame, section, values.length, flush)
    if housing is None or tenon is None:
        raise JointError(TOO_SMALL, {})
    if values.housing_depth > frame.full_depth + _MARGIN:
        depth = {"depth": mm_text(values.housing_depth), "host_depth": mm_text(frame.full_depth)}
        raise JointError(TOO_DEEP, depth)
    deepest = _depth(frame, housing)
    if not through and deepest >= frame.host_depth - CONTACT_TOLERANCE_MM:
        if deepest > frame.host_depth + _MARGIN:
            depth = {"depth": mm_text(deepest), "host_depth": mm_text(frame.host_depth)}
            raise JointError(TOO_DEEP, depth)
        through = True  # affleure la face opposée : débouchant (pas de peau nulle)
        housing = _mortise(frame, section, values, rules, through)
        tenon = _tenon(frame, section, values.length, flush)
        if housing is None or tenon is None:
            raise JointError(TOO_SMALL, {})
    _walls(frame, housing, rules)
    return _plan(frame, housing, tenon)


def _plan(frame: ObliqueFrame, housing: Polyhedron, tenon: Polyhedron) -> JointPlan:
    contact = frame.contact
    wedge = () if contact.added is None else (contact.added,)
    trims = () if contact.removed is None else (contact.removed,)
    bevels: tuple[Bevel, ...] = ()
    if contact.angle > _BEVEL_MIN_DEG:
        bevels = (frame.bevel(),)
    return JointPlan(
        host_cuts=(housing.moved(contact.transform),),
        guest_additions=(*wedge, tenon),
        guest_trims=trims,
        guest_bevels=bevels,
    )
