# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces affichées par le panneau « Répéter » (jv, 2026-11-11) : les copies en transparence, les
pièces d'origine en transparence et teintes, le temps du panneau (:mod:`base`)."""

from __future__ import annotations

from collections.abc import Iterable

from freecad.menuiserie.features.distance import is_distance
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.furniture_bindings import members_of
from freecad.menuiserie.features.furniture_view import shown_object
from freecad.menuiserie.features.repeat import copies_of

__all__ = ["copy_parts", "shown_parts"]


def shown_parts(objects: Iterable[DocumentObject]) -> list[DocumentObject]:
    """Objets affichés des pièces ``objects`` (pièce usinée si elle a des assemblages) ; un
    ensemble donne ceux de ses membres, sous-ensembles compris. Les distances sont ignorées."""
    found: dict[str, DocumentObject] = {}
    pending = list(objects)
    while pending:
        obj = pending.pop()
        if is_furniture(obj):
            pending.extend(members_of(obj))
        elif not is_distance(obj):
            shown = shown_object(obj)
            found.setdefault(shown.Name, shown)
    return list(found.values())


def copy_parts(repeat: DocumentObject | None) -> list[DocumentObject]:
    """Objets affichés des copies de ``repeat`` (aucun sans répétition), membres des ensembles
    copiés compris."""
    return [] if repeat is None else shown_parts(copies_of(repeat))
