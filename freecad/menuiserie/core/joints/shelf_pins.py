# SPDX-License-Identifier: LGPL-2.1-or-later
"""Perçage LR32 et taquets de tablette : deux colonnes de trous au pas de 32 mm dans un côté.

Un perçage ne relie pas deux pièces : ``guest`` est la même pièce que ``host`` (le côté de
caisson debout). Deux colonnes de trous de 5 mm au pas de 32 mm (système « ligne et rangée de
32 mm ») sont percées dans une face, à 37 mm des bouts horizontaux ; les taquets de la tablette
sont des pièces rapportées plantées dans un rang de trous (ADR 0033). Calculs dans le repère du
côté ; sa longueur ou sa largeur est la verticale du document, son épaisseur est horizontale.

Ce module est maintenant organisé en package pour une meilleure maintenabilité :
- shelf_pins/_params.py : Paramètres et valeurs (dataclasses, constantes)
- shelf_pins/_strategy.py : Stratégie d'assemblage (ShelfPinsStrategy)
- shelf_pins/_layout.py : Calcul du layout (positions des trous et taquets)
- shelf_pins/_drilling.py : Fonctions de perçage (création des trous et taquets)

Pour la compatibilité descendante, toutes les classes et fonctions sont ré-exportées.
"""

# Ré-export complet depuis le package shelf_pins
from freecad.menuiserie.core.joints.shelf_pins._params import (
    FACES,
    ShelfPinsParams,
    ShelfPinsValues,
)
from freecad.menuiserie.core.joints.shelf_pins._strategy import ShelfPinsStrategy
from freecad.menuiserie.core.joints.shelf_pins._layout import (
    NOT_UPRIGHT,
    opposite_values,
)
from freecad.menuiserie.core.joints.shelf_pins._drilling import pin_rests
from freecad.menuiserie.core.joints._shelf_layout import (
    Neighbor,
    facing_side,
    picked_choice,
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
