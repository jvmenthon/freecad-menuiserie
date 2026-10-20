# SPDX-License-Identifier: LGPL-2.1-or-later
"""Position relative de deux pièces d'équerre : contact, chevauchement ou pièces écartées (J3a).

Toutes les longueurs sont en mm ; la comparaison se fait dans le repère local de l'hôte, à
:data:`~.geometry.CONTACT_TOLERANCE_MM` près.
"""

from __future__ import annotations

from dataclasses import dataclass

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Axis,
    Box,
    PlacedBlock,
    RigidTransform,
    moved_axis,
    moved_box,
    relative_transform,
)

__all__ = ["Contact", "Overlap", "Separated", "classify"]


@dataclass(frozen=True)
class Contact:
    """Deux pièces qui se touchent par une face (chevauchement nul à la tolérance près)."""

    guest_face: Axis
    host_face: Axis
    rectangle: Box  # aplati, repère de l'invitée
    host_depth: float  # étendue de l'hôte dans l'axe normal au contact


@dataclass(frozen=True)
class Overlap:
    """Deux pièces qui se chevauchent sur les trois axes."""

    common: Box  # repère de l'hôte


@dataclass(frozen=True)
class Separated:
    """Pièces écartées, ou qui ne se touchent que par une arête ou un coin."""


def _contact(host_box: Box, guest_box: Box, normal: int, transform: RigidTransform) -> Contact:
    host_side = 1 if guest_box.center(normal) > host_box.center(normal) else -1
    plane = guest_box.lo(normal) if host_side > 0 else guest_box.hi(normal)
    ranges = [
        (max(host_box.lo(i), guest_box.lo(i)), min(host_box.hi(i), guest_box.hi(i)))
        for i in range(3)
    ]
    ranges[normal] = (plane, plane)
    host_face = Axis.of(normal, host_side)
    back = transform.inverse()
    rectangle = moved_box(Box.from_ranges(ranges), back)
    guest_face = moved_axis(back, host_face.opposite())
    return Contact(guest_face, host_face, rectangle, host_box.size(normal))


def classify(host: PlacedBlock, guest: PlacedBlock) -> Contact | Overlap | Separated:
    """Position relative de deux pièces d'équerre (``JointError`` sinon)."""
    transform = relative_transform(host, guest)
    host_box = host.local_box()
    guest_box = moved_box(guest.local_box(), transform)
    overlaps = [
        min(host_box.hi(i), guest_box.hi(i)) - max(host_box.lo(i), guest_box.lo(i))
        for i in range(3)
    ]
    if min(overlaps) < -CONTACT_TOLERANCE_MM:
        return Separated()
    touching = [i for i, overlap in enumerate(overlaps) if overlap <= CONTACT_TOLERANCE_MM]
    if not touching:
        lows = [max(host_box.lo(i), guest_box.lo(i)) for i in range(3)]
        return Overlap(
            Box.from_ranges([(low, low + size) for low, size in zip(lows, overlaps, strict=True)])
        )
    if len(touching) > 1:
        return Separated()
    return _contact(host_box, guest_box, touching[0], transform)
