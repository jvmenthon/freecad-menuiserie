# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rôles des deux pièces (hôte, invitée) devinés d'après leur position. Module privé."""

from __future__ import annotations

from freecad.menuiserie.core.contact import Contact, Overlap, classify
from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, PlacedBlock


def _face_covered(contact: Contact, guest: PlacedBlock) -> bool:
    """Vrai si le contact couvre toute la face de l'invitée qui touche."""
    face = guest.local_box()
    normal = contact.guest_face.index
    return all(
        contact.rectangle.size(axis) >= face.size(axis) - CONTACT_TOLERANCE_MM
        for axis in range(3)
        if axis != normal
    )


def guess_roles(a: PlacedBlock, b: PlacedBlock) -> tuple[int, int]:
    """Indices (hôte, invitée) parmi ``(a, b)`` ; ordre donné conservé si c'est ambigu.

    Contact : l'invitée est la pièce dont la face qui touche est entièrement couverte (bout de
    traverse contre chant de montant). Chevauchement : l'invitée est la plus mince.
    """
    relation = classify(a, b)
    if isinstance(relation, Overlap):
        swap = a.dimensions.thickness < b.dimensions.thickness
    elif isinstance(relation, Contact):
        reverse = classify(b, a)
        b_covered = _face_covered(relation, b)
        a_covered = isinstance(reverse, Contact) and _face_covered(reverse, a)
        swap = a_covered and not b_covered
    else:
        swap = False
    return (1, 0) if swap else (0, 1)
