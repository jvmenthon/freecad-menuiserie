# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boîte qui contient les futurs membres d'un ensemble (``build_furniture``).

Les cotes d'une pièce (de bois ou en bois) sont celles de ``dimensions_of`` : pour une pièce en
bois, son encombrement.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.furniture import FurnitureBox
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture, origin_of
from freecad.menuiserie.features.i18n import translated_errors
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["corners_of", "enclosing"]


def corners_of(obj: DocumentObject) -> list[Vec3]:
    """Sommets de la boîte d'un membre dans le repère de son conteneur."""
    if is_furniture(obj):
        low = origin_of(obj)
        sizes = (obj.Width.Value, obj.Depth.Value, obj.Height.Value)
        return [low, Vec3(low.x + sizes[0], low.y + sizes[1], low.z + sizes[2])]
    with translated_errors():
        size = dimensions_of(obj)
    transform = rigid_transform(obj.Placement)
    return [
        transform.apply(Vec3(x, y, z))
        for x in (0.0, size.length)
        for y in (0.0, size.width)
        for z in (0.0, size.thickness)
    ]


def enclosing(objects: Sequence[DocumentObject]) -> tuple[FurnitureBox, Vec3]:
    """Boîte qui contient les membres (cotes et coin minimal), arrondie au millionième de mm."""
    points = [point for obj in objects for point in corners_of(obj)]
    low = [round(min(p.component(i) for p in points), 6) + 0.0 for i in range(3)]  # pas de -0
    high = [round(max(p.component(i) for p in points), 6) for i in range(3)]
    with translated_errors():
        box = FurnitureBox(*(hi - lo for lo, hi in zip(low, high, strict=True)))
    return box, Vec3.of(low)
