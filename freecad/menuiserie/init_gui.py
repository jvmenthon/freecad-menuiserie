# SPDX-License-Identifier: LGPL-2.1-or-later
"""Enregistrement du workbench Menuiserie dans l'interface de FreeCAD.

FreeCAD exécute ce fichier au démarrage de l'interface. Les commandes et
objets sont importés dans ``Initialize`` uniquement, pour ne pas ralentir
le lancement de FreeCAD tant que l'atelier n'est pas activé.
"""

from typing import ClassVar

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import TRANSLATIONS_DIR, icon_path

translate = App.Qt.translate
QT_TRANSLATE_NOOP = App.Qt.QT_TRANSLATE_NOOP


class MenuiserieWorkbench(Gui.Workbench):  # type: ignore[misc]
    """Atelier de menuiserie paramétrique."""

    MenuText = QT_TRANSLATE_NOOP("Workbench", "Menuiserie")
    ToolTip = QT_TRANSLATE_NOOP("Workbench", "Pièces de bois, assemblages et liste de débit")
    Icon = icon_path("menuiserie.svg")

    # Noms des commandes enregistrées par l'atelier ; complétés jalon après jalon.
    commands: ClassVar[list[str]] = []

    def Initialize(self) -> None:
        """Appelé une seule fois, à la première activation de l'atelier."""
        Gui.addLanguagePath(str(TRANSLATIONS_DIR))
        Gui.updateLocale()
        if self.commands:
            self.appendToolbar(translate("Workbench", "Menuiserie"), self.commands)
            self.appendMenu(translate("Workbench", "&Menuiserie"), self.commands)

    def Activated(self) -> None:
        """Appelé à chaque activation de l'atelier."""

    def Deactivated(self) -> None:
        """Appelé à chaque désactivation de l'atelier."""

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MenuiserieWorkbench())
