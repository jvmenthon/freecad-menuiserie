# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Définir une distance » (DI-b, critères E1 et E5, ADR 0022).

Active quand la sélection compte exactement deux éléments (face, arête, sommet) de deux objets
différents : menu et barre d'outils de l'atelier, et menu contextuel de la vue 3D et de
l'arborescence (``MenuiserieWorkbench.ContextMenu``). La commande lit les éléments, refuse
d'emblée ce qui ne peut pas être mesuré (éléments non parallèles, aucune pièce de l'atelier)
puis ouvre le panneau dans la transaction « Définir une distance ».
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.distance_move import DistanceMove
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.gui.commands.base import TransactionCommand, report_refusal
from freecad.menuiserie.gui.selection import picked_elements, view_direction
from freecad.menuiserie.gui.task_panels.distance import open_panel

COMMAND_NAME: Final = "Menuiserie_SetDistance"


def selected_pair() -> tuple[PickedElement, PickedElement] | None:
    """Les deux éléments sélectionnés (face, arête ou sommet) si ce sont bien deux éléments de
    deux objets différents, ``None`` sinon. Lecture seule."""
    elements = picked_elements()
    if len(elements) != 2 or not all(element.is_subelement() for element in elements):
        return None
    first, second = elements
    if first.owner() == second.owner():
        return None
    return first, second


class SetDistanceCommand(TransactionCommand):
    """Amène deux éléments sélectionnés à une distance donnée en déplaçant une pièce."""

    NAME = COMMAND_NAME
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_SetDistance", "Définir une distance")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_SetDistance",
        "Définit la distance entre deux faces, arêtes ou sommets sélectionnés (de deux objets) "
        "en déplaçant une pièce de l'atelier : par défaut la seconde sélectionnée.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Définir une distance")

    def IsActive(self) -> bool:
        """Active avec un document, aucun panneau ouvert et exactement deux éléments de deux
        objets différents. Appelée à chaque rafraîchissement : la sélection est seulement
        examinée."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and selected_pair() is not None
        )

    def Activated(self) -> None:
        """Lit les éléments, refuse ce qui ne se mesure pas (message dans la barre d'état et la
        vue rapport), puis ouvre le panneau dans une transaction que « OK » valide et
        « Annuler » abandonne."""
        pair = selected_pair()
        if pair is None:
            return
        try:
            move = DistanceMove(*pair, toward_observer=view_direction())
            move.gap()  # éléments parallèles ? (D2)
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        doc = App.ActiveDocument
        doc.openTransaction(translated(self.TRANSACTION))
        open_panel(move)


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, SetDistanceCommand())
