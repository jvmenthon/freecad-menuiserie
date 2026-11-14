# SPDX-License-Identifier: LGPL-2.1-or-later
"""Alignement de deux faces planes : règles pures (AL-a, ADR 0054).

Façade : ré-exporte l'API publique de ``_align``. ``features/`` lit les faces comme cibles de
``core/snap``, appelle :func:`align` puis écrit le ``Placement``. Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

from freecad.menuiserie.core.align._align import (
    NO_OFFSET,
    AlignError,
    Alignment,
    AlignMode,
    align,
    face_center,
)

__all__ = [
    "NO_OFFSET",
    "AlignError",
    "AlignMode",
    "Alignment",
    "align",
    "face_center",
]
