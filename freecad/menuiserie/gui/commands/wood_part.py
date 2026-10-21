# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Pièce de bois » : crée une pièce et ouvre son panneau de tâche."""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.api import make_wood_part
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.task_panels.base import close_transaction
from freecad.menuiserie.gui.task_panels.wood_part import show_panel
from freecad.menuiserie.gui.view_providers.wood_part import ICON

COMMAND_NAME: Final = "Menuiserie_WoodPart"
CREATE_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Créer une pièce de bois")
EMPTY_LIBRARY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Aucun matériau dans la bibliothèque : impossible de créer une pièce de bois. Vérifiez le "
    "fichier de matériaux (vue rapport).",
)


class CreateWoodPartCommand:
    """Crée une pièce de bois aux valeurs par défaut, puis ouvre le panneau pour la régler."""

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(ICON),
            "MenuText": QT_TRANSLATE_NOOP("Menuiserie_WoodPart", "Pièce de bois"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Menuiserie_WoodPart",
                "Crée une pièce de bois paramétrique (planche, tasseau, panneau) : cotes finies, "
                "matériau de la bibliothèque, sens du fil et surcotes de débit.",
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
        """Pièce créée dans la transaction « Créer une pièce de bois », validée ou abandonnée
        par le panneau. Une exception ne laisse ni pièce ni transaction."""
        if not len(get_library()):
            report_warning(translated(EMPTY_LIBRARY))
            return
        doc = App.ActiveDocument
        doc.openTransaction(translated(CREATE_TRANSACTION))
        try:
            obj = make_wood_part(doc=doc)
        except BaseException:
            close_transaction(App.getActiveTransaction(), abort=True)
            raise
        show_panel(obj, creating=True)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, CreateWoodPartCommand())
