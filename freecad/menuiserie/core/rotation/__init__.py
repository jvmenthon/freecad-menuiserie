# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rotation libre d'une pièce : règles pures (RO-a, ADR 0025).

Ce module est une façade : il ré-exporte l'API publique des sous-modules. ``features/`` lit et
écrit le ``Placement`` ; ``gui/`` fournit le rayon de la souris et la tolérance en mm. Aucun
import de FreeCAD, de Qt ni de pivy.
"""

from __future__ import annotations

from freecad.menuiserie.core.rotation._angles import Angles, angles_of, matrix_of
from freecad.menuiserie.core.rotation._ring import (
    EDGE_ON_DEGREES,
    MAX_RING_RADIUS_MM,
    MIN_RING_RADIUS_MM,
    Ring,
    plane_point,
    ring_angle,
    ring_hit,
    ring_of,
)
from freecad.menuiserie.core.rotation._turn import snapped_angle, turned_about

__all__ = [
    "EDGE_ON_DEGREES",
    "MAX_RING_RADIUS_MM",
    "MIN_RING_RADIUS_MM",
    "Angles",
    "Ring",
    "angles_of",
    "matrix_of",
    "plane_point",
    "ring_angle",
    "ring_hit",
    "ring_of",
    "snapped_angle",
    "turned_about",
]
