# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Finition des chants » (issue #5, C1) : profil des arêtes des pièces sélectionnées.

Active dès qu'un document est ouvert et qu'aucun panneau de tâche ne l'est. Sans sélection, le
panneau demande de désigner dans la vue 3D des pièces, faces ou arêtes ; avec des pièces (brutes
ou usinées), faces, arêtes ou sommets sélectionnés, ils sont déjà choisis, une carte par pièce ;
avec un profil d'arête, sa modification. Une pièce en bois dont la forme n'est pas une boîte est
refusée avec un message clair.
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
from freecad.menuiserie.gui.pick_edge import selected_picks
from freecad.menuiserie.gui.task_panels.edge_finish import (
    CREATE_TRANSACTION,
    show_panel,
    start_editing,
)
from freecad.menuiserie.gui.view_providers.edge_profile import ICON

COMMAND_NAME: Final = "Menuiserie_EdgeFinish"


def selected_profile() -> DocumentObject | None:
    """Profil d'arête sélectionné seul, ``None`` sinon."""
    selection = Gui.Selection.getSelection()
    if len(selection) == 1 and is_edge_profile(selection[0]):
        return selection[0]
    return None


def _selected_parts() -> list[DocumentObject]:
    """Pièces de bois (brutes) sélectionnées, une pièce usinée ramenée à sa brute."""
    parts: list[DocumentObject] = []
    for obj in Gui.Selection.getSelection():
        part = obj.Base if is_machined_part(obj) else obj
        if (is_wood_part(part) or is_shaped_part(part)) and part not in parts:
            parts.append(part)
    return parts


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
        """Profil sélectionné : sa modification ; sinon le panneau, avec les pièces, faces et
        arêtes sélectionnées déjà choisies (ou aucune). Une pièce sélectionnée qui n'est pas une
        boîte est refusée avec un message (dans le panneau s'il y a d'autres pièces)."""
        profile = selected_profile()
        if profile is not None:
            start_editing(profile)
            return
        refusals = [
            refusal for refusal in map(box_part_refusal, _selected_parts()) if refusal is not None
        ]
        picks = [pick for pick in selected_picks() if box_part_refusal(pick.part) is None]
        if refusals and not picks:
            report_refusal("\n".join(refusals))
            return
        App.ActiveDocument.openTransaction(translated(CREATE_TRANSACTION))
        show_panel(picks, refusals)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, EdgeFinishCommand())
