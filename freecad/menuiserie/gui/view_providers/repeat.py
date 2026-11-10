# SPDX-License-Identifier: LGPL-2.1-or-later
"""Affichage de la Répétition (R-c, ADR 0043) : icône dans l'arborescence, panneau « Modifier la
répétition » au double-clic.

Contrat de persistance (ADR 0003) : le chemin de ce module et le nom de la classe sont écrits
dans les documents (``GuiDocument.xml``) ; ils ne changent jamais. La Répétition n'a pas de forme
(les copies sont des pièces ordinaires, qui gardent leur propre ViewProvider et leur propre
double-clic) : aucun mode d'affichage ne dessine quoi que ce soit, et sans état enregistré.
"""

from __future__ import annotations

from typing import Any, Final

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.gui.view_providers.no_geometry import NoGeometryView
from freecad.menuiserie.gui.view_providers.wood_part import PanelEditing

ViewObject = Any

ICON: Final = "Menuiserie_RepeatObject.svg"


class ViewProviderRepeat(NoGeometryView, PanelEditing):
    """ViewProvider de la Répétition. Chemin de module figé (ADR 0003), sans état enregistré."""

    ICON = ICON

    def open_panel(self, vobj: ViewObject) -> bool | None:
        """Mode 0 (double-clic) : panneau « Modifier la répétition »."""
        from freecad.menuiserie.gui.task_panels.repeat import start_editing

        return start_editing(vobj.Object)


def ensure_view_provider(repeat: DocumentObject) -> None:
    """Pose le ViewProvider sur une répétition qui n'en a pas (créée par l'api, qui ne touche pas
    à l'interface) ; sans effet sans interface ou s'il est déjà là."""
    vobj = getattr(repeat, "ViewObject", None) if App.GuiUp else None
    if vobj is not None and not isinstance(getattr(vobj, "Proxy", None), ViewProviderRepeat):
        ViewProviderRepeat(vobj)
