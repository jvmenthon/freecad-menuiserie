# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces qui suivent la face haute d'une pièce dont l'épaisseur change (issue #133).

Le repère d'une pièce a son origine sur sa face basse : changer l'épaisseur déplace la face haute
(z = épaisseur) et, avec elle, le contact des pièces posées dessus. Ces pièces suivent alors la
face, du même écart, pour que leurs assemblages tiennent. Logique pure : aucun import FreeCAD.
"""

from __future__ import annotations

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    PlacedBlock,
    Vec3,
    moved_box,
    relative_transform,
)

__all__ = ["follow_shift", "touches_raised_face"]

_THICKNESS_AXIS = 2


def touches_raised_face(changed: PlacedBlock, other: PlacedBlock) -> bool:
    """Vrai si ``other`` repose contre la face haute de ``changed`` (prise à son épaisseur
    d'avant) : sa face basse y est, au contact près, et les deux se recouvrent sur la face.
    Faux pour une pièce oblique par rapport à ``changed``."""
    try:
        box = moved_box(other.local_box(), relative_transform(changed, other))
    except ValueError:
        return False
    top = changed.dimensions.thickness
    if abs(box.lo(_THICKNESS_AXIS) - top) > CONTACT_TOLERANCE_MM:
        return False
    sizes = (changed.dimensions.length, changed.dimensions.width)
    return all(
        min(box.hi(i), sizes[i]) - max(box.lo(i), 0.0) > CONTACT_TOLERANCE_MM for i in range(2)
    )


def follow_shift(changed: PlacedBlock, delta: float) -> Vec3:
    """Translation (repère du document) de ``delta`` mm le long de l'épaisseur de ``changed``."""
    return changed.placement.rotate(Vec3(0.0, 0.0, delta))
