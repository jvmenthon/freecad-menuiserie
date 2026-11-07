# SPDX-License-Identifier: LGPL-2.1-or-later
"""Coulisses de tiroir à billes : pose face à face entre un côté de caisson et un côté de tiroir.

Contrairement aux assemblages de chant ou de bout, les deux pièces sont séparées par un jeu (la
coulisse l'occupe) : le côté du caisson (host) et celui du tiroir (guest) se font face. La
coulisse, pièce rapportée, est posée à hauteur réglée sur le côté du caisson ; chaque côté reçoit
des avant-trous au pas du système 32 (ADR 0033).

Ce package est organisé en modules pour une meilleure maintenabilité :
- _params.py : Paramètres, valeurs et constantes
- _strategy.py : Stratégie d'assemblage (SlideStrategy)
- _layout.py : Calcul du layout (positions, dimensions)
- _drilling.py : Fonctions de perçage (trous, corps de la coulisse)

Pour la compatibilité descendante, toutes les classes et fonctions sont ré-exportées.
"""

from freecad.menuiserie.core.joints.slides._params import (
    SLIDE_LENGTHS,
    SlideParams,
    SlideValues,
)
from freecad.menuiserie.core.joints.slides._strategy import SlideStrategy

__all__ = ["SLIDE_LENGTHS", "SlideParams", "SlideStrategy", "SlideValues"]
