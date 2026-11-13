# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Aligner deux faces » (AL-c, ADR 0054).

Active quand la sélection compte exactement deux faces de deux objets différents. La commande
lit les faces puis ouvre le panneau dans la transaction « Aligner deux faces » : la seconde pièce
(ou la première si la seconde n'est pas de l'atelier) tourne puis se plaque en direct.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_align import FaceAlign
from freecad.menuiserie.gui.commands import hints
from freecad.menuiserie.gui.commands.base import TransactionCommand, report_refusal
from freecad.menuiserie.gui.commands.distance import selected_pair
from freecad.menuiserie.gui.selection import view_direction
from freecad.menuiserie.gui.task_panels.align import open_panel

COMMAND_NAME: Final = "Menuiserie_AlignFaces"


def selected_faces() -> bool:
    """Vrai si la sélection est exactement deux faces de deux objets différents. Lecture seule."""
    pair = selected_pair()
    return pair is not None and all(item.element.startswith("Face") for item in pair)


class AlignFacesCommand(TransactionCommand):
    """Tourne puis plaque une pièce pour que deux faces sélectionnées soient dans le même plan."""

    NAME = COMMAND_NAME
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_AlignFaces", "Aligner deux faces")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_AlignFaces",
        "Aligne deux faces planes sélectionnées (de deux objets) : la seconde pièce de l'atelier "
        "pivote si besoin pour que les faces soient parallèles, puis vient dans le même plan. "
        "La rotation la plus petite est choisie : faces au ras (même sens) ou face contre face.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Aligner deux faces")
    PREREQUISITE = hints.ALIGN_FACES

    def IsActive(self) -> bool:
        """Active avec un document, aucun panneau ouvert et deux faces de deux objets."""
        return (
            App.ActiveDocument is not None and not Gui.Control.activeDialog() and selected_faces()
        )

    def Activated(self) -> None:
        """Lit les faces, refuse ce qui ne s'aligne pas (message dans la barre d'état et la vue
        rapport), puis ouvre le panneau dans une transaction que « OK » valide et « Annuler »
        abandonne."""
        pair = selected_pair()
        doc = App.ActiveDocument
        if pair is None or doc is None:
            return
        try:
            aligned = FaceAlign(*pair, toward_observer=view_direction())
            aligned.plan()  # faces planes ?
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        doc.openTransaction(translated(self.TRANSACTION))
        open_panel(aligned)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, AlignFacesCommand())
