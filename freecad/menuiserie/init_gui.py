# SPDX-License-Identifier: LGPL-2.1-or-later
"""Enregistrement du workbench Menuiserie dans l'interface de FreeCAD.

FreeCAD exécute ce fichier au démarrage de l'interface. Les commandes et
objets sont importés dans ``Initialize`` uniquement, pour ne pas ralentir
le lancement de FreeCAD tant que l'atelier n'est pas activé.
"""

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
    commands: tuple[str, ...] = (
        "Menuiserie_WoodPart",
        "Menuiserie_MortiseTenon",
        "Menuiserie_TongueGroove",
        "Menuiserie_Rabbet",
        "Menuiserie_Dowels",
        "Menuiserie_HalfLap",
        "Menuiserie_Dovetail",
        "Menuiserie_Miter",
        # Ensembles (J4c)
        "Menuiserie_Furniture",
        "Menuiserie_FurnitureAdd",
        "Menuiserie_FurnitureRemove",
        "Menuiserie_FurnitureRebind",
    )

    def Initialize(self) -> None:
        """Appelé une seule fois, à la première activation de l'atelier."""
        Gui.addLanguagePath(str(TRANSLATIONS_DIR))
        Gui.updateLocale()
        from freecad.menuiserie.gui.commands import joints, wood_part

        wood_part.register()
        joints.register()
        from freecad.menuiserie.gui.commands import furniture

        furniture.register()
        self.appendToolbar(translate("Workbench", "Menuiserie"), list(self.commands))
        self.appendMenu(translate("Workbench", "&Menuiserie"), list(self.commands))

    def GetClassName(self) -> str:
        """Type C++ de l'atelier attendu par FreeCAD pour un atelier écrit en Python."""
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MenuiserieWorkbench())
