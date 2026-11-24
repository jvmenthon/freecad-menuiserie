# SPDX-License-Identifier: LGPL-2.1-or-later
"""Glissement d'une pièce à la souris, aimantation et poignées : règles pures (SM-a, ADR 0021).

Ce module est une façade : il ré-exporte l'API publique des sous-modules. ``gui/`` fournit le
rayon de la souris, les positions en pixels et la tolérance ; ``features/`` lit les formes en
guides (:class:`Guide`) et écrit les propriétés. Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

from freecad.menuiserie.core.magnet._axis import (
    MAGNET_PX,
    arrows,
    axis_param,
    handle_point,
    mouse_ray,
)
from freecad.menuiserie.core.magnet._coplanar import (
    MAX_COPLANAR,
    SNAP_REACH_MM,
    PlaneIndex,
    box_faces,
    overlaps,
    snap_field,
)
from freecad.menuiserie.core.magnet._magnet import (
    HANDLE_RADIUS_PX,
    handle_at,
    magnet,
    mm_per_pixel,
    resize,
)
from freecad.menuiserie.core.magnet._model import (
    MIN_SIZE_MM,
    THICKNESS_AXIS,
    Arrow,
    Blocker,
    DragResult,
    Guide,
    GuideKind,
    Handle,
    MagnetHit,
    MagnetKind,
    PixelTarget,
    Ray,
    ResizeResult,
)

__all__ = [
    "HANDLE_RADIUS_PX",
    "MAGNET_PX",
    "MAX_COPLANAR",
    "MIN_SIZE_MM",
    "SNAP_REACH_MM",
    "THICKNESS_AXIS",
    "Arrow",
    "Blocker",
    "DragResult",
    "Guide",
    "GuideKind",
    "Handle",
    "MagnetHit",
    "MagnetKind",
    "PixelTarget",
    "PlaneIndex",
    "Ray",
    "ResizeResult",
    "arrows",
    "axis_param",
    "box_faces",
    "handle_at",
    "handle_point",
    "magnet",
    "mm_per_pixel",
    "mouse_ray",
    "overlaps",
    "resize",
    "snap_field",
]
