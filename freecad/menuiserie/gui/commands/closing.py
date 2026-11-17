# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commande « Fermer le caisson » (ADR 0064) : crée les côtés, le dessus (ou le dessous), le fond
et les assemblages autour de la pièce sélectionnée, qui n'est ni recréée ni déplacée.

Active quand la sélection est une seule pièce de bois rectangulaire (brute ou usinée), dans la
barre de l'atelier et le menu contextuel (``MenuiserieWorkbench.ContextMenu``). La commande lit la
sélection (face choisie, vue 3D), puis ouvre le panneau dans la transaction « Fermer le caisson ».
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.closing import anchor_blank, default_front_turns, default_role
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.gui.camera import frame_view
from freecad.menuiserie.gui.commands import hints
from freecad.menuiserie.gui.commands.base import TransactionCommand, report_refusal
from freecad.menuiserie.gui.selection import view_direction
from freecad.menuiserie.gui.task_panels.closing import CLOSE_TRANSACTION, show_panel

COMMAND_NAME: Final = "Menuiserie_CloseCarcass"
_FAR_MM: Final = 100_000.0  # l'observateur est loin : seule sa direction compte


def selected_anchor() -> DocumentObject | None:
    """Brute de l'unique pièce de bois rectangulaire sélectionnée, ``None`` sinon. Lecture seule."""
    selection = Gui.Selection.getSelection()
    try:
        return anchor_blank(selection)
    except ValueError:
        return None


def _selected_face() -> tuple[DocumentObject, str] | tuple[None, None]:
    """Objet et nom de la face choisie (``Face3``) ; ``(None, None)`` si aucune."""
    for item in Gui.Selection.getSelectionEx():
        for name in item.SubElementNames:
            if name.startswith("Face"):
                return item.Object, str(name)
    return None, None


def _viewer(anchor: DocumentObject) -> tuple[float, float, float]:
    """Observateur : loin de l'ancre, dans la direction de la caméra."""
    center = anchor.getGlobalPlacement().Base
    toward: Vec3 = view_direction()
    return (
        center.x + toward.x * _FAR_MM,
        center.y + toward.y * _FAR_MM,
        center.z + toward.z * _FAR_MM,
    )


class CloseCarcassCommand(TransactionCommand):
    """Ouvre le panneau « Fermer le caisson » autour de la pièce sélectionnée."""

    NAME = COMMAND_NAME
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_CloseCarcass", "Fermer le caisson")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_CloseCarcass",
        "Génère les côtés, le fond, le dessus (ou le dessous) autour de la pièce sélectionnée, "
        "qui reste telle quelle : hauteur, éléments à créer, assemblages et épaisseurs se règlent "
        "dans le panneau, avec un aperçu. Les pièces forment un ensemble « Caisson ».",
    )
    TRANSACTION = CLOSE_TRANSACTION
    PREREQUISITE = hints.CLOSE_CARCASS

    def IsActive(self) -> bool:
        """Active avec un document, au moins un matériau, aucun panneau ouvert et une pièce de bois
        rectangulaire sélectionnée."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and bool(len(get_library()))
            and selected_anchor() is not None
        )

    def Activated(self) -> None:
        """Lit la sélection (sens, avant), refuse ce qui ne convient pas (message dans la barre
        d'état et la vue rapport), puis ouvre le panneau dans la transaction « Fermer le caisson »,
        que « OK » valide et « Annuler » abandonne."""
        doc = App.ActiveDocument
        try:
            anchor = anchor_blank(Gui.Selection.getSelection())
            picked, face = _selected_face()
            role = default_role(anchor, face, picked)
            turns = default_front_turns(anchor, _viewer(anchor))
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
        try:
            with frame_view():
                doc.openTransaction(translated(CLOSE_TRANSACTION))
                show_panel(doc, anchor, role, turns)  # abandonne la transaction s'il échoue
        except (TypeError, ValueError) as error:  # cotes de l'ancre sans valeurs par défaut
            report_refusal(str(error))


def register() -> None:
    """Enregistre la commande auprès de FreeCAD."""
    Gui.addCommand(COMMAND_NAME, CloseCarcassCommand())
