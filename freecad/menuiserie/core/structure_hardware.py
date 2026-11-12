# SPDX-License-Identifier: LGPL-2.1-or-later
"""Quelle ligne du panneau « Structure » range un type d'assemblage (ADR 0046, ADR 0033), sans
FreeCAD.

Table pure : un type d'assemblage est de la **quincaillerie** quand c'est un objet du commerce
posé entre les pièces (pied de caisson, taquet de tablette LR32, coulisse, charnière) ; sinon
c'est un **assemblage** (tenon-mortaise, rainure-languette, feuillure, mi-bois, queue d'aronde,
onglet, et les fixations tourillon, faux tenon et biscuit, que jv veut sous « Assemblages » même si
l'ADR 0033 les pose depuis le catalogue). Les Distances sont des assemblages.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.joints import JointKind

__all__ = ["HARDWARE_KINDS", "WOOD_JOINT_KINDS", "is_hardware_kind"]

HARDWARE_KINDS: Final = frozenset(
    {
        JointKind.FOOT,
        JointKind.SHELF_PINS,
        JointKind.DRAWER_SLIDE,
        JointKind.HINGE,
    }
)
WOOD_JOINT_KINDS: Final = frozenset(JointKind) - HARDWARE_KINDS


def is_hardware_kind(kind: JointKind) -> bool:
    """Vrai si ``kind`` se range sous « Quincaillerie », faux sous « Assemblages »."""
    return kind in HARDWARE_KINDS
