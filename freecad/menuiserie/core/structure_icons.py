# SPDX-License-Identifier: LGPL-2.1-or-later
"""Icône de chaque genre de ligne du panneau « Structure » (ADR 0046), sans FreeCAD ni Qt.

Table genre -> nom de fichier de ``resources/icons`` : les icônes des commandes et des objets de
l'atelier sont réutilisées ; seules « Répétition », « Autre objet » et « Quincaillerie » ont été
ajoutées (``tools/generer_icones.py``). Une ligne sans entrée n'a pas d'icône.

L'icône d'une ligne dépend du **type précis** de l'objet (``StructureNode.subtype``) : chaque
assemblage a l'icône de sa commande (``Menuiserie_<JointKind>.svg``), la Distance et la pièce en
forme celle de leur objet de l'arbre natif ; sans type, celle du genre de ligne.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from freecad.menuiserie.core.joints import JointKind
from freecad.menuiserie.core.structure_tree import NodeKind

__all__ = ["DISTANCE_SUBTYPE", "ICON_BY_KIND", "ICON_BY_SUBTYPE", "SHAPED_SUBTYPE", "icon_name"]

DISTANCE_SUBTYPE: Final = "distance"
SHAPED_SUBTYPE: Final = "shaped"

ICON_BY_KIND: Final[Mapping[NodeKind, str]] = {
    NodeKind.FURNITURE: "Menuiserie_Furniture.svg",
    NodeKind.PIECE: "Menuiserie_WoodPart.svg",
    NodeKind.JOINTS: "Menuiserie_MortiseTenon.svg",
    NodeKind.JOINT: "Menuiserie_MortiseTenon.svg",
    NodeKind.HARDWARE: "Menuiserie_Hardware.svg",
    NodeKind.HARDWARE_ITEM: "Menuiserie_Hardware.svg",
    NodeKind.REPEAT: "Menuiserie_Repeat.svg",
    NodeKind.COPY: "Menuiserie_Repeat.svg",
    NodeKind.CUTLIST: "Menuiserie_CutList.svg",
    NodeKind.OTHERS: "Menuiserie_Other.svg",
    NodeKind.OTHER: "Menuiserie_Other.svg",
    NodeKind.LEFTOVERS: "Menuiserie_Other.svg",
    NodeKind.LEFTOVER: "Menuiserie_Other.svg",
}


ICON_BY_SUBTYPE: Final[Mapping[str, str]] = {
    **{kind.value: f"Menuiserie_{kind.value}.svg" for kind in JointKind},
    DISTANCE_SUBTYPE: "Menuiserie_Distance.svg",
    SHAPED_SUBTYPE: "Menuiserie_ShapedPartObject.svg",
}


def icon_name(kind: NodeKind, subtype: str = "") -> str:
    """Nom du fichier d'icône d'une ligne : celui de son type précis ``subtype`` s'il est connu,
    sinon celui du genre ``kind`` (vide : pas d'icône)."""
    return ICON_BY_SUBTYPE.get(subtype) or ICON_BY_KIND.get(kind, "")
