# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces planes : règles pures (AL-a, ADR 0054).

Façade : ré-exporte l'API publique de ``_align`` et ``_layout``. ``features/`` lit les faces
comme cibles de ``core/snap``, appelle :func:`align` puis écrit le ``Placement``.
Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

from freecad.menuiserie.core.align._align import (
    NO_OFFSET,
    AlignError,
    Alignment,
    AlignMode,
    face_center,
)
from freecad.menuiserie.core.align._layout import (
    NO_LAYOUT,
    Anchor,
    Layout,
    align,
    crosses_faces,
)

__all__ = [
    "NO_LAYOUT",
    "NO_OFFSET",
    "AlignError",
    "AlignMode",
    "Alignment",
    "Anchor",
    "Layout",
    "align",
    "crosses_faces",
    "face_center",
]
