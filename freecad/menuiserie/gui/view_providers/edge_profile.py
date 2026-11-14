# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage d'un profil d'arête : icône dans l'arbre, réglage dans le panneau de tâche au
double-clic (issue #5).

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. Le profil n'a pas de forme :
rien à afficher dans la vue 3D, la pièce usinée montre le résultat.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import icon_path
from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

ViewObject = Any

ICON: Final = "Menuiserie_FinitionChants.svg"


class ViewProviderEdgeProfile(PanelEditing):
    """ViewProvider du profil d'arête. Chemin de module figé (ADR 0003), sans état."""

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré)."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la commande « Finition des chants »."""
        return icon_path(ICON)

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : réglage du profil dans son panneau de tâche."""
        from freecad.menuiserie.gui.task_panels.edge_finish import start_editing

        return start_editing(vobj.Object)
