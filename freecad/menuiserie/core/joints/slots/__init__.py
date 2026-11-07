# SPDX-License-Identifier: LGPL-2.1-or-later
"""Faux tenons et biscuits : mortaises plates dans les deux pièces, pièce rapportée entre elles.

Un faux tenon (type Domino) et un biscuit (lamelle) partagent le même plan d'usinage : logements
répartis le long de la largeur du contact, la pièce rapportée traversant de moitié chaque pièce
(ADR 0033). Leurs formes sont celles du commerce : le faux tenon a une section en stade (bouts
demi-ronds, comme les Domino de Festool) extrudée dans la profondeur ; le biscuit est un stade
dans le plan du joint (comme les lamelles de Lamello), de l'épaisseur de la fente. La taille se
choisit dans la liste du commerce (Festool, Lamello) ; seul le faux tenon accepte une taille
personnalisée. Calculs dans le repère de l'invitée (:mod:`._profile`).

Paquet : ``_params`` (paramètres, valeurs, constantes) et ``_strategy`` (calcul des usinages) ;
l'interface publique est celle de l'ancien module (ADR 0040).
"""

from __future__ import annotations

from freecad.menuiserie.core.joints._slot_shapes import half_stadium, rounded_rectangle
from freecad.menuiserie.core.joints.slots._params import (
    AUTO_SIZE,
    BISCUIT_SIZES,
    LOOSE_TENON_SIZES,
    SlotParams,
    SlotSize,
    SlotValues,
)
from freecad.menuiserie.core.joints.slots._strategy import BiscuitStrategy, LooseTenonStrategy

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
