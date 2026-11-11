# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pièces d'équerre proches mais qui ne se touchent pas : écart à combler avant un assemblage.

Deux pièces sont « proches » quand leurs boîtes ne sont écartées que sur un seul axe, de moins de
:data:`NEAR_GAP_MM`, et se recouvrent franchement sur les deux autres : les rapprocher de cet
écart les met en contact par une face (et non par une arête). :func:`near_gap` mesure cet écart,
sans rien décider : déplacer une pièce ou l'agrandir jusqu'au contact est l'affaire de
``features/near_gap`` (ADR 0039). Toutes les longueurs sont en mm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import (
    CONTACT_TOLERANCE_MM,
    JointError,
    PlacedBlock,
    is_square,
    moved_box,
    relative_axes,
    relative_transform,
)

__all__ = ["NEAR_GAP_MM", "NearGap", "near_gap"]

NEAR_GAP_MM: Final = 20.0  # écart au-delà duquel les pièces sont jugées volontairement écartées


@dataclass(frozen=True)
class NearGap:
    """Écart entre une pièce de référence ``a`` et une pièce ``b`` proche, sur un axe.

    ``axis`` (0 = X…) est un axe du repère de ``a`` ; ``side`` vaut +1 si ``b`` est du côté +
    de ``a`` sur cet axe, -1 sinon ; ``distance`` est l'écart (mm, > 0). ``b_axis`` est l'axe du
    repère de ``b`` parallèle à ``axis`` et ``b_low`` vaut ``True`` si la face de ``b`` tournée
    vers ``a`` est celle de coordonnée 0 sur cet axe (la face du bas), ``False`` si c'est la
    face du haut."""

    axis: int
    side: int
    distance: float
    b_axis: int
    b_low: bool


def near_gap(a: PlacedBlock, b: PlacedBlock, max_gap: float = NEAR_GAP_MM) -> NearGap | None:
    """Écart de ``b`` à ``a`` si les pièces, d'équerre, ne sont écartées que sur un axe de moins
    de ``max_gap`` mm et se recouvrent sur les deux autres ; sinon ``None`` (déjà en contact ou
    chevauchées, trop loin, en biais, arête contre arête)."""
    if not is_square(a, b):
        return None
    transform = relative_transform(a, b)
    a_box = a.local_box()
    b_box = moved_box(b.local_box(), transform)
    overlaps = [min(a_box.hi(i), b_box.hi(i)) - max(a_box.lo(i), b_box.lo(i)) for i in range(3)]
    apart = [i for i, overlap in enumerate(overlaps) if overlap < -CONTACT_TOLERANCE_MM]
    others = [overlap for i, overlap in enumerate(overlaps) if i not in apart]
    if len(apart) != 1 or not all(overlap > CONTACT_TOLERANCE_MM for overlap in others):
        return None
    axis = apart[0]
    distance = -overlaps[axis]
    if distance > max_gap:
        return None
    side = 1 if b_box.center(axis) > a_box.center(axis) else -1
    try:
        directions = relative_axes(a, b)
    except JointError:  # défense : is_square l'a déjà admis
        return None
    b_axis = next(j for j, direction in enumerate(directions) if direction.index == axis)
    facing = -side * directions[b_axis].sign  # sens, sur l'axe de b, de la face tournée vers a
    return NearGap(axis, side, distance, b_axis, facing < 0)
