# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cadre du profil en biais : contact vu de l'invitée (ADR 0024, AB-b). Module privé."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.contact import ObliqueContact, Overlap, relation
from freecad.menuiserie.core.geometry import Box, JointError, PlacedBlock, Vec3, is_square
from freecad.menuiserie.core.joints._base import (
    OVERLAPPING,
    SEPARATED,
    Bevel,
    ObliqueReference,
    mm_round,
)
from freecad.menuiserie.core.joints._profile import (
    EDGE_CONTACT,
    THICKNESS_AXIS,
    ContactFrame,
    contact_frame,
)
from freecad.menuiserie.core.vectors import dot, norm, unit

__all__ = ["Frame", "ObliqueFrame", "profile_frame"]

_MARGIN: Final = 1e-9
_TENON: Final = ObliqueReference.TENON_PIECE.value
_MIN_WALL_MM: Final = 1.0  # paroi laissée au fond par la longueur automatique


@dataclass(frozen=True)
class ObliqueFrame:
    """Contact en biais vu de l'invitée : face de l'invitée, plan d'épaulement et passages de
    repère. Mêmes propriétés que ``ContactFrame`` pour les règles de valeurs communes."""

    contact: ObliqueContact
    guest: PlacedBlock
    host_box: Box  # boîte de l'hôte, repère de l'hôte
    width_axis: int
    reference: str = ObliqueReference.TENON_PIECE.value

    @property
    def normal(self) -> int:
        """Axe local de l'invitée normal à la face qui touche."""
        return self.contact.guest_face.index

    @property
    def sign(self) -> int:
        """Sens, sur l'axe normal, de l'invitée vers l'hôte."""
        return self.contact.guest_face.sign

    @property
    def outward(self) -> Vec3:
        """Normale unitaire de la face de l'hôte, sortante (repère de l'invitée)."""
        return unit(self.contact.shoulder.normal)

    @property
    def fibre(self) -> Vec3:
        """Axe de l'invitée (son fil), de son bout vers l'hôte."""
        return self.contact.guest_face.unit()

    @property
    def direction(self) -> Vec3:
        """Axe du tenon selon la référence : celui de l'invitée (pièce à tenon, défaut), la
        perpendiculaire à la face de l'hôte (pièce mortaisée) ou la bissectrice (mi-angle)."""
        if self.reference == ObliqueReference.MORTISED_PIECE.value:
            return -self.outward
        if self.reference == ObliqueReference.HALF_ANGLE.value:
            return unit(self.fibre - self.outward)
        return self.fibre

    @property
    def cosine(self) -> float:
        """Cosinus de l'angle entre l'axe du tenon et la normale (opposée) de l'épaulement."""
        return -dot(self.direction, self.outward)

    @property
    def host_depth(self) -> float:
        """Étendue de l'hôte perpendiculairement au plan d'épaulement."""
        return self.contact.host_depth

    @property
    def full_depth(self) -> float:
        """Profondeur d'un logement traversant, mesurée sur l'axe du tenon."""
        return self.host_depth / self.cosine

    @property
    def through_length(self) -> float:
        """Longueur d'un tenon traversant : plan d'épaulement → face opposée, sur l'axe."""
        return self.full_depth

    @property
    def face(self) -> Box:
        """Face de l'invitée qui touche (boîte aplatie, repère de l'invitée)."""
        box = self.guest.local_box()
        bound = box.hi(self.normal) if self.sign > 0 else box.lo(self.normal)
        return box.with_range(self.normal, bound, bound)

    @property
    def contact_width(self) -> float:
        """Étendue de la face de l'invitée selon la largeur du profil."""
        return self.face.size(self.width_axis)

    @property
    def contact_thickness(self) -> float:
        """Étendue de la face de l'invitée selon l'épaisseur du profil."""
        return self.face.size(THICKNESS_AXIS)

    def _tilt_reach(self) -> float:
        """Plus grand écart d'un coin de la face à son centre, dans le sens de l'inclinaison."""
        tilt = self.outward + self.direction.scaled(self.cosine)
        if norm(tilt) < _MARGIN:
            return 0.0
        tilt = unit(tilt)
        face = self.face
        centre = Vec3(face.center(0), face.center(1), face.center(2))
        return max(
            abs(dot(Vec3(x, y, z) - centre, tilt))
            for x in (face.lo(0), face.hi(0))
            for y in (face.lo(1), face.hi(1))
            for z in (face.lo(2), face.hi(2))
        )

    def bevel(self) -> Bevel:
        """Bout coupé en biais : face, normale du plan d'épaulement et long point (coordonnée,
        sur l'axe de la face, du point le plus long du corps : coins ajoutés compris, coins
        retirés exclus)."""
        plane, outward = self.contact.shoulder, self.outward
        face, sign, index = self.face, self.sign, self.normal
        bound = face.hi(index) if sign > 0 else face.lo(index)
        reaches = [
            dot(Vec3(x, y, z) - plane.point, outward) / self.cosine
            for x in (face.lo(0), face.hi(0))
            for y in (face.lo(1), face.hi(1))
            for z in (face.lo(2), face.hi(2))
        ]
        return Bevel(self.contact.guest_face, plane.normal, bound + sign * max(reaches))

    def oblique_values(self) -> dict[str, float]:
        """Biais et réglages de la scie, affichés avec les valeurs effectives."""
        cut, tilt = self.bevel().saw_angles()
        grain = math.degrees(math.acos(min(1.0, max(-1.0, dot(self.direction, self.fibre)))))
        return {
            "oblique": round(self.contact.angle, 1),
            "cut_angle": cut,
            "blade_tilt": tilt,
            "grain_angle": round(grain, 1),
        }

    def auto_length(self, clearance: float) -> float:
        """Longueur automatique : ``mm_round(2 · profondeur / (3 · cos β))`` (la formule
        d'équerre quand β → 0), réduite au mm tant que le point le plus profond de la mortaise
        (jeu de fond compris) ne laisse pas une paroi de matière (spécification, § 4.4)."""
        cosine = self.cosine
        sine = math.sqrt(max(0.0, 1.0 - cosine * cosine))
        length = mm_round(2 * self.host_depth / (3 * cosine))
        reach = self._tilt_reach()
        while length > 1 and (length + clearance) * cosine + reach * sine > (
            self.host_depth - _MIN_WALL_MM
        ):
            length -= 1.0
        return length


Frame = ContactFrame | ObliqueFrame


def profile_frame(
    host: PlacedBlock, guest: PlacedBlock, *, end_only: bool, reference: str = _TENON
) -> Frame:
    """Cadre du profil : celui des pièces d'équerre (``contact_frame``, ADR 0016) ou, si leur
    angle n'est pas un multiple de 90°, le cadre en biais (ADR 0024)."""
    if is_square(host, guest):
        return contact_frame(host, guest, end_only=end_only)
    found = relation(host, guest)
    if not isinstance(found, ObliqueContact):
        raise JointError(OVERLAPPING if isinstance(found, Overlap) else SEPARATED, {})
    if end_only and found.guest_face.index != 0:
        raise JointError(EDGE_CONTACT, {})
    return ObliqueFrame(found, guest, host.local_box(), 1 - found.guest_face.index, reference)
