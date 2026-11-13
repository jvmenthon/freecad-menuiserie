# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cotes de détail et angles de la face du plan de l'ouvrage (retour de jv du 2026-11-13).

Sous les cotes hors tout, une chaîne de cotes donne les positions où commence ou finit chaque
pièce, en largeur et en hauteur : épaisseur d'un plateau, débord d'une pièce, étendue d'une
pièce en biais. Les points trop proches pour que leur cote se lise sont fusionnés. Une pièce en
biais sur la face porte son angle avec l'horizontale.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from typing import Final

__all__ = ["chain_segments", "slant_angle"]

MIN_SLANT_DEG: Final = 0.5  # en deçà (ou au-delà de 90 - ce seuil), la pièce est d'équerre
_SAME_MM: Final = 0.05


def chain_segments(points: Iterable[float], min_gap: float) -> list[tuple[float, float]]:
    """Segments successifs d'une chaîne de cotes passant par ``points`` (mm réels) : points triés,
    ceux à moins de ``min_gap`` du précédent gardé fusionnés (le dernier point, l'extrémité, est
    toujours gardé). Vide s'il n'y a qu'un segment : la cote hors tout le donne déjà."""
    ordered = sorted({round(value, 3) for value in points})
    if len(ordered) < 2:
        return []
    kept = [ordered[0]]
    for value in ordered[1:-1]:
        if value - kept[-1] >= min_gap and ordered[-1] - value >= min_gap:
            kept.append(value)
    kept.append(ordered[-1])
    segments = [(a, b) for a, b in itertools.pairwise(kept) if b - a > _SAME_MM]
    return segments if len(segments) > 1 else []


def slant_angle(horizontal: float, vertical: float) -> float | None:
    """Angle (degrés, de 0 à 90) avec l'horizontale de la feuille d'une direction vue de
    composantes ``horizontal`` et ``vertical`` ; ``None`` si elle est d'équerre (horizontale,
    verticale) ou perpendiculaire à la feuille."""
    if math.hypot(horizontal, vertical) < 1e-6:
        return None
    angle = math.degrees(math.atan2(abs(vertical), abs(horizontal)))
    if angle < MIN_SLANT_DEG or angle > 90.0 - MIN_SLANT_DEG:
        return None
    return angle
