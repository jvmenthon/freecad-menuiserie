# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la Distance gardée : icône dans l'arborescence, panneau de tâche au double-clic
(DI-c, critère F8, ADR 0018).

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. La Distance n'a pas de forme :
aucun mode d'affichage ne dessine quoi que ce soit, et sans état enregistré.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie import icon_path
from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

ViewObject = Any

ICON: Final = "Menuiserie_Distance.svg"


class ViewProviderDistance(PanelEditing):
    """ViewProvider de la Distance gardée. Chemin de module figé (ADR 0003), sans état."""

    def __init__(self, vobj: ViewObject) -> None:
        vobj.Proxy = self

    def attach(self, vobj: ViewObject) -> None:
        """Garde le ViewObject (non enregistré) pour l'arbre."""
        self.vobj = vobj

    def getIcon(self) -> str:
        """Icône de l'arbre : celle de la Distance gardée."""
        return icon_path(ICON)

    def getDisplayModes(self, vobj: ViewObject) -> list[str]:
        """Aucune géométrie : un seul mode d'affichage, vide."""
        del vobj
        return ["Default"]

    def getDefaultDisplayMode(self) -> str:
        """Mode d'affichage unique."""
        return "Default"

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : la valeur de la Distance dans son panneau de tâche."""
        from freecad.menuiserie.gui.task_panels.distance_kept import start_editing

        return start_editing(vobj.Object)
