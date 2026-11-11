# SPDX-License-Identifier: LGPL-2.1-or-later
"""Chaîne d'ensembles qui contiennent un objet, pour la sélection dans la vue 3D (ADR 0048)."""

from __future__ import annotations

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import furniture_of, is_furniture
from freecad.menuiserie.features.furniture_container import carried_furniture
from freecad.menuiserie.features.machined_part import blank_of

__all__ = ["chain_of", "normalized"]


def _piece_of(obj: DocumentObject) -> DocumentObject | None:
    """Objet qui porte le lien ``Furniture`` : l'ensemble lui-même, la brute d'une pièce usinée
    ou la pièce ; ``None`` pour un objet étranger à l'atelier."""
    if is_furniture(obj):
        return obj
    try:
        return blank_of(obj)
    except TypeError:
        return obj if furniture_of(obj) is not None else None


def normalized(obj: DocumentObject) -> DocumentObject:
    """Objet que la sélection désigne : l'ensemble qu'un Std Part d'ensemble porte, la brute d'une
    pièce usinée, sinon ``obj``."""
    carried = carried_furniture(obj)
    if carried is not None:
        return carried
    return _piece_of(obj) or obj


def chain_of(obj: DocumentObject) -> list[DocumentObject]:
    """Ensembles qui contiennent ``obj`` (du plus haut au plus bas niveau) puis ``obj`` normalisé
    (brute ou ensemble) ; vide si ``obj`` n'est membre d'aucun ensemble."""
    piece = _piece_of(obj)
    if piece is None:
        return []
    parents: list[DocumentObject] = []
    current = piece
    while (parent := furniture_of(current)) is not None and parent not in [piece, *parents]:
        parents.append(parent)
        current = parent
    return [*reversed(parents), piece] if parents else []
