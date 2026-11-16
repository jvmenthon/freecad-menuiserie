# SPDX-License-Identifier: LGPL-2.1-or-later
"""Disposition des 4 arêtes d'une face vue de l'extérieur, pour un sélecteur visuel (issue #5).

Module privé. La face est vue de face, ``Z`` vers le haut (dessus et dessous : vus de dessus et
de dessous, ``X`` vers la droite). Chaque côté du rectangle est l'arête que la face partage avec
la face voisine indiquée.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Final

from freecad.menuiserie.core.edges._ids import (
    FACE_CODES,
    EdgeId,
    face_code,
    parse_edge,
    parse_face,
)

__all__ = ["SIDES", "face_sides", "faces_covering"]

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
    key = face_code(axis)
    return tuple(
        (side, neighbour, EdgeId.between(axis, parse_face(neighbour)))
        for side, neighbour in zip(SIDES, _NEIGHBOURS[key], strict=True)
    )


def faces_covering(codes: Collection[str]) -> tuple[str, ...]:
    """Peu de faces dont les contours contiennent toutes les arêtes ``codes`` (choix glouton : la
    face qui en porte le plus d'abord, à égalité dans l'ordre dessus, dessous, avant, arrière,
    gauche, droite) : les sélecteurs à afficher pour des arêtes déjà profilées. Vide sans arête ;
    ``EdgeError`` pour un code inconnu."""
    remaining = {edge.code: edge for edge in map(parse_edge, codes)}
    faces: list[str] = []
    while remaining:
        counts = {
            code: sum(code in (face_code(e.first), face_code(e.second)) for e in remaining.values())
            for code in FACE_CODES
        }
        best = max(FACE_CODES, key=lambda code: counts[code])
        faces.append(best)
        remaining = {
            key: edge
            for key, edge in remaining.items()
            if best not in (face_code(edge.first), face_code(edge.second))
        }
    return tuple(faces)
