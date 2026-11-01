# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la Distance gardée : icône dans l'arborescence, panneau de tâche au double-clic
(DI-c, critère F8, ADR 0018).

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. La Distance n'a pas de forme :
aucun mode d'affichage ne dessine quoi que ce soit, et sans état enregistré.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie.gui.view_providers.no_geometry import NoGeometryView
from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

ViewObject = Any

ICON: Final = "Menuiserie_Distance.svg"


class ViewProviderDistance(NoGeometryView, PanelEditing):
    """ViewProvider de la Distance gardée. Chemin de module figé (ADR 0003), sans état."""

    ICON = ICON

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : la valeur de la Distance dans son panneau de tâche."""
        from freecad.menuiserie.gui.task_panels.distance_kept import start_editing

        return start_editing(vobj.Object)
