# SPDX-License-Identifier: LGPL-2.1-or-later
"""Accrochage ponctuel d'une nouvelle pièce contre des faces, arêtes ou sommets (J6a, ADR 0011).

Ce module est une façade : il ré-exporte l'API publique des sous-modules. ``features/`` convertit
les formes en cibles (:class:`FaceTarget`, :class:`EdgeTarget`, :class:`VertexTarget`, repères
tangents par :func:`tangent_frame`), appelle :func:`snap`, puis écrit le ``Placement``. Aucun
import de FreeCAD ni de Qt.
"""

from __future__ import annotations

from freecad.menuiserie.core.snap._frames import tangent_frame, turned_in_place
from freecad.menuiserie.core.snap._model import (
    EdgeTarget,
    FaceTarget,
    Frame,
    FreeTest,
    Orientation,
    SnapNotice,
    SnapNoticeKind,
    SnapResult,
    Target,
    Turn,
    VertexTarget,
)
from freecad.menuiserie.core.snap._solve import MAX_TARGETS, snap

__all__ = [
    "MAX_TARGETS",
    "EdgeTarget",
    "FaceTarget",
    "Frame",
    "FreeTest",
    "Orientation",
    "SnapNotice",
    "SnapNoticeKind",
    "SnapResult",
    "Target",
    "Turn",
    "VertexTarget",
    "snap",
    "tangent_frame",
    "turned_in_place",
]
