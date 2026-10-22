# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de la liste de débit attendues (J2d, critères G1 et G2), partagées par les tests
unitaires (analyse statique) et les vérifications d'interface : nom → libellé.

Données seules, sans import de FreeCAD : importable par ``pytest`` comme par FreeCAD.
"""

from __future__ import annotations

from typing import Final

COMMANDES_DEBIT: Final = {
    "Menuiserie_CutList": "Liste de débit",
    "Menuiserie_CutListExport": "Exporter la liste de débit (CSV)…",
}
