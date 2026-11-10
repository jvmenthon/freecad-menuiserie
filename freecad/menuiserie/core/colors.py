# SPDX-License-Identifier: LGPL-2.1-or-later
"""Conversion des couleurs de FreeCAD (flottants de 0 à 1) en octets (0 à 255), sans FreeCAD."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

__all__ = ["COLOR_SCALE", "Rgb", "from_bytes", "to_bytes"]

Rgb = tuple[int, int, int]
COLOR_SCALE: Final = 255


def to_bytes(color: Iterable[float]) -> Rgb:
    """Composantes rouge, vert, bleu de 0 à 255 (comparaison sans erreur d'arrondi)."""
    red, green, blue = (round(component * COLOR_SCALE) for component in tuple(color)[:3])
    return red, green, blue


def from_bytes(color: Rgb) -> tuple[float, ...]:
    """Composantes de 0 à 1 de la couleur ``color`` (0 à 255)."""
    return tuple(component / COLOR_SCALE for component in color)
