# SPDX-License-Identifier: LGPL-2.1-or-later
"""Disposition des 4 arêtes d'une face vue de l'extérieur, pour un sélecteur visuel (issue #5).

Module privé. La face est vue de face, ``Z`` vers le haut (dessus et dessous : vus de dessus et
de dessous, ``X`` vers la droite). Chaque côté du rectangle est l'arête que la face partage avec
la face voisine indiquée.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.edges._ids import EdgeId, parse_face

__all__ = ["SIDES", "face_sides"]

SIDES: Final = ("top", "left", "right", "bottom")

# Face → voisines en haut, à gauche, à droite, en bas (vue de l'extérieur).
_NEIGHBOURS: Final = {
    "Z+": ("Y+", "X-", "X+", "Y-"),
    "Z-": ("Y-", "X-", "X+", "Y+"),
    "Y-": ("Z+", "X-", "X+", "Z-"),
    "Y+": ("Z+", "X+", "X-", "Z-"),
    "X+": ("Z+", "Y-", "Y+", "Z-"),
    "X-": ("Z+", "Y+", "Y-", "Z-"),
}


def face_sides(face: str) -> tuple[tuple[str, str, EdgeId], ...]:
    """Les 4 côtés de la face désignée par son code (``"Z+"``) ou son nom : ``(côté, face
    voisine, arête)`` dans l'ordre haut, gauche, droite, bas. ``EdgeError`` si la face est
    inconnue."""
    axis = parse_face(face)
    key = axis.value[1] + axis.value[0]
    return tuple(
        (side, neighbour, EdgeId.between(axis, parse_face(neighbour)))
        for side, neighbour in zip(SIDES, _NEIGHBOURS[key], strict=True)
    )
