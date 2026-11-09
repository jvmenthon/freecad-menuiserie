# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition de pièces (ADR 0043, spécification ``docs/specs/repetition.md``) : calcul pur.

Décrit une répétition linéaire ou en grille X x Y x Z (nombre et pas, nombre sur une longueur, pas
sur une longueur : un seul mode de saisie, une ligne par axe) sans rien connaître de FreeCAD :
paramètres validés (:class:`RepeatParams`, :class:`AxisRepeat`), nombre et pas effectifs
(:func:`resolve` pour un axe, :func:`resolve_grid` pour la grille), cellules et décalages des copies
(:func:`cell_offsets`, :func:`offsets`) et détection du chevauchement (:func:`overlaps`,
:func:`overlapping_axes`, :func:`grid_overlaps`). Les modes cercle et trajet sont réservés dans
le modèle (ADR 0043 et 0045).
"""

from freecad.menuiserie.core.repeat._compute import (
    OVERLAP_TOLERANCE_MM,
    Resolved,
    overlaps,
    resolve,
    resolve_line,
)
from freecad.menuiserie.core.repeat._grid import (
    ORIGIN,
    ResolvedAxis,
    ResolvedGrid,
    axis_index,
    cell_offsets,
    cells_of,
    grid_overlaps,
    grid_text,
    offsets,
    overlapping_axes,
    rank_of,
    resolve_grid,
)
from freecad.menuiserie.core.repeat._model import (
    MAX_COPIES,
    NO_AXIS,
    AxisRepeat,
    Cell,
    RepeatAxis,
    RepeatError,
    RepeatMode,
    RepeatParams,
    SpacingMode,
)

__all__ = [
    "MAX_COPIES",
    "NO_AXIS",
    "ORIGIN",
    "OVERLAP_TOLERANCE_MM",
    "AxisRepeat",
    "Cell",
    "RepeatAxis",
    "RepeatError",
    "RepeatMode",
    "RepeatParams",
    "Resolved",
    "ResolvedAxis",
    "ResolvedGrid",
    "SpacingMode",
    "axis_index",
    "cell_offsets",
    "cells_of",
    "grid_overlaps",
    "grid_text",
    "offsets",
    "overlapping_axes",
    "overlaps",
    "rank_of",
    "resolve",
    "resolve_grid",
    "resolve_line",
]
