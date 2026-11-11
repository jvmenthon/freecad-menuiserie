# SPDX-License-Identifier: LGPL-2.1-or-later
"""Résumé et avertissement de chevauchement du panneau « Répéter » (grille, ADR 0045)."""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import mm_text
from freecad.menuiserie.core.repeat import (
    RepeatAxis,
    ResolvedGrid,
    grid_overlaps,
    grid_text,
    overlapping_axes,
)
from freecad.menuiserie.features.i18n import translated

__all__ = ["overlap_text", "summary_text"]

_SUMMARY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "{count} copies en plus de l'original, pas de {step} mm."
)
_GRID_SUMMARY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Grille {counts} : {count} copies en plus de l'original ({steps})."
)
_AXIS_STEP: Final = QT_TRANSLATE_NOOP("Menuiserie", "{axis} : pas de {step} mm")
_OVERLAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Attention : le pas de {step} mm est inférieur à la cote de la pièce ({extent} mm) sur "
    "l'axe {axis}, les copies se chevauchent.",
)
_GRID_OVERLAP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "La grille complète est concernée : des copies voisines en diagonale se touchent."
)


def summary_text(grid: ResolvedGrid) -> str:
    """Total des copies et, selon le nombre d'axes, le pas ou la grille et le pas de chaque axe."""
    if len(grid.axes) == 1:
        only = grid.axes[0]
        return translated(_SUMMARY, {"count": str(grid.total), "step": mm_text(only.step)})
    steps = ", ".join(
        translated(_AXIS_STEP, {"axis": line.axis.value, "step": mm_text(line.step)})
        for line in grid.axes
    )
    return translated(
        _GRID_SUMMARY, {"counts": grid_text(grid), "count": str(grid.total), "steps": steps}
    )


def overlap_text(grid: ResolvedGrid, extents: dict[RepeatAxis, float]) -> str:
    """Avertissement de chevauchement : un message par axe concerné, puis un mot sur la grille
    complète quand plusieurs axes se chevauchent (non bloquant)."""
    axes = overlapping_axes(grid, extents)
    texts = [
        translated(
            _OVERLAP,
            {
                "step": mm_text(line.step),
                "extent": mm_text(extents[line.axis]),
                "axis": line.axis.value,
            },
        )
        for line in grid.axes
        if line.axis in axes
    ]
    if len(axes) > 1 and grid_overlaps(grid, extents):
        texts.append(translated(_GRID_OVERLAP))
    return "\n".join(texts)
