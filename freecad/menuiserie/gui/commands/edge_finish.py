# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Finition des chants » (issue #5, C1) : profil des arêtes de la pièce sélectionnée.

Active dès qu'un document est ouvert et qu'aucun panneau de tâche ne l'est. Sans sélection, le
panneau demande de désigner dans la vue 3D une pièce, une face ou une arête ; avec une pièce
(brute ou usinée), une face, une arête ou un sommet sélectionné, ils sont déjà choisis ; avec un
profil d'arête, sa modification. Une pièce en bois (forme dessinée) est refusée avec un message
clair.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.box_parts import box_part_refusal
from freecad.menuiserie.features.edge_profile import is_edge_profile
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.shaped_part import is_shaped_part
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.pick_edge import selected_pick
from freecad.menuiserie.gui.task_panels.edge_finish import (
    CREATE_TRANSACTION,
    show_panel,
    start_editing,
)
from freecad.menuiserie.gui.view_providers.edge_profile import ICON

COMMAND_NAME: Final = "Menuiserie_EdgeFinish"


def selected_part() -> DocumentObject | None:
    """Pièce de bois (brute) ou profil d'arête sélectionné, ``None`` sinon : un seul objet
    sélectionné, une pièce usinée étant ramenée à sa brute."""
    selection = Gui.Selection.getSelection()
    if len(selection) != 1:
        return None
    obj = selection[0]
    if is_machined_part(obj):
        obj = obj.Base
    if is_wood_part(obj) or is_shaped_part(obj) or is_edge_profile(obj):
        return obj
    return None


class EdgeFinishCommand:
    """Ouvre le panneau des profils d'arête de la pièce sélectionnée, dans la transaction
    « Finition des chants » (ou, sur un profil, la modification de ce profil)."""

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(ICON),
            "MenuText": QT_TRANSLATE_NOOP("Menuiserie_EdgeFinish", "Finition des chants"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "Menuiserie_EdgeFinish",
                "Donne un profil aux arêtes d'une pièce de bois : quart de rond (arête cassée), "
                "chanfrein, gorge, demi-rond, bec-de-corbin ou doucine. Sélectionnez avant une "
                "face, une arête ou un sommet pour cocher ses arêtes. Les cotes finies ne "
                "changent pas.",
            ),
        }

    def IsActive(self) -> bool:
        """Active avec un document et sans panneau ouvert : sans sélection, le panneau demande de
        désigner la pièce, la face ou l'arête."""
        return App.ActiveDocument is not None and not Gui.Control.activeDialog()

    def Activated(self) -> None:
        """Profil sélectionné : sa modification ; pièce dessinée : refusée ; sinon le panneau,
        avec la pièce, les faces et les arêtes sélectionnées déjà choisies (ou aucune)."""
        target = selected_part()
        if target is not None and is_edge_profile(target):
            start_editing(target)
            return
        refusal = None if target is None else box_part_refusal(target)
        if refusal is not None:
            report_refusal(refusal)
            return
        pick = selected_pick(target)
        App.ActiveDocument.openTransaction(translated(CREATE_TRANSACTION))
        show_panel(target if pick is None else pick.part, preselected=pick)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, EdgeFinishCommand())
