# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contact entre deux pièces dont l'angle relatif n'est pas un multiple de 90° (ADR 0024, AB-a).

Tout se passe dans le repère de l'**invitée** : l'hôte y est une boîte tournée. Le bout de
l'invitée (ou son chant, pour une languette) rencontre la face de l'hôte que son axe traverse.
La face de l'hôte est le plan d'épaulement ; l'invitée peut être dessinée pointe contre la face
(coin ajouté), hors tout (coin retiré) ou à cheval (les deux). Module privé ; l'API est
:func:`.contact.relation`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core._contact_types import ObliqueContact, Overlap, Separated
from freecad.menuiserie.core._polyhedron import Plane, Polyhedron, clipped_box
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    MAX_OBLIQUE_DEG,
    Axis,
    Box,
    JointError,
    PlacedBlock,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.vectors import dot

__all__ = ["EDGE_HIT", "TOO_OBLIQUE", "oblique_relation"]

TOO_OBLIQUE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les deux pièces font un angle de {angle}° ; l'atelier accepte au plus {maximum}° "
    "pour un assemblage en biais.",
)
EDGE_HIT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le bout de la pièce rencontre une arête ou un coin de l'autre pièce et non une face : "
    "déplacez-la pour qu'il arrive sur une face.",
)

_IDENTITY: Final = RigidTransform.identity()
_ENDS: Final = (Axis.X_POS, Axis.X_NEG)  # bouts, essayés d'abord
_EDGES: Final = (Axis.Y_POS, Axis.Y_NEG)  # chants (languette)
_PARALLEL: Final = 1e-9
_ANGLE_SLACK_DEG: Final = 1e-6


@dataclass(frozen=True)
class _Setup:
    guest_box: Box
    host_box: Box
    to_host: RigidTransform  # invitée → hôte, rotation exacte
    to_guest: RigidTransform


@dataclass(frozen=True)
class _HostFace:
    axis: Axis  # dans le repère de l'hôte
    normal: Vec3  # unitaire, sortante, repère de l'invitée
    point: Vec3  # un point de la face, repère de l'invitée

    def distance(self, point: Vec3) -> float:
        """Distance signée au plan de la face : positive du côté extérieur de l'hôte."""
        return dot(point - self.point, self.normal)


@dataclass(frozen=True)
class _Candidate:
    guest_face: Axis
    face: _HostFace
    gap: float  # distance du centre de la face de l'invitée au plan


def _setup(host: PlacedBlock, guest: PlacedBlock) -> _Setup:
    to_host = host.placement.inverse().compose(guest.placement)
    return _Setup(guest.local_box(), host.local_box(), to_host, to_host.inverse())


def _centre(box: Box) -> Vec3:
    return Vec3(box.center(0), box.center(1), box.center(2))


def _host_faces(setup: _Setup) -> list[_HostFace]:
    faces = []
    for index in range(3):
        for sign in (-1.0, 1.0):
            axis = Axis.of(index, sign)
            bound = setup.host_box.hi(index) if sign > 0 else setup.host_box.lo(index)
            point = setup.to_guest.apply(_centre(setup.host_box).with_component(index, bound))
            faces.append(_HostFace(axis, setup.to_guest.rotate(axis.unit()), point))
    return faces


def _face_points(box: Box, face: Axis) -> tuple[Vec3, list[Vec3]]:
    """Centre et quatre coins de la face ``face`` d'une boîte."""
    index = face.index
    bound = box.hi(index) if face.sign > 0 else box.lo(index)
    first, second = (i for i in range(3) if i != index)
    centre = _centre(box).with_component(index, bound)
    corners = [
        centre.with_component(first, a).with_component(second, b)
        for a in (box.lo(first), box.hi(first))
        for b in (box.lo(second), box.hi(second))
    ]
    return centre, corners


def _in_face(setup: _Setup, face: _HostFace, point: Vec3) -> bool:
    """Le point (repère de l'invitée, dans le plan de la face) est dans le rectangle de la face."""
    local = setup.to_host.apply(point)
    return all(
        setup.host_box.lo(i) - CONTACT_TOLERANCE_MM
        <= local.component(i)
        <= setup.host_box.hi(i) + CONTACT_TOLERANCE_MM
        for i in range(3)
        if i != face.axis.index
    )


def _entered_through(setup: _Setup, face: _HostFace, centre: Vec3, direction: Vec3) -> bool:
    """L'axe de la face de l'invitée entre dans l'hôte par ``face``."""
    slope = dot(direction, face.normal)
    if slope > -_PARALLEL:
        return False
    reach = -face.distance(centre) / slope
    return _in_face(setup, face, centre + direction.scaled(reach))


def _candidate(setup: _Setup, faces: list[_HostFace], guest_face: Axis) -> _Candidate | None:
    """Face de l'hôte que rencontre la face ``guest_face`` de l'invitée, ``None`` s'il n'y en a
    pas ; ``JointError`` (EDGE_HIT) si l'axe passe exactement sur une arête."""
    centre, corners = _face_points(setup.guest_box, guest_face)
    body = _centre(setup.guest_box)
    direction = guest_face.unit()
    valid = []
    for face in faces:
        reaches = min(face.distance(corner) for corner in corners) <= CONTACT_TOLERANCE_MM
        outside = face.distance(body) > CONTACT_TOLERANCE_MM
        if reaches and outside and _entered_through(setup, face, centre, direction):
            valid.append(_Candidate(guest_face, face, abs(face.distance(centre))))
    if len(valid) > 1:
        raise JointError(EDGE_HIT, {})
    return valid[0] if valid else None


def _removed(setup: _Setup, face: _HostFace) -> Polyhedron | None:
    """Partie de l'invitée qui entre dans l'hôte au-delà du plan de la face."""
    return clipped_box(setup.guest_box, _IDENTITY, (Plane(face.point, face.normal),))


def _added(setup: _Setup, candidate: _Candidate, cosine: float) -> Polyhedron | None:
    """Prolongement de l'invitée, au-delà de sa face, jusqu'au plan de la face de l'hôte."""
    face, guest_face = candidate.face, candidate.guest_face
    _, corners = _face_points(setup.guest_box, guest_face)
    reach = max(face.distance(corner) for corner in corners) / cosine
    if reach <= CONTACT_TOLERANCE_MM:
        return None
    index, box = guest_face.index, setup.guest_box
    if guest_face.sign > 0:
        extended = box.with_range(index, box.hi(index), box.hi(index) + reach)
    else:
        extended = box.with_range(index, box.lo(index) - reach, box.lo(index))
    return clipped_box(extended, _IDENTITY, (Plane(face.point, -face.normal),))


def _common(setup: _Setup) -> Overlap | None:
    """Matière commune des deux pièces (repère de l'hôte), ``None`` s'il n'y en a pas."""
    planes = tuple(Plane(face.point, face.normal) for face in _host_faces(setup))
    common = clipped_box(setup.guest_box, _IDENTITY, planes)
    return None if common is None else Overlap(common.moved(setup.to_host).bounds())


def _escapes(setup: _Setup, face: _HostFace, removed: Polyhedron) -> set[Axis]:
    """Faces de l'hôte (repère de l'hôte) que le coin retiré dépasse, hors la face d'entrée."""
    box, found = setup.host_box, set()
    for vertex in removed.vertices():
        local = setup.to_host.apply(vertex)
        for index in range(3):
            if local.component(index) > box.hi(index) + CONTACT_TOLERANCE_MM:
                found.add(Axis.of(index, 1.0))
            if local.component(index) < box.lo(index) - CONTACT_TOLERANCE_MM:
                found.add(Axis.of(index, -1.0))
    found.discard(face.axis)
    return found


def _build(setup: _Setup, candidate: _Candidate) -> ObliqueContact | Overlap:
    face, guest_face = candidate.face, candidate.guest_face
    cosine = min(1.0, -dot(guest_face.unit(), face.normal))
    angle = math.degrees(math.acos(cosine))
    if angle > MAX_OBLIQUE_DEG + _ANGLE_SLACK_DEG:
        raise JointError(TOO_OBLIQUE, {"angle": f"{angle:.1f}", "maximum": f"{MAX_OBLIQUE_DEG:g}"})
    removed = _removed(setup, face)
    if removed is not None:
        escapes = _escapes(setup, face, removed)
        if face.axis.opposite() in escapes:
            return _common(setup) or Overlap(setup.host_box)
        if escapes:
            raise JointError(EDGE_HIT, {})
    opposite = next(f for f in _host_faces(setup) if f.axis == face.axis.opposite())
    return ObliqueContact(
        guest_face=guest_face,
        host_face=face.axis,
        angle=angle,
        shoulder=Plane(face.point, face.normal),
        opposite=Plane(opposite.point, opposite.normal),
        removed=removed,
        added=_added(setup, candidate, cosine),
        transform=setup.to_host,
        host_depth=setup.host_box.size(face.axis.index),
    )


def oblique_relation(host: PlacedBlock, guest: PlacedBlock) -> ObliqueContact | Overlap | Separated:
    """Position relative de deux pièces dont la rotation relative n'est pas d'équerre.

    Contact en biais, chevauchement (invitée qui traverse l'hôte ou y entre par un chant),
    pièces écartées ; ``JointError`` si l'écart d'angle dépasse
    :data:`~.geometry.MAX_OBLIQUE_DEG` ou si le bout tombe sur une arête de l'hôte.
    """
    setup = _setup(host, guest)
    faces = _host_faces(setup)
    for group in (_ENDS, _EDGES):
        found = [c for axis in group if (c := _candidate(setup, faces, axis)) is not None]
        if found:
            return _build(setup, min(found, key=lambda c: c.gap))
    return _common(setup) or Separated()
