# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes d'assemblage attendues, partagées par les tests unitaires (analyse statique) et les
vérifications d'interface : nom ``Menuiserie_<JointKind.value>`` → (libellé, fabrique de l'api).

Données seules, sans import de FreeCAD : importable par ``pytest`` comme par FreeCAD.
"""

from __future__ import annotations

from typing import Final

COMMANDES_ASSEMBLAGE: Final = {
    "Menuiserie_MortiseTenon": ("Tenon-mortaise", "make_mortise_tenon"),
    "Menuiserie_TongueGroove": ("Rainure-languette", "make_tongue_groove"),
    "Menuiserie_Rabbet": ("Feuillure", "make_rabbet"),
    "Menuiserie_Dowels": ("Tourillons", "make_dowels"),
    "Menuiserie_HalfLap": ("Mi-bois", "make_half_lap"),
    "Menuiserie_Dovetail": ("Queue d'aronde", "make_dovetail"),
    "Menuiserie_Miter": ("Onglet", "make_miter"),
}
