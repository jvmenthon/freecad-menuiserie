# SPDX-License-Identifier: LGPL-2.1-or-later
"""Orientation initiale d'une pièce accrochée à plusieurs éléments (J6d).

Posée à plat sur la première face, une tablette entre deux joues ne peut pas être étirée : l'écart
tombe sur son épaisseur (notice ``ThicknessGap``). Parmi les 24 orientations d'une boîte, on garde
alors celle qui touche le plus d'éléments, sans avis, avec l'épaisseur la plus verticale et la
longueur étirée de préférence.
"""

from __future__ import annotations

from collections.abc import Sequence

from freecad.menuiserie.core.geometry import Matrix3
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap._frames import anchor_of
from freecad.menuiserie.core.snap._model import (
    FreeTest,
    Orientation,
    SnapNoticeKind,
    SnapResult,
    Target,
    Turn,
)
from freecad.menuiserie.core.snap._solve import snap

_VERTICAL_ROW = 2  # ligne « Z du document » de la rotation repère d'appui → document


def support_rotation(targets: Sequence[Target]) -> Matrix3 | None:
    """Rotation repère d'appui → document de la première cible, ``None`` sans cible."""
    if not targets:
        return None
    return anchor_of(targets[0]).frame.to_transform().rotation


def all_orientations() -> tuple[Orientation, ...]:
    """Les 24 orientations d'une boîte, de l'identité vers les plus tournées (ordre figé)."""
    found = [Orientation()]
    for orientation in found:  # la liste grandit pendant le parcours
        for turn in Turn:
            turned = orientation.turned(turn)
            if turned not in found:
                found.append(turned)
    return tuple(found)


def _vertical_thickness(orientation: Orientation, support: Matrix3) -> float:
    """|cosinus| entre l'axe de l'épaisseur et la verticale du document (1 : épaisseur
    verticale)."""
    matrix = orientation.matrix
    thickness = [matrix[row][2] for row in range(3)]
    up = support[_VERTICAL_ROW]
    return abs(sum(a * b for a, b in zip(thickness, up, strict=True)))


def _score(
    result: SnapResult, orientation: Orientation, support: Matrix3
) -> tuple[int, int, float, int]:
    stretched_length = int(orientation.matrix[2][0] != 0.0)  # L le long de la normale d'appui
    return (
        len(result.used),
        -len(result.notices),
        round(_vertical_thickness(orientation, support), 6),
        stretched_length,
    )


def initial_orientation(
    dimensions: Dimensions, targets: Sequence[Target], *, is_free: FreeTest | None = None
) -> Orientation:
    """Orientation de départ de la pièce : à plat, sauf si deux éléments en vis-à-vis tombent
    sur son épaisseur (jamais étirée) ; une autre orientation les touche alors tous les deux."""
    flat = Orientation()
    support = support_rotation(targets)
    if support is None or len(targets) < 2:
        return flat
    first = snap(dimensions, flat, targets, is_free=is_free)
    if all(notice.kind is not SnapNoticeKind.THICKNESS_GAP for notice in first.notices):
        return flat
    best, best_score = flat, _score(first, flat, support)
    for orientation in all_orientations()[1:]:
        result = snap(dimensions, orientation, targets, is_free=is_free)
        score = _score(result, orientation, support)
        if score > best_score:
            best, best_score = orientation, score
    return best
