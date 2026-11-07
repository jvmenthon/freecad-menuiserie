# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits : mortaises plates dans les deux pièces.

Un faux tenon (type Domino) et un biscuit (lamelle) partagent le même plan d'usinage :
logements répartis le long de la largeur du contact, la pièce rapportée traversant de
moitié chaque pièce (ADR 0033).

Ce package est organisé en modules pour une meilleure maintenabilité :
- _params.py : Paramètres, valeurs et constantes
- _base.py : Classe de base _SlotStrategy
- _strategies.py : Implémentations concrètes (LooseTenon, Biscuit)
- _utils.py : Fonctions utilitaires de calcul

Pour la compatibilité descendante, toutes les classes et fonctions sont ré-exportées.
"""

from freecad.menuiserie.core.joints.slots._params import (
    AUTO_SIZE,
    BISCUIT_SIZES,
    LOOSE_TENON_SIZES,
    MIN_BOTTOM_MM,
    MIN_WALL_MM,
    SlotParams,
    SlotSize,
    SlotValues,
)
from freecad.menuiserie.core.joints.slots._strategies import (
    BiscuitStrategy,
    LooseTenonStrategy,
)
from freecad.menuiserie.core.joints._slot_shapes import half_stadium, rounded_rectangle

__all__ = [
    "AUTO_SIZE",
    "BISCUIT_SIZES",
    "LOOSE_TENON_SIZES",
    "BiscuitStrategy",
    "LooseTenonStrategy",
    "SlotParams",
    "SlotSize",
    "SlotValues",
    "half_stadium",
    "rounded_rectangle",
]
