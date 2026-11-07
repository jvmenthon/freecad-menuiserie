# SPDX-License-Identifier: LGPL-2.1-or-later
"""Taille initiale d'une nouvelle pièce limitée par les collisions : géométrie pure.

La pièce créée garde ses cotes par défaut tant qu'elle ne chevauche aucune autre pièce ; sinon
chaque cote, dans l'ordre longueur, largeur, épaisseur, est ramenée à la plus grande valeur
entière (en mm) sans chevauchement. Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from freecad.menuiserie.core._validation import MIN_DIMENSION_MM
from freecad.menuiserie.core.part_model import Dimensions

__all__ = ["DimensionsFree", "limit_dimensions"]

DimensionsFree = Callable[[Dimensions], bool]
"""Vrai si la pièce de ces cotes, posée comme la création la pose, ne chevauche aucune pièce."""

_AXES = ("length", "width", "thickness")


def limit_dimensions(dimensions: Dimensions, is_free: DimensionsFree) -> Dimensions:
    """``dimensions`` ramenées au jeu libre : inchangées si la pièce est libre. Une cote dont la
    valeur minimale chevauche déjà une pièce est laissée telle quelle (rien à gagner)."""
    current = dimensions
    for axis in _AXES:
        if is_free(current):
            break
        current = _limited(current, axis, is_free)
    return current


def _limited(dimensions: Dimensions, axis: str, is_free: DimensionsFree) -> Dimensions:
    """Cote ``axis`` ramenée à la plus grande valeur libre (plus grande valeur entière, ou la
    valeur minimale si aucune ne l'est)."""
    low, high = MIN_DIMENSION_MM, float(getattr(dimensions, axis))
    if not is_free(replace(dimensions, **{axis: low})):
        return dimensions
    while high - low > 1.0:
        middle = float(int((low + high) / 2))
        if middle <= low:
            break
        if is_free(replace(dimensions, **{axis: middle})):
            low = middle
        else:
            high = middle
    return replace(dimensions, **{axis: low})
