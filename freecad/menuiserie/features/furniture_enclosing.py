# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boîte qui contient les futurs membres d'un ensemble (``build_furniture``).

Les cotes d'une pièce (de bois ou en bois) sont celles de ``dimensions_of`` : pour une pièce en
bois, son encombrement.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.furniture import FurnitureBox
from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture, origin_of
from freecad.menuiserie.features.furniture_container import std_part_of
from freecad.menuiserie.features.i18n import translated_errors
from freecad.menuiserie.features.solids import rigid_transform
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["corner_box", "corners_of", "enclosing"]


def corners_of(obj: DocumentObject) -> list[Vec3]:
    """Sommets de la boîte d'un membre dans le repère de son conteneur."""
    if is_furniture(obj):
        # Sous-ensemble : sa boîte tournée avec son Std Part (ADR 0049), pas seulement son coin.
        low = origin_of(obj)
        high = low + Vec3(obj.Width.Value, obj.Depth.Value, obj.Height.Value)
        part = std_part_of(obj)
        transform = RigidTransform.identity() if part is None else rigid_transform(part.Placement)
        return [
            transform.apply(Vec3(x, y, z))
            for x in (low.x, high.x)
            for y in (low.y, high.y)
            for z in (low.z, high.z)
        ]
    with translated_errors():
        size = dimensions_of(obj)
    transform = rigid_transform(obj.Placement)
    return [
        transform.apply(Vec3(x, y, z))
        for x in (0.0, size.length)
        for y in (0.0, size.width)
        for z in (0.0, size.thickness)
    ]


def corner_box(points: Sequence[Vec3]) -> Box | None:
    """Boîte alignée qui contient ``points``, arrondie au millionième de mm ; ``None`` sans
    point."""
    if not points:
        return None
    return Box.from_ranges(
        [
            (
                round(min(p.component(i) for p in points), 6) + 0.0,  # pas de -0
                round(max(p.component(i) for p in points), 6),
            )
            for i in range(3)
        ]
    )


def enclosing(objects: Sequence[DocumentObject]) -> tuple[FurnitureBox, Vec3]:
    """Boîte qui contient les membres (cotes et coin minimal), arrondie au millionième de mm.
    ``ValueError`` sans membre."""
    box = corner_box([point for obj in objects for point in corners_of(obj)])
    if box is None:
        raise ValueError("enclosing() : aucun membre")
    with translated_errors():
        size = FurnitureBox(*(box.size(i) for i in range(3)))
    return size, box.min
