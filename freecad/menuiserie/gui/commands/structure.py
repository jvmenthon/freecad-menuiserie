# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Structure » : ouvre le panneau ancré de l'arbre simplifié (ADR 0046, lot 1).

Cette commande n'écrit rien dans le document ; le panneau est dans ``gui/structure_panel``.
"""

from __future__ import annotations

from typing import Final

import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.gui.structure_panel import show_panel

COMMAND_NAME: Final = "Menuiserie_Structure"


class StructureCommand:
    """Ouvre le panneau « Structure » à côté de l'arbre de FreeCAD, qui n'est pas modifié."""

    NAME = COMMAND_NAME
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Structure", "Structure")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Structure",
        "Ouvre le panneau « Structure » : l'arbre simplifié des ensembles, de leurs pièces et "
        "de leurs assemblages. Clic droit ou glisser-déposer pour ranger les pièces dans les "
        "ensembles ; l'arbre de FreeCAD reste inchangé.",
    )

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(f"{self.NAME}.svg"),
            "MenuText": self.MENU_TEXT,
            "ToolTip": self.TOOL_TIP,
        }

    def IsActive(self) -> bool:
        """Toujours active : le panneau s'ouvre aussi sans document."""
        return True

    def Activated(self) -> None:
        """Ouvre (ou rafraîchit) le panneau."""
        show_panel()


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, StructureCommand())
