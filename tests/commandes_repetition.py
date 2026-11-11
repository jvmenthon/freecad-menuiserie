# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de la répétition attendues (lot R-c, ADR 0043), partagées par les tests unitaires
(analyse statique) et les vérifications d'interface : nom → (libellé, entrée d'annulation).

Données seules, sans import de FreeCAD : importable par ``pytest`` comme par FreeCAD.
"""

from __future__ import annotations

from typing import Final

COMMANDES_REPETITION: Final = {
    "Menuiserie_Repeat": ("Répéter", "Répéter"),
    "Menuiserie_RepeatEdit": ("Modifier la répétition", "Modifier la répétition"),
    "Menuiserie_RepeatDissociate": ("Dissocier la copie", "Dissocier la copie"),
}
