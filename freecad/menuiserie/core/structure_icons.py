# SPDX-License-Identifier: LGPL-2.1-or-later
"""Icône de chaque genre de ligne du panneau « Structure » (ADR 0046), sans FreeCAD ni Qt.

Table genre -> nom de fichier de ``resources/icons`` : les icônes des commandes et des objets de
l'atelier sont réutilisées ; seules « Répétition » et « Autre objet » ont été ajoutées
(``tools/generer_icones.py``). Une ligne sans entrée n'a pas d'icône.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from freecad.menuiserie.core.structure_tree import NodeKind

__all__ = ["ICON_BY_KIND", "icon_name"]

ICON_BY_KIND: Final[Mapping[NodeKind, str]] = {
    NodeKind.FURNITURE: "Menuiserie_Furniture.svg",
    NodeKind.PIECE: "Menuiserie_WoodPart.svg",
    NodeKind.JOINTS: "Menuiserie_MortiseTenon.svg",
    NodeKind.JOINT: "Menuiserie_MortiseTenon.svg",
    NodeKind.REPEAT: "Menuiserie_Repeat.svg",
    NodeKind.COPY: "Menuiserie_Repeat.svg",
    NodeKind.CUTLIST: "Menuiserie_CutList.svg",
    NodeKind.OTHERS: "Menuiserie_Other.svg",
    NodeKind.OTHER: "Menuiserie_Other.svg",
    NodeKind.LEFTOVERS: "Menuiserie_Other.svg",
    NodeKind.LEFTOVER: "Menuiserie_Other.svg",
}


def icon_name(kind: NodeKind) -> str:
    """Nom du fichier d'icône du genre ``kind`` (vide : pas d'icône)."""
    return ICON_BY_KIND.get(kind, "")
