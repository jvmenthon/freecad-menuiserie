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
    # Gabarits (J4d)
    commands += ("Menuiserie_Carcass",)
    # Distance entre deux pièces (DI-b)
    commands += ("Menuiserie_SetDistance",)
    # Liste de débit (J2d, J2g)
    commands += (
        "Menuiserie_CutList",
        "Menuiserie_CutListPreview",
        "Menuiserie_CutListExport",
        "Menuiserie_CutListPdf",
        "Menuiserie_NumberMarks",
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
        from freecad.menuiserie.gui.commands import carcass  # gabarits (J4d)

        carcass.register()
        from freecad.menuiserie.gui.commands import cutlist  # liste de débit (J2d)

        cutlist.register()
        from freecad.menuiserie.gui.commands import distance  # distance entre deux pièces (DI-b)

        distance.register()
        self.appendToolbar(translate("Workbench", "Menuiserie"), list(self.commands))
        self.appendMenu(translate("Workbench", "&Menuiserie"), list(self.commands))

    def Activated(self) -> None:
        """Atelier actif : double-clic dans la vue 3D sur ses objets (ADR 0018)."""
        from freecad.menuiserie.gui import double_click

        double_click.install()

    def Deactivated(self) -> None:
        """Atelier quitté : le filtre du double-clic est retiré de toutes les vues."""
        from freecad.menuiserie.gui import double_click

        double_click.uninstall()

    def ContextMenu(self, recipient: str) -> None:
        """Menu contextuel de la vue 3D (« View ») et de l'arborescence (« Tree ») : « Définir une
        distance » quand la sélection compte deux éléments de deux objets. Ce menu n'existe que
        pendant que l'atelier est actif (ADR 0007)."""
        from freecad.menuiserie.gui.commands import distance

        if distance.selected_pair() is not None:
            self.appendContextMenu(translate("Workbench", "Menuiserie"), [distance.COMMAND_NAME])

    def GetClassName(self) -> str:
        """Type C++ de l'atelier attendu par FreeCAD pour un atelier écrit en Python."""
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MenuiserieWorkbench())
