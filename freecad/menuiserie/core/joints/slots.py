# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits : mortaises plates dans les deux pièces, pièce rapportée entre elles.

Un faux tenon (type Domino) et un biscuit (lamello) partagent le même plan d'usinage : logements
répartis le long de la largeur du contact, la pièce rapportée traversant de moitié chaque pièce
(ADR 0033). Leurs formes sont celles du commerce : le faux tenon a une section en stade (bouts
demi-ronds, comme les Domino de Festool) extrudée dans la profondeur ; le biscuit est un stade
dans le plan du joint (comme les lamelles de Lamello), de l'épaisseur de la fente. La taille se
choisit dans la liste du commerce (Festool, Lamello) ; seul le faux tenon accepte une taille
personnalisée. Calculs dans le repère de l'invitée (:mod:`._profile`).

Ce module est maintenant organisé en package pour une meilleure maintenabilité :
- slots/_params.py : Paramètres, valeurs et constantes
- slots/_base.py : Classe de base _SlotStrategy
- slots/_strategies.py : Implémentations concrètes (LooseTenon, Biscuit)
- slots/_utils.py : Fonctions utilitaires de calcul

Pour la compatibilité descendante, toutes les classes et fonctions sont ré-exportées.
"""

# Ré-export complet depuis le package slots
from freecad.menuiserie.core.joints.slots._params import (
    AUTO_SIZE,
    BISCUIT_SIZES,
    LOOSE_TENON_SIZES,
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
