# SPDX-License-Identifier: LGPL-2.1-or-later
"""Distance entre deux éléments de deux pièces (DI-a, ADR 0022).

Façade : ré-exporte l'API publique de ``_measure``. ``features/`` convertit les sélections en
cibles de ``core/snap``, appelle :func:`measure` puis :func:`moved_by` et écrit le ``Placement``.
Aucun import de FreeCAD ni de Qt.
"""

from __future__ import annotations

from freecad.menuiserie.core.distance._measure import (
    DistanceError,
    FrameAxis,
    Gap,
    ensemble_axis,
    measure,
    moved_by,
)

__all__ = ["DistanceError", "FrameAxis", "Gap", "ensemble_axis", "measure", "moved_by"]
