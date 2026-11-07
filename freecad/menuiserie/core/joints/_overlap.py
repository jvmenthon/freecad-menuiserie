# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chevauchement de deux pièces en biais (ADR 0034) : la pièce logée dans le repère de l'hôte.

Feuillure, mi-bois et onglet se calculent sur deux pièces qui se superposent. Quand leur
rotation relative n'est pas d'équerre, la pièce logée est une boîte dans un repère quelconque
(``Polyhedron``) et la matière commune est l'hôte coupé par les six faces de cette boîte.
Module privé.
"""

from __future__ import annotations

from dataclasses import dataclass

from freecad.menuiserie.core._polyhedron import Plane, Polyhedron, clipped_box
from freecad.menuiserie.core.contact import ObliqueContact, relation
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    Box,
    JointError,
    PlacedBlock,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints._base import SEPARATED

__all__ = ["OBLIQUE_OVERLAP_ONLY", "ObliqueOverlap", "oblique_overlap"]

OBLIQUE_OVERLAP_ONLY = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Entre pièces en biais, dessinez les deux pièces de façon qu'elles se chevauchent.",
)


@dataclass(frozen=True)
class ObliqueOverlap:
    """Pièces en biais qui se chevauchent : invitée dans le repère de l'hôte et matière commune."""

    to_host: RigidTransform  # repère de l'invitée → repère de l'hôte (rotation exacte)
    guest_box: Box  # boîte de l'invitée, repère de l'invitée
    host_box: Box  # boîte de l'hôte, repère de l'hôte
    common: Polyhedron  # matière commune, repère de l'hôte

    def guest_faces(self) -> tuple[Plane, ...]:
        """Les six faces de l'invitée en demi-espaces du repère de l'hôte."""
        return _faces(self.guest_box, self.to_host)

    def guest_solid(self, overrun: float = 0.0) -> Polyhedron:
        """Invitée dans le repère de l'hôte, prolongée de ``overrun`` à chaque bout de son axe
        le plus long."""
        box = self.guest_box
        axis = max(range(3), key=box.size)
        extended = box.with_range(axis, box.lo(axis) - overrun, box.hi(axis) + overrun)
        return Polyhedron(extended, self.to_host)

    def splits_host(self, overrun: float = 0.0) -> bool:
        """Vrai si enlever :meth:`guest_solid` coupe l'hôte en deux ou l'enlève entièrement.

        L'invitée (prolongée de ``overrun``) doit sortir de l'hôte par ses deux bouts (sinon c'est
        une entaille) ; la coupe est alors un prisme de section rectangulaire qui sépare l'hôte si
        cette section en couvre toute l'étendue dans un sens et laisse de la matière de part et
        d'autre dans l'autre."""
        box, to_host = self.guest_box, self.to_host
        long_axis = max(range(3), key=box.size)
        others = [axis for axis in range(3) if axis != long_axis]
        dirs = {
            axis: to_host.rotate(Vec3(0.0, 0.0, 0.0).with_component(axis, 1.0)) for axis in range(3)
        }
        corners = [
            Vec3(x, y, z)
            for x in (self.host_box.lo(0), self.host_box.hi(0))
            for y in (self.host_box.lo(1), self.host_box.hi(1))
            for z in (self.host_box.lo(2), self.host_box.hi(2))
        ]
        origin = to_host.apply(Vec3(0.0, 0.0, 0.0))

        def coords(axis: int) -> list[float]:
            direction = dirs[axis]
            return [
                (c.x - origin.x) * direction.x
                + (c.y - origin.y) * direction.y
                + (c.z - origin.z) * direction.z
                for c in corners
            ]

        tol = CONTACT_TOLERANCE_MM
        extended = box.with_range(
            long_axis, box.lo(long_axis) - overrun, box.hi(long_axis) + overrun
        )
        reach = clipped_box(self.host_box, RigidTransform.identity(), _faces(extended, to_host))
        sides = tuple(
            plane for index, plane in enumerate(_faces(box, to_host)) if index // 2 != long_axis
        )
        endless = clipped_box(self.host_box, RigidTransform.identity(), sides)
        if reach is None or endless is None:
            return False
        if reach.volume() < endless.volume() * (1.0 - 1e-6):
            return False  # l'invitée s'arrête avant de traverser l'hôte : simple entaille
        covered, free = [], []
        for axis in others:
            values = coords(axis)
            covered.append(box.lo(axis) <= min(values) + tol and box.hi(axis) >= max(values) - tol)
            free.append(box.lo(axis) > min(values) + tol and box.hi(axis) < max(values) - tol)
        # Tout couvert, ou couvert dans un sens et matière restante des deux côtés dans l'autre.
        return all(covered) or (covered[0] and free[1]) or (covered[1] and free[0])


def _faces(box: Box, transform: RigidTransform) -> tuple[Plane, ...]:
    """Les six faces de ``box`` (repère source) en demi-espaces du repère d'arrivée."""
    planes = []
    centre = Vec3(box.center(0), box.center(1), box.center(2))
    for index in range(3):
        for sign, bound in ((-1.0, box.lo(index)), (1.0, box.hi(index))):
            point = centre.with_component(index, bound)
            normal = Vec3(0.0, 0.0, 0.0).with_component(index, sign)
            planes.append(Plane(transform.apply(point), transform.rotate(normal)))
    return tuple(planes)


def oblique_overlap(host: PlacedBlock, guest: PlacedBlock) -> ObliqueOverlap:
    """Chevauchement de deux pièces dont la rotation n'est pas d'équerre ; :class:`JointError`
    si elles sont écartées ou ne font que se toucher (``OBLIQUE_OVERLAP_ONLY``).

    La matière commune est calculée directement : un bout d'invitée qui entre dans l'hôte est un
    chevauchement pour ces assemblages, même si ``relation`` y voit un contact (ADR 0016)."""
    to_host = host.placement.inverse().compose(guest.placement)
    planes = _faces(guest.local_box(), to_host)
    common = clipped_box(host.local_box(), RigidTransform.identity(), planes)
    if common is None:
        if isinstance(relation(host, guest), ObliqueContact):
            raise JointError(OBLIQUE_OVERLAP_ONLY, {})
        raise JointError(SEPARATED, {})
    return ObliqueOverlap(to_host, guest.local_box(), host.local_box(), common)
