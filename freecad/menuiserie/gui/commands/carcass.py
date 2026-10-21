# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Caisson » (J4d, critère K6) : gabarit qui crée un caisson complet, puis disparaît
(ADR 0010) ; le panneau règle ses paramètres avec un aperçu."""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.task_panels.carcass import CREATE_TRANSACTION, ICON, show_panel

COMMAND_NAME: Final = "Menuiserie_Carcass"


class CreateCarcassCommand:
    """Ouvre le panneau du gabarit « Caisson » dans la transaction « Créer un caisson »."""

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(ICON),
            "MenuText": QT_TRANSLATE_NOOP("Menuiserie_Carcass", "Caisson"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Menuiserie_Carcass",
                "Crée un caisson complet en un clic : côtés, dessus, dessous, fond en feuillure, "
                "étagères et tourillons, réunis dans un ensemble que l'on redimensionne ensuite "
                "comme tout ensemble.",
            ),
        }

    def IsActive(self) -> bool:
        """Active s'il y a un document, au moins un matériau et aucun panneau de tâche."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and bool(len(get_library()))
        )

    def Activated(self) -> None:
        """Panneau ouvert dans la transaction « Créer un caisson », validée (une entrée
        d'annulation) ou abandonnée (aucun objet) par le panneau."""
        doc = App.ActiveDocument
        doc.openTransaction(translated(CREATE_TRANSACTION))
        show_panel(doc)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, CreateCarcassCommand())
