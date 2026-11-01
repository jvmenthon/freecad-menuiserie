# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rôles des deux pièces (hôte, invitée) devinés d'après leur position. Module privé."""

from __future__ import annotations

from freecad.menuiserie.core.contact import Contact, ObliqueContact, Overlap, Relation, relation
from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    JointError,
    PlacedBlock,
    is_square,
)


def _face_covered(contact: Contact, guest: PlacedBlock) -> bool:
    """Vrai si le contact couvre toute la face de l'invitée qui touche."""
    face = guest.local_box()
    normal = contact.guest_face.index
    return all(
        contact.rectangle.size(axis) >= face.size(axis) - CONTACT_TOLERANCE_MM
        for axis in range(3)
        if axis != normal
    )


def _is_end(found: Relation | None) -> bool:
    """Vrai si c'est le bout (et non le chant) de l'invitée qui touche en biais."""
    return isinstance(found, ObliqueContact) and found.guest_face.index == 0


def _safe_relation(host: PlacedBlock, guest: PlacedBlock) -> Relation | None:
    """Position relative, ``None`` si elle est refusée (bout sur une arête, angle trop grand)."""
    try:
        return relation(host, guest)
    except JointError:
        return None


def guess_roles(a: PlacedBlock, b: PlacedBlock) -> tuple[int, int]:
    """Indices (hôte, invitée) parmi ``(a, b)`` ; ordre donné conservé si c'est ambigu.

    Contact : l'invitée est la pièce dont la face qui touche est entièrement couverte (bout de
    traverse contre chant de montant). En biais : la pièce dont le bout rencontre une face de
    l'autre. Chevauchement : l'invitée est la plus mince (épaisseurs égales à
    :data:`~.geometry.CONTACT_TOLERANCE_MM` près : ordre donné).
    """
    try:
        found = relation(a, b)
    except JointError:
        if _is_end(_safe_relation(b, a)):
            return (1, 0)
        raise
    swap = _swap(a, b, found)
    return (1, 0) if swap else (0, 1)


def _swap(a: PlacedBlock, b: PlacedBlock, found: Relation) -> bool:
    """Vrai si l'invitée est ``a`` : la relation ``found`` est celle de ``a`` (hôte) et ``b``."""
    if isinstance(found, Overlap):
        # Épaisseurs égales à la tolérance de contact près : ordre donné conservé.
        return a.dimensions.thickness < b.dimensions.thickness - CONTACT_TOLERANCE_MM
    if isinstance(found, Contact):
        reverse = relation(b, a)
        a_covered = isinstance(reverse, Contact) and _face_covered(reverse, a)
        return a_covered and not _face_covered(found, b)
    if is_square(a, b):
        return False
    return not _is_end(found) and _is_end(_safe_relation(b, a))
