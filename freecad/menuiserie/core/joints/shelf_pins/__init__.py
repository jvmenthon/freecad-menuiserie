# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette : module principal.

Ce package contient l'implémentation du perçage LR32 (deux colonnes de trous au pas de
32 mm dans un côté de caisson) avec gestion des taquets de tablette.

Structure :
- _params.py : Paramètres et valeurs (dataclasses, constantes)
- _strategy.py : Stratégie d'assemblage (ShelfPinsStrategy)
- _layout.py : Calcul du layout (position des trous et taquets)
- _drilling.py : Fonctions de perçage (création des trous et taquets)
"""

from freecad.menuiserie.core.joints.shelf_pins._params import (
    FACES,
    MIN_BOTTOM_MM,
    MIN_WALL_MM,
    ShelfPinsParams,
    ShelfPinsValues,
)
from freecad.menuiserie.core.joints.shelf_pins._strategy import ShelfPinsStrategy
from freecad.menuiserie.core.joints.shelf_pins._layout import (
    opposite_values,
    NOT_UPRIGHT,
)
from freecad.menuiserie.core.joints.shelf_pins._drilling import pin_rests

__all__ = [
    "FACES",
    "MIN_BOTTOM_MM",
    "MIN_WALL_MM",
    "NOT_UPRIGHT",
    "ShelfPinsParams",
    "ShelfPinsStrategy",
    "ShelfPinsValues",
    "facing_side",
    "opposite_values",
    "picked_choice",
    "pin_rests",
]

# Ré-export depuis _shelf_layout pour compatibilité descendante
from freecad.menuiserie.core.joints._shelf_layout import (
    NOT_UPRIGHT,
    Layout,
    Neighbor,
    choose_face,
    facing_side,
    free_window,
    heights_of,
    picked_choice,
    pin_rows,
    side_boxes,
    touching_boxes,
    upright,
)
