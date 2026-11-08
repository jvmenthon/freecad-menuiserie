# SPDX-License-Identifier: LGPL-2.1-or-later
"""Répétition de pièces (ADR 0043, spécification ``docs/specs/repetition.md``) : calcul pur.

Décrit une répétition linéaire (nombre et pas, nombre sur une longueur, pas sur une longueur)
sans rien connaître de FreeCAD : paramètres validés (:class:`RepeatParams`), nombre et pas
effectifs (:func:`resolve`), décalages des copies (:func:`offsets`) et détection du
chevauchement (:func:`overlaps`). Les modes cercle et trajet sont réservés dans le modèle.
"""

from freecad.menuiserie.core.repeat._compute import (
    OVERLAP_TOLERANCE_MM,
    Resolved,
    offsets,
    overlaps,
    resolve,
)
from freecad.menuiserie.core.repeat._model import (
    MAX_COPIES,
    RepeatAxis,
    RepeatError,
    RepeatMode,
    RepeatParams,
    SpacingMode,
)

__all__ = [
    "MAX_COPIES",
    "OVERLAP_TOLERANCE_MM",
    "RepeatAxis",
    "RepeatError",
    "RepeatMode",
    "RepeatParams",
    "Resolved",
    "SpacingMode",
    "offsets",
    "overlaps",
    "resolve",
]
