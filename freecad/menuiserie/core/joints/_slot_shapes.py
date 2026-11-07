# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contours arrondis des logements de faux tenons et de biscuits (plans (u, v), en mm)."""

from __future__ import annotations

import math
from typing import Final

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM

__all__ = ["Point2", "half_stadium", "rounded_rectangle"]

Point2 = tuple[float, float]
_ARC_STEPS: Final = 8  # segments par quart de cercle des bouts arrondis


def rounded_rectangle(width: float, height: float, radius: float) -> tuple[Point2, ...]:
    """Contour (u, v) d'un rectangle à coins arrondis centré à l'origine ; un rayon égal à la
    moitié du plus petit côté donne un stade (bouts demi-ronds)."""
    radius = min(radius, width / 2, height / 2)
    reach_u, reach_v = width / 2 - radius, height / 2 - radius
    points: list[Point2] = []
    for center_u, center_v, start in (
        (reach_u, reach_v, 0.0),
        (-reach_u, reach_v, 90.0),
        (-reach_u, -reach_v, 180.0),
        (reach_u, -reach_v, 270.0),
    ):
        for step in range(_ARC_STEPS + 1):
            angle = math.radians(start + 90.0 * step / _ARC_STEPS)
            points.append(
                (center_u + radius * math.cos(angle), center_v + radius * math.sin(angle))
            )
    return _distinct(points)


def half_stadium(length: float, radius: float) -> tuple[Point2, ...]:
    """Contour (u, v ≥ 0) de la moitié d'un stade de longueur ``length`` et de rayon ``radius``,
    posée sur sa corde (v = 0), centrée en u."""
    radius = min(radius, length / 2)
    reach = length / 2 - radius
    points: list[Point2] = []
    for center, start in ((-reach, 180.0), (reach, 90.0)):
        for step in range(_ARC_STEPS + 1):
            angle = math.radians(start - 90.0 * step / _ARC_STEPS)
            points.append((center + radius * math.cos(angle), radius * math.sin(angle)))
    return _distinct(points)


def _distinct(points: list[Point2]) -> tuple[Point2, ...]:
    """Contour sans sommets confondus avec le précédent (ni le dernier avec le premier)."""
    kept: list[Point2] = []
    for point in points:
        if not kept or math.dist(point, kept[-1]) > CONTACT_TOLERANCE_MM / 1000:
            kept.append(point)
    if len(kept) > 1 and math.dist(kept[0], kept[-1]) <= CONTACT_TOLERANCE_MM / 1000:
        kept.pop()
    return tuple(kept)
