# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes des plans cotés attendues (issue #153), partagées par les tests unitaires et les
vérifications d'interface : nom → libellé. Données seules, sans import de FreeCAD."""

from __future__ import annotations

from typing import Final

COMMANDES_PLAN: Final = {
    "Menuiserie_Drawing": "Plan de l'ouvrage",
    "Menuiserie_PartDrawings": "Plans de pièce",
    "Menuiserie_ExplodedDrawing": "Vue éclatée",
    "Menuiserie_DrawingPdf": "Exporter le plan (PDF)…",
}
