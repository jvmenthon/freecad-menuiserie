# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Aligner deux faces » (AL-c, ADR 0054).

Active quand la sélection compte exactement deux faces de deux objets différents. La commande
tourne puis plaque la seconde pièce (ou la première si la seconde n'est pas de l'atelier) : une
seule entrée d'annulation, les assemblages défaits sont proposés avant tout recalcul (ADR 0026).
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.align import AlignMode
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.drag_joints import DragCancelledError
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_align import FaceAlign
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.commands import hints
from freecad.menuiserie.gui.commands.base import TransactionCommand, refusable_transaction
from freecad.menuiserie.gui.commands.distance import selected_pair
from freecad.menuiserie.gui.selection import view_direction

COMMAND_NAME: Final = "Menuiserie_AlignFaces"
_CANCELLED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Alignement annulé : rien n'a bougé.")


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
        """Aligne dans une transaction ; refus : message, rien n'est modifié."""
        pair = selected_pair()
        doc = App.ActiveDocument
        if pair is None or doc is None:
            return
        with refusable_transaction(doc, self.TRANSACTION):
            try:
                aligned = FaceAlign(*pair, toward_observer=view_direction())
                _alignment, messages = aligned.apply(AlignMode.AUTO, joint_choice.choose)
            except DragCancelledError:  # assemblages défaits, « Annuler le déplacement »
                raise ValueError(translated(_CANCELLED)) from None
            report(messages)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, AlignFacesCommand())
