# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets que la sélection d'une ligne du panneau « Structure » rend transparents (ADR 0046),
sans FreeCAD ni Qt : l'étendue dépend du genre de la ligne."""

from __future__ import annotations

from enum import Enum
from typing import Final

from freecad.menuiserie.core.structure_tree import NodeKind

__all__ = ["SCOPE_BY_KIND", "Scope", "scope_of"]


class Scope(Enum):
    """Ce qu'une ligne met en évidence."""

    OBJECT = "object"  # l'objet affiché de la ligne ; pour un assemblage, ses pièces
    PIECES = "pieces"  # toutes les pièces de l'ensemble et de ses sous-ensembles


SCOPE_BY_KIND: Final = {
    NodeKind.FURNITURE: Scope.PIECES,
    NodeKind.PIECE: Scope.OBJECT,
    NodeKind.COPY: Scope.OBJECT,
    NodeKind.REPEAT: Scope.OBJECT,
    NodeKind.JOINT: Scope.OBJECT,
    NodeKind.HARDWARE_ITEM: Scope.OBJECT,
    NodeKind.LEFTOVER: Scope.OBJECT,
}


def scope_of(kind: str) -> Scope | None:
    """Étendue de la ligne de genre ``kind`` (``NodeKind.value``) ; ``None`` : rien à montrer
    (nœuds repliés, liste de débit, objets d'autres ateliers)."""
    try:
        return SCOPE_BY_KIND.get(NodeKind(kind))
    except ValueError:
        return None
