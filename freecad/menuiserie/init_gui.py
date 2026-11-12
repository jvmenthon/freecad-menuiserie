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

    # Commandes enregistrées par l'atelier, regroupées par thème : une barre d'outils par
    # thème, séparés par un trait dans le menu.
    themes: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            QT_TRANSLATE_NOOP("Workbench", "Pièces"),
            (
                "Menuiserie_WoodPart",  # pièce en bois
                "Menuiserie_ShapedPart",  # pièce à forme libre (PD-d)
                "Menuiserie_SetDistance",  # distance entre deux pièces (DI-b)
            ),
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Assemblages"),
            (
                "Menuiserie_MortiseTenon",
                "Menuiserie_TongueGroove",
                "Menuiserie_Rabbet",
                "Menuiserie_Dowels",
                "Menuiserie_LooseTenon",
                "Menuiserie_Biscuit",
                "Menuiserie_HalfLap",
                "Menuiserie_Dovetail",
                "Menuiserie_Miter",
            ),
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Quincaillerie"),
            (
                "Menuiserie_Foot",
                "Menuiserie_ShelfPins",
                "Menuiserie_DrawerSlide",
            ),
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Ensembles"),
            (
                "Menuiserie_Furniture",  # (J4c)
                "Menuiserie_FurnitureAdd",
                "Menuiserie_FurnitureRemove",
                "Menuiserie_FurnitureRebind",
                "Menuiserie_Carcass",  # gabarits (J4d)
            ),
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Vue"),
            ("Menuiserie_Structure",),  # panneau « Structure » (ADR 0046)
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Répétition"),
            (
                "Menuiserie_Repeat",  # (R-c)
                "Menuiserie_RepeatEdit",
                "Menuiserie_RepeatDissociate",
            ),
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Liste de débit"),
            (
                "Menuiserie_CutList",  # (J2d, J2g)
                "Menuiserie_CutListPreview",
                "Menuiserie_CutListExport",
                "Menuiserie_CutListPdf",
                "Menuiserie_NumberMarks",
            ),
        ),
        (
            QT_TRANSLATE_NOOP("Workbench", "Plans"),
            (
                "Menuiserie_Drawing",  # plans cotés (issue #153, ADR 0053)
                "Menuiserie_DrawingPdf",
            ),
        ),
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
        from freecad.menuiserie.gui.commands import drawing  # plans cotés (issue #153)

        drawing.register()
        from freecad.menuiserie.gui.commands import distance  # distance entre deux pièces (DI-b)

        distance.register()
        from freecad.menuiserie.gui.commands import shaped_part  # pièce en bois (PD-d)

        shaped_part.register()
        from freecad.menuiserie.gui.commands import structure  # panneau « Structure » (ADR 0046)

        structure.register()
        from freecad.menuiserie.gui.commands import repeat  # répétition de pièces (R-c)

        repeat.register()
        # Un menu, thèmes séparés : FreeCAD déforme les accents du titre d'un sous-menu.
        menu: list[str] = []
        for theme, names in self.themes:
            title = translate("Workbench", theme)
            self.appendToolbar(f"{translate('Workbench', 'Menuiserie')} : {title}", list(names))
            menu += [*names, "Separator"]
        self.appendMenu(translate("Workbench", "&Menuiserie"), menu[:-1])

    def Activated(self) -> None:
        """Atelier actif : double-clic dans la vue 3D sur ses objets (ADR 0018) et flèches de
        déplacement de la pièce sélectionnée (ADR 0021)."""
        from freecad.menuiserie.gui import click_select, double_click
        from freecad.menuiserie.gui.drag import events

        try:
            double_click.install()
            click_select.install()  # après le double-clic : Qt appelle le dernier posé d'abord
        finally:
            events.install()
        from freecad.menuiserie.gui.structure_panel import open_by_default_later

        open_by_default_later()  # panneau « Structure » ouvert par défaut (ADR 0046)

    def Deactivated(self) -> None:
        """Atelier quitté : filtres, observateur de sélection et flèches sont retirés."""
        from freecad.menuiserie.gui import click_select, double_click
        from freecad.menuiserie.gui.drag import events

        try:
            click_select.uninstall()
        finally:
            try:
                double_click.uninstall()
            finally:
                events.uninstall()

    def ContextMenu(self, recipient: str) -> None:
        """Menu contextuel de la vue 3D (« View ») et de l'arborescence (« Tree ») : « Définir une
        distance » (au premier niveau, pas dans un sous-menu) quand la sélection compte deux
        éléments de deux objets. Ce menu n'existe que
        pendant que l'atelier est actif (ADR 0007)."""
        from freecad.menuiserie.gui.commands import distance

        if distance.selected_pair() is not None:
            self.appendContextMenu("", [distance.COMMAND_NAME])  # au premier niveau du menu

    def GetClassName(self) -> str:
        """Type C++ de l'atelier attendu par FreeCAD pour un atelier écrit en Python."""
        return "Gui::PythonWorkbench"


Gui.addWorkbench(MenuiserieWorkbench())
