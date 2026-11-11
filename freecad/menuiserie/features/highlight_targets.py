# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets affichés à mettre en évidence pour une ligne du panneau « Structure » (ADR 0046).

Lecture seule. Ce sont les objets visibles (la pièce usinée à la place de sa brute, comme
``shown_object``) : la pièce de la ligne, les pièces d'un ensemble, les copies d'une répétition,
ou les deux pièces d'un assemblage ou d'une quincaillerie.
"""

from __future__ import annotations

from freecad.menuiserie.core.structure_highlight import Scope
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_view import pieces_below, shown_object
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.repeat import copies_of, is_inner_copy

__all__ = ["highlighted_objects"]


def _copies_of(repeat: DocumentObject) -> list[DocumentObject]:
    """Copies de premier niveau de la répétition ``repeat`` (celles de ses membres copiés sont
    sous leur ensemble copie, dont les pièces sont mises en évidence)."""
    return [copy for copy in copies_of(repeat) if not is_inner_copy(copy)]


def _shown_by(copy: DocumentObject) -> list[DocumentObject]:
    """Objets affichés d'une copie : elle-même, ou les pièces d'un ensemble copie."""
    if is_furniture(copy):
        return [shown_object(piece) for piece in pieces_below(copy)]
    return [shown_object(copy)]


def highlighted_objects(obj: DocumentObject, scope: Scope) -> list[DocumentObject]:
    """Objets affichés que la ligne de ``obj`` met en évidence, sans doublon."""
    if scope is Scope.COPIES:
        found = [shown for copy in _copies_of(obj) for shown in _shown_by(copy)]
    elif scope is Scope.PIECES or is_furniture(obj):
        found = [shown_object(piece) for piece in pieces_below(obj)]
    elif is_joint(obj):
        found = [shown_object(p) for p in (obj.HostPart, obj.GuestPart) if p is not None]
    else:
        found = [shown_object(obj)]
    return list({item.Name: item for item in found}.values())
