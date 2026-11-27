# SPDX-License-Identifier: LGPL-2.1-or-later
"""Réglages des taquets (système 32) : clés et catalogue du groupe « Taquets » (ADR 0069, 0070).

Ce module ne lit aucune préférence : il décrit seulement les réglages, que
:mod:`freecad.menuiserie.features.settings` réunit dans le catalogue de l'atelier. Les valeurs
sont copiées dans le perçage à sa création (:mod:`freecad.menuiserie.features.joint_settings`) ;
le recalcul ne lit jamais le réglage.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import MIN_WALL_MM
from freecad.menuiserie.core.joints.shelf_pins import (
    AUTO_DEPTH_MM,
    AUTO_DIAMETER_MM,
    ShelfPinsParams,
)
from freecad.menuiserie.features.settings_build import length_setting
from freecad.menuiserie.kit.config.catalog import Relation, Setting, Value

__all__ = [
    "SHELF_PINS",
    "SHELF_PIN_DEPTH",
    "SHELF_PIN_DIAMETER",
    "SHELF_PIN_PITCH",
    "hardware_relations",
    "hardware_settings",
]

# Clés (noms des paramètres FreeCAD, figés : une clé renommée perd la valeur de l'utilisateur).
SHELF_PIN_PITCH: Final = "ShelfPinPitch"
SHELF_PIN_DIAMETER: Final = "ShelfPinDiameter"
SHELF_PIN_DEPTH: Final = "ShelfPinDepth"

SHELF_PINS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Taquets")

_MIN_DIAMETER_MM: Final = 1.0
_MAX_DIAMETER_MM: Final = 30.0
# Le perçage refuse un pas inférieur à son diamètre + MIN_WALL_MM (PITCH_TOO_SMALL) ; le diamètre
# automatique est le plus petit que le perçage emploie sans réglage explicite.
_MIN_PITCH_MM: Final = AUTO_DIAMETER_MM + MIN_WALL_MM
_MAX_PITCH_MM: Final = 200.0
_MIN_DEPTH_MM: Final = 1.0
_MAX_DEPTH_MM: Final = 100.0


def _pitch_fits_diameter(values: Mapping[str, Value]) -> bool:
    """Le pas laisse au moins MIN_WALL_MM de matière entre deux trous."""
    return float(values[SHELF_PIN_PITCH]) >= float(values[SHELF_PIN_DIAMETER]) + MIN_WALL_MM


def hardware_relations() -> list[Relation]:
    """Pas et diamètre : chacun est borné seul, mais le pas dépend du diamètre."""
    return [Relation((SHELF_PIN_PITCH, SHELF_PIN_DIAMETER), _pitch_fits_diameter)]


def hardware_settings() -> list[Setting]:
    """Pas, diamètre et profondeur du perçage des taquets d'un nouveau perçage LR32."""
    return [
        length_setting(
            SHELF_PIN_PITCH,
            ShelfPinsParams().pitch,
            QT_TRANSLATE_NOOP("Menuiserie", "Pas des trous"),
            QT_TRANSLATE_NOOP(
                "Menuiserie", "Écart entre deux trous d'un nouveau perçage (système 32 : 32 mm)."
            ),
            SHELF_PINS,
            minimum=_MIN_PITCH_MM,
            maximum=_MAX_PITCH_MM,
            remember_last=True,
        ),
        length_setting(
            SHELF_PIN_DIAMETER,
            AUTO_DIAMETER_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des trous"),
            QT_TRANSLATE_NOOP("Menuiserie", "Diamètre des trous d'un nouveau perçage."),
            SHELF_PINS,
            minimum=_MIN_DIAMETER_MM,
            maximum=_MAX_DIAMETER_MM,
            remember_last=True,
        ),
        length_setting(
            SHELF_PIN_DEPTH,
            AUTO_DEPTH_MM,
            QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des trous"),
            QT_TRANSLATE_NOOP("Menuiserie", "Profondeur des trous d'un nouveau perçage."),
            SHELF_PINS,
            minimum=_MIN_DEPTH_MM,
            maximum=_MAX_DEPTH_MM,
            remember_last=True,
        ),
    ]
