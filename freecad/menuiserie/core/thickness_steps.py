# SPDX-License-Identifier: LGPL-2.1-or-later
"""Crans d'épaisseur d'un panneau tiré à la souris (jv, 2026-11-26, ADR 0021 point 1 modifié) :
l'épaisseur saute d'une épaisseur standard à la suivante, sans descendre sous la plus petite ni
dépasser la plus grande. Python pur, sans FreeCAD ni dépendance à l'atelier."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

__all__ = ["snap_thickness", "thickness_steps"]


def thickness_steps(standards: Iterable[float]) -> tuple[float, ...]:
    """Crans (mm) croissants et sans doublon des épaisseurs ``standards`` ; une valeur nulle,
    négative ou non finie est écartée."""
    return tuple(sorted({float(t) for t in standards if math.isfinite(t) and t > 0}))


def snap_thickness(value: float, steps: Sequence[float]) -> float:
    """Cran de ``steps`` (croissants, non vides) le plus proche de ``value`` (mm) : la plus petite
    épaisseur en dessous, la plus grande au-dessus ; à égale distance, le cran du dessous.
    ``ValueError`` si ``steps`` est vide ; ``NaN`` donne le plus petit cran."""
    if not steps:
        raise ValueError("aucun cran d'épaisseur")
    if math.isnan(value):
        return steps[0]
    if math.isinf(value):
        return steps[0] if value < 0 else steps[-1]
    return min(steps, key=lambda step: (abs(step - value), step))
