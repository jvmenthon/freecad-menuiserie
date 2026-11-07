# SPDX-License-Identifier: LGPL-2.1-or-later
"""Disposition du perçage LR32 d'après les pièces voisines du côté (module privé).

Le côté est debout (axe local vertical, épaisseur horizontale). Les pièces voisines posées contre
une de ses faces le limitent : une pièce **assemblée** au côté (fond, dessus, séparation) borne la
zone percée, une pièce **libre** (tablette) reçoit des taquets sous elle. Les hauteurs sont
comptées vers le haut depuis le bas du côté. Calculs dans le repère du côté.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import (
    Box,
    JointError,
    PlacedBlock,
    Vec3,
    is_square,
    moved_box,
    relative_transform,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP

__all__ = [
    "NOT_UPRIGHT",
    "Layout",
    "Neighbor",
    "choose_face",
    "facing_side",
    "free_window",
    "picked_choice",
    "pin_rows",
    "touching_boxes",
    "upright",
]

_TOUCH_BELOW_MM: Final = 0.5  # la voisine peut entrer de 0,5 mm dans le côté
_TOUCH_ABOVE_MM: Final = 1.0  # ou rester à 1 mm de sa face
_OVERLAP_MM: Final = 1e-6
_DOWN: Final = Vec3(0.0, 0.0, -1.0)
_TILT_TOLERANCE: Final = 1e-3

NOT_UPRIGHT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Le perçage se pose sur un côté debout : son épaisseur doit être horizontale et sa longueur "
    "ou sa largeur verticale.",
)


@dataclass(frozen=True)
class Neighbor:
    """Pièce voisine du côté : ``fixed`` si un assemblage la relie au côté."""

    block: PlacedBlock
    fixed: bool


@dataclass(frozen=True)
class Layout:
    """Face percée (``+1`` : +Z local, ``-1`` : -Z), hauteurs des rangs de trous depuis le bas du
    côté et rangs (depuis 0) qui portent des taquets."""

    face_sign: float
    heights: tuple[float, ...]
    pin_rows: tuple[int, ...]


def _overlap(low_a: float, high_a: float, low_b: float, high_b: float) -> bool:
    return min(high_a, high_b) - max(low_a, low_b) > _OVERLAP_MM


def side_boxes(
    host: PlacedBlock, neighbors: tuple[Neighbor, ...], vertical: int
) -> list[tuple[Box, bool]]:
    """Boîtes (repère du côté) des voisines d'équerre qui recouvrent le côté dans son plan."""
    box = host.local_box()
    horizontal = 1 - vertical
    found = []
    for neighbor in neighbors:
        if not is_square(host, neighbor.block):
            continue
        other = moved_box(neighbor.block.local_box(), relative_transform(host, neighbor.block))
        if _overlap(
            box.lo(vertical), box.hi(vertical), other.lo(vertical), other.hi(vertical)
        ) and (
            _overlap(
                box.lo(horizontal), box.hi(horizontal), other.lo(horizontal), other.hi(horizontal)
            )
        ):
            found.append((other, neighbor.fixed))
    return found


def touching_boxes(
    boxes: list[tuple[Box, bool]], host: PlacedBlock, sign: float
) -> list[tuple[Box, bool]]:
    """Voisines posées contre la face ``sign`` du côté (et qui en sortent)."""
    box = host.local_box()
    plane = box.hi(2) if sign > 0 else box.lo(2)
    found = []
    for other, fixed in boxes:
        if sign > 0:
            touches = plane - _TOUCH_BELOW_MM <= other.lo(2) <= plane + _TOUCH_ABOVE_MM
            outside = other.hi(2) > plane + _TOUCH_ABOVE_MM
        else:
            touches = plane - _TOUCH_ABOVE_MM <= other.hi(2) <= plane + _TOUCH_BELOW_MM
            outside = other.lo(2) < plane - _TOUCH_ABOVE_MM
        if touches and outside:
            found.append((other, fixed))
    return found


def choose_face(face: str, host: PlacedBlock, boxes: list[tuple[Box, bool]]) -> float:
    """Face percée : celle demandée, sinon la face intérieure : celle contre laquelle sont
    posées le plus de pièces, puis celle qui regarde une autre pièce (l'autre côté)."""
    if face != "auto":
        return 1.0 if face == "plus" else -1.0
    plane_hi, plane_lo = host.local_box().hi(2), host.local_box().lo(2)

    def score(sign: float) -> tuple[int, int]:
        facing = sum(
            1
            for other, _fixed in boxes
            if (
                other.lo(2) > plane_hi + _TOUCH_ABOVE_MM
                if sign > 0
                else other.hi(2) < plane_lo - _TOUCH_ABOVE_MM
            )
        )
        return len(touching_boxes(boxes, host, sign)), facing

    return 1.0 if score(1.0) >= score(-1.0) else -1.0


def heights_of(box: Box, bottom: float, down: float, vertical: int) -> tuple[float, float]:
    """Intervalle de hauteurs (depuis le bas du côté) qu'occupe ``box``."""
    first, second = ((bottom - box.lo(vertical)) * down, (bottom - box.hi(vertical)) * down)
    return min(first, second), max(first, second)


def free_window(
    fixed: list[tuple[float, float]], total: float, target: float = 0.0
) -> tuple[float, float]:
    """Intervalle libre de ``[0, total]`` entre les zones occupées par les pièces assemblées :
    celui qui contient la hauteur ``target`` (point cliqué), sinon le plus grand (le plus bas en
    cas d'égalité) ; ``(0, 0)`` si tout est occupé."""
    gaps = []
    cursor = 0.0
    for low, high in sorted((max(low, 0.0), min(high, total)) for low, high in fixed):
        if low > cursor:
            gaps.append((cursor, low))
        cursor = max(cursor, high)
    if cursor < total:
        gaps.append((cursor, total))
    if not gaps:
        return 0.0, 0.0
    if target > 0:
        for low, high in gaps:
            if low <= target <= high:
                return low, high
    return max(gaps, key=lambda gap: (round(gap[1] - gap[0], 6), -gap[0]))


def pin_rows(
    heights: tuple[float, ...], shelves: list[tuple[float, float]], radius: float
) -> tuple[int, ...]:
    """Rang du taquet sous chaque tablette : le plus haut dont le dessus (centre plus rayon) ne
    dépasse pas le dessous de la tablette."""
    rows = set()
    for bottom, _top in shelves:
        below = [i for i, height in enumerate(heights) if height + radius <= bottom + 0.5]
        if below:
            rows.add(below[-1])
    return tuple(sorted(rows))


def facing_side(
    host: PlacedBlock, face: str, others: tuple[PlacedBlock, ...]
) -> tuple[int, str, float] | None:
    """Côté debout parallèle le plus proche en face de la face percée ``face`` (``plus`` ou
    ``minus``) de ``host`` et qui le recouvre au moins de moitié : (indice dans ``others``, sa face
    tournée vers ``host``, hauteur de son bas au-dessus du bas de ``host``) ; ``None`` sans côté."""
    vertical, down = upright(host)
    horizontal = 1 - vertical
    box = host.local_box()
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    sign = 1.0 if face == "plus" else -1.0
    best: tuple[float, int, str, float] | None = None
    for index, other in enumerate(others):
        if not is_square(host, other):
            continue
        try:
            upright(other)
        except JointError:
            continue
        transform = relative_transform(host, other)
        moved = moved_box(other.local_box(), transform)
        if moved.size(2) >= min(moved.size(vertical), moved.size(horizontal)):
            continue  # pas parallèle au côté
        gap = moved.lo(2) - box.hi(2) if sign > 0 else box.lo(2) - moved.hi(2)
        if gap <= 0 or not all(_half_cover(box, moved, axis) for axis in (vertical, horizontal)):
            continue
        if best is None or gap < best[0]:
            toward = transform.rotate(Vec3(0.0, 0.0, 1.0)).z * -sign
            low, _high = heights_of(moved, bottom, down, vertical)
            best = (gap, index, "plus" if toward > 0 else "minus", low)
    return None if best is None else best[1:]


def _half_cover(box: Box, other: Box, axis: int) -> bool:
    common = min(box.hi(axis), other.hi(axis)) - max(box.lo(axis), other.lo(axis))
    return common >= min(box.size(axis), other.size(axis)) / 2


def picked_choice(host: PlacedBlock, point: Vec3) -> tuple[str, float]:
    """Face (``plus`` ou ``minus``) et hauteur depuis le bas du côté d'un point cliqué sur le
    côté (repère du côté) : le perçage se fait sur cette face, dans la zone de ce point."""
    vertical, down = upright(host)
    box = host.local_box()
    bottom = box.hi(vertical) if down > 0 else box.lo(vertical)
    near_plus = abs(point.z - box.hi(2)) <= abs(point.z - box.lo(2))
    height = (bottom - point.component(vertical)) * down
    return ("plus" if near_plus else "minus"), max(height, 0.0)


def upright(host: PlacedBlock) -> tuple[int, float]:
    """(axe local vertical, sens vers le bas sur cet axe) d'un côté debout, sinon refus."""
    down = host.placement.inverse().rotate(_DOWN)
    vertical = 0 if abs(down.component(0)) > abs(down.component(1)) else 1
    if abs(abs(down.component(vertical)) - 1.0) > _TILT_TOLERANCE:
        raise JointError(NOT_UPRIGHT, {})
    return vertical, 1.0 if down.component(vertical) > 0 else -1.0
