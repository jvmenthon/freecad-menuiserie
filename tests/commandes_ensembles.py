# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de l'ensemble attendues (J4c, critère P1), partagées par les tests unitaires
(analyse statique) et les vérifications d'interface : nom → (libellé, entrée d'annulation).

Données seules, sans import de FreeCAD : importable par ``pytest`` comme par FreeCAD.
"""

from __future__ import annotations

from typing import Final

COMMANDES_ENSEMBLE: Final = {
    "Menuiserie_Furniture": ("Ensemble", "Créer un ensemble"),
    "Menuiserie_FurnitureAdd": ("Ajouter à l'ensemble", "Ajouter à l'ensemble"),
    "Menuiserie_FurnitureRemove": ("Retirer de l'ensemble", "Retirer de l'ensemble"),
    "Menuiserie_FurnitureRebind": ("Relier les pièces", "Relier les pièces"),
}
