# SPDX-License-Identifier: LGPL-2.1-or-later
"""Quelle ligne du panneau « Structure » range un type d'assemblage (ADR 0046, ADR 0033), sans
FreeCAD.

Table pure : un type d'assemblage est de la **quincaillerie** quand l'ADR 0033 le pose depuis une
référence du catalogue du commerce (tourillon, faux tenon, biscuit, pied de caisson, taquet de
tablette LR32, coulisse) ; sinon c'est un **assemblage** taillé dans le bois (tenon-mortaise,
rainure-languette, feuillure, mi-bois, queue d'aronde, onglet). Les Distances sont des
assemblages (aucune quincaillerie).
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.joints import JointKind

__all__ = ["HARDWARE_KINDS", "WOOD_JOINT_KINDS", "is_hardware_kind"]

HARDWARE_KINDS: Final = frozenset(
    {
        JointKind.DOWELS,
        JointKind.LOOSE_TENON,
        JointKind.BISCUIT,
        JointKind.FOOT,
        JointKind.SHELF_PINS,
        JointKind.DRAWER_SLIDE,
    }
)
WOOD_JOINT_KINDS: Final = frozenset(JointKind) - HARDWARE_KINDS


def is_hardware_kind(kind: JointKind) -> bool:
    """Vrai si ``kind`` se range sous « Quincaillerie », faux sous « Assemblages »."""
    return kind in HARDWARE_KINDS
