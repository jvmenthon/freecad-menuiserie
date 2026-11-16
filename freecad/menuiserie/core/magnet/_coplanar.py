# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faces coplanaires montrées pendant un déplacement, une copie ou une répétition (ADR 0058).

Une face de la pièce déplacée (ou d'une copie) est **coplanaire** à une face voisine quand les
deux sont normales au même axe et à la même position sur cet axe, à
:data:`~freecad.menuiserie.core.geometry.CONTACT_TOLERANCE_MM` près, même si les deux faces ne
se recouvrent pas (autre meuble, autre caisson) : c'est ce que jv veut voir pour savoir qu'un
espacement met une copie au ras d'une voisine. Les deux faces sont rendues en plans
(:class:`~freecad.menuiserie.core.magnet.Guide`) pour être dessinées comme les guides aimantés.
"""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from typing import Final

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Box
from freecad.menuiserie.core.magnet._model import Guide, GuideKind

MAX_COPLANAR: Final = 64  # faces montrées au plus : au-delà, le dessin n'aide plus

__all__ = ["MAX_COPLANAR", "PlaneIndex", "box_faces", "overlaps"]


def box_faces(box: Box, faces: Iterable[tuple[int, bool]]) -> tuple[Guide, ...]:
    """Plans des faces ``faces`` de ``box`` : (axe, face de fin ?) ; normale sortante."""
    found = []
    for axis, at_end in faces:
        level = box.hi(axis) if at_end else box.lo(axis)
        found.append(
            Guide(GuideKind.PLANE, box.with_range(axis, level, level), axis, 1 if at_end else -1)
        )
    return tuple(found)


def overlaps(face: Guide, other: Guide, tolerance: float = CONTACT_TOLERANCE_MM) -> bool:
    """Vrai si les étendues de ``face`` et ``other`` se recouvrent (ou se touchent) sur les axes
    autres que celui de ``face`` : une voisine qui recouvre la face la montre déjà."""
    return all(
        other.extent.lo(i) <= face.extent.hi(i) + tolerance
        and other.extent.hi(i) >= face.extent.lo(i) - tolerance
        for i in range(3)
        if i != face.axis
    )


class PlaneIndex:
    """Plans voisins rangés par axe et par position, pour trouver vite ceux d'une position.

    Seuls les guides :attr:`GuideKind.PLANE` de ``guides`` sont gardés (droites et sommets ne
    sont pas des faces)."""

    def __init__(self, guides: Iterable[Guide]) -> None:
        by_axis: list[list[tuple[float, int, Guide]]] = [[], [], []]
        for index, guide in enumerate(guides):
            if guide.kind is GuideKind.PLANE and guide.axis is not None:
                by_axis[guide.axis].append((guide.position(guide.axis), index, guide))
        for planes in by_axis:
            planes.sort(key=lambda item: item[:2])
        self._planes = by_axis
        self._positions = [[item[0] for item in planes] for planes in by_axis]

    def at(
        self, axis: int, position: float, tolerance: float = CONTACT_TOLERANCE_MM
    ) -> list[Guide]:
        """Plans normaux à ``axis`` à ``position`` ± ``tolerance``, dans l'ordre des positions."""
        positions = self._positions[axis]
        first = bisect.bisect_left(positions, position - tolerance)
        last = bisect.bisect_right(positions, position + tolerance)
        return [item[2] for item in self._planes[axis][first:last]]

    def coplanar(
        self,
        faces: Sequence[Guide],
        axes: Iterable[int] = (0, 1, 2),
        tolerance: float = CONTACT_TOLERANCE_MM,
    ) -> tuple[Guide, ...]:
        """Faces ``faces`` (plans) qui ont un plan voisin coplanaire sur un axe de ``axes``, et ces
        plans voisins, sans doublon ; au plus :data:`MAX_COPLANAR` (les premières faces d'abord).
        Une face qui n'est pas un plan est ignorée."""
        wanted = set(axes)
        shown: dict[Guide, None] = {}
        for face in faces:
            if face.kind is not GuideKind.PLANE or face.axis not in wanted:
                continue
            neighbors = self.at(face.axis, face.position(face.axis), tolerance)
            if not neighbors:
                continue
            shown.setdefault(face)
            for neighbor in neighbors:
                shown.setdefault(neighbor)
            if len(shown) >= MAX_COPLANAR:
                break
        return tuple(shown)[:MAX_COPLANAR]
