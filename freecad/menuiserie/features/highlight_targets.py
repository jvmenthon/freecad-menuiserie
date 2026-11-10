# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets affichés à mettre en évidence pour une ligne du panneau « Structure » (ADR 0046).

Lecture seule. Ce sont les objets visibles (la pièce usinée à la place de sa brute, comme
``shown_object``) : la pièce de la ligne, les pièces d'un ensemble, ou les deux pièces d'un
assemblage ou d'une quincaillerie.
"""

from __future__ import annotations

from freecad.menuiserie.core.structure_highlight import Scope
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture_view import pieces_below, shown_object
from freecad.menuiserie.features.joints.base import is_joint

__all__ = ["highlighted_objects"]


def highlighted_objects(obj: DocumentObject, scope: Scope) -> list[DocumentObject]:
    """Objets affichés que la ligne de ``obj`` met en évidence, sans doublon."""
    if scope is Scope.PIECES:
        found = [shown_object(piece) for piece in pieces_below(obj)]
    elif is_joint(obj):
        found = [shown_object(p) for p in (obj.HostPart, obj.GuestPart) if p is not None]
    else:
        found = [shown_object(obj)]
    return list({item.Name: item for item in found}.values())
