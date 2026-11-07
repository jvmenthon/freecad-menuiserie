# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette : deux colonnes de trous au pas de 32 mm dans un côté.

Un perçage ne relie pas deux pièces : ``guest`` est la même pièce que ``host`` (le côté de
caisson debout). Deux colonnes de trous de 5 mm au pas de 32 mm (système « ligne et rangée de
32 mm ») sont percées dans une face, à 37 mm des bouts horizontaux ; les taquets de la tablette
sont des pièces rapportées plantées dans un rang de trous (ADR 0033). Calculs dans le repère du
côté ; sa longueur ou sa largeur est la verticale du document, son épaisseur est horizontale.

Paquet : ``_params`` (paramètres, valeurs, constantes) et ``_strategy`` (calcul des usinages) ;
l'interface publique est celle de l'ancien module (ADR 0040).
"""

from __future__ import annotations

from freecad.menuiserie.core.joints._shelf_layout import (
    NOT_UPRIGHT,
    Neighbor,
    facing_side,
    picked_choice,
)
from freecad.menuiserie.core.joints.shelf_pins._params import (
    FACES,
    ShelfPinsParams,
    ShelfPinsValues,
)
from freecad.menuiserie.core.joints.shelf_pins._strategy import (
    ShelfPinsStrategy,
    opposite_values,
    pin_rests,
)

__all__ = [
    "FACES",
    "NOT_UPRIGHT",
    "Neighbor",
    "ShelfPinsParams",
    "ShelfPinsStrategy",
    "ShelfPinsValues",
    "facing_side",
    "opposite_values",
    "picked_choice",
    "pin_rests",
]
