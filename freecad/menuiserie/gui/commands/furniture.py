# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de l'ensemble (J4c, critère P1) : créer un ensemble depuis la sélection, y ajouter
des pièces, les en retirer, « Relier les pièces ».

Chaque commande appelle l'api dans sa propre transaction (une entrée d'annulation) ; un refus
de l'api n'en laisse aucune et s'affiche dans la barre d'état et la vue rapport ; les
avertissements des liaisons vont dans la vue rapport (api) et la barre d'état. Les pièces
sélectionnées peuvent être des pièces de bois, des pièces usinées ou des ensembles.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import (
    furniture_of,
    has_member_properties,
    is_furniture,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.gui.commands.joints import (
    REFUSAL_DISPLAY_MS,
    TransactionCommand,
    report_refusal,
)
from freecad.menuiserie.gui.task_panels.base import close_transaction

Action = Callable[[], Sequence[str]]  # action de la commande, renvoie ses avertissements

# Noms des commandes, aussi noms de leurs icônes (``<nom>.svg``) et contextes de traduction.
FURNITURE: Final = "Menuiserie_Furniture"
FURNITURE_ADD: Final = "Menuiserie_FurnitureAdd"
FURNITURE_REMOVE: Final = "Menuiserie_FurnitureRemove"
FURNITURE_REBIND: Final = "Menuiserie_FurnitureRebind"
COMMANDS: Final = (FURNITURE, FURNITURE_ADD, FURNITURE_REMOVE, FURNITURE_REBIND)


def is_candidate(obj: DocumentObject) -> bool:
    """Vrai pour ce qui peut être membre d'un ensemble : pièce de bois, pièce usinée d'une
    pièce de bois, ensemble."""
    return (
        is_wood_part(obj) or is_furniture(obj) or (is_machined_part(obj) and is_wood_part(obj.Base))
    )


def selected_candidates() -> list[DocumentObject] | None:
    """Sélection, si elle n'est faite que de pièces et d'ensembles (``None`` sinon)."""
    selection = Gui.Selection.getSelection()
    if not selection or not all(is_candidate(obj) for obj in selection):
        return None
    return list(selection)


def target_and_others() -> tuple[DocumentObject, list[DocumentObject]] | None:
    """Ensemble choisi (le premier sélectionné) et les autres objets sélectionnés."""
    selection = selected_candidates() or []
    target = next((obj for obj in selection if is_furniture(obj)), None)
    others = [obj for obj in selection if obj is not target]
    return (target, others) if target is not None and others else None


def _member(obj: DocumentObject) -> DocumentObject:
    return obj if is_furniture(obj) else blank_of(obj)


class FurnitureCommand(TransactionCommand):
    """Base des commandes de l'ensemble (Command) : chaque sous-classe fournit ses textes,
    l'objet de sa transaction et :meth:`action` (``None`` si la sélection ne convient pas)."""

    def IsActive(self) -> bool:
        """Active s'il y a un document, aucun panneau ouvert et une sélection qui convient."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and self.action() is not None
        )

    def Activated(self) -> None:
        """Action dans la transaction de la commande, validée (une entrée d'annulation) ou
        abandonnée sur un refus, signalé dans la barre d'état et la vue rapport."""
        action = self.action()
        if action is None:
            return
        doc = App.ActiveDocument
        shown = concerned_furniture()
        doc.openTransaction(translated(self.TRANSACTION))
        transaction = App.getActiveTransaction()
        try:
            messages = action()
            refresh_tree(shown)
        except (TypeError, ValueError) as error:
            close_transaction(transaction, abort=True)
            report_refusal(str(error))
            return
        except BaseException:
            close_transaction(transaction, abort=True)
            raise
        close_transaction(transaction, abort=False)
        show_notices(messages)

    def action(self) -> Action | None:
        """Action à mener sur la sélection actuelle, ``None`` si elle ne convient pas."""
        raise NotImplementedError


def concerned_furniture() -> list[DocumentObject]:
    """Ensembles sélectionnés et ensembles des membres sélectionnés."""
    found = []
    for obj in selected_candidates() or []:
        member = _member(obj)
        found += [item for item in (member, furniture_of(member)) if is_furniture(item)]
    return found


def refresh_tree(furniture: list[DocumentObject]) -> None:
    """L'arbre ne relit les enfants d'un objet que s'il change : les ensembles dont les membres
    ont changé sont marqués à recalculer (leur ``execute`` ne fait que contrôler les cotes)."""
    for obj in furniture:
        if is_furniture(obj):
            obj.touch()
    if furniture:
        furniture[0].Document.recompute()


def show_notices(messages: Sequence[str]) -> None:
    """Avertissements (déjà dans la vue rapport) rappelés dans la barre d'état."""
    window = Gui.getMainWindow()
    if messages and window is not None:
        window.statusBar().showMessage(" ".join(messages), REFUSAL_DISPLAY_MS)


class CreateFurnitureCommand(FurnitureCommand):
    """Crée un ensemble autour des pièces sélectionnées."""

    NAME = FURNITURE
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Furniture", "Ensemble")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Furniture",
        "Regroupe les pièces sélectionnées dans un ensemble à cotes globales (largeur, "
        "profondeur, hauteur) : quand une cote change, chaque pièce suit les bords dont la "
        "distance est fixe. Double-cliquez l'ensemble pour régler ses cotes et ses pièces.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un ensemble")

    def action(self) -> Action | None:
        """``make_furniture`` sur la sélection."""
        selection = selected_candidates()
        if selection is None:
            return None
        return lambda: api.make_furniture(selection)[1]


class AddToFurnitureCommand(FurnitureCommand):
    """Ajoute les pièces sélectionnées à l'ensemble sélectionné."""

    NAME = FURNITURE_ADD
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_FurnitureAdd", "Ajouter à l'ensemble")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_FurnitureAdd",
        "Ajoute les pièces sélectionnées au premier ensemble sélectionné : elles suivent ses "
        "cotes, toutes leurs distances aux bords étant fixes par défaut.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Ajouter à l'ensemble")

    def action(self) -> Action | None:
        """``add_to_furniture`` : premier ensemble sélectionné, autres objets."""
        chosen = target_and_others()
        if chosen is None:
            return None
        target, others = chosen
        return lambda: api.add_to_furniture(target, others)


class RemoveFromFurnitureCommand(FurnitureCommand):
    """Retire les pièces sélectionnées de leur ensemble."""

    NAME = FURNITURE_REMOVE
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_FurnitureRemove", "Retirer de l'ensemble")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_FurnitureRemove",
        "Retire les pièces sélectionnées de leur ensemble : elles gardent leur forme et leur "
        "place, mais ne suivent plus ses cotes.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Retirer de l'ensemble")

    def action(self) -> Action | None:
        """``remove_from_furniture`` : sélection faite de membres seulement."""
        selection = selected_candidates()
        if selection is None or not all(has_member_properties(_member(o)) for o in selection):
            return None

        def remove() -> Sequence[str]:
            api.remove_from_furniture(selection)
            return ()

        return remove


class RebindFurnitureCommand(FurnitureCommand):
    """« Relier les pièces » de l'ensemble sélectionné."""

    NAME = FURNITURE_REBIND
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_FurnitureRebind", "Relier les pièces")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_FurnitureRebind",
        "Recalcule les expressions qui relient les pièces de l'ensemble sélectionné à ses "
        "cotes, d'après leur position actuelle (après une retouche à la main) ; les options "
        "« fixe » sont gardées.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Relier les pièces")

    def action(self) -> Action | None:
        """``rebind_furniture`` : un seul ensemble sélectionné."""
        selection = selected_candidates()
        if selection is None or len(selection) != 1 or not is_furniture(selection[0]):
            return None
        furniture = selection[0]
        return lambda: api.rebind_furniture(furniture)


def register() -> None:
    """Enregistre les commandes de l'ensemble auprès de FreeCAD."""
    Gui.addCommand(FURNITURE, CreateFurnitureCommand())
    Gui.addCommand(FURNITURE_ADD, AddToFurnitureCommand())
    Gui.addCommand(FURNITURE_REMOVE, RemoveFromFurnitureCommand())
    Gui.addCommand(FURNITURE_REBIND, RebindFurnitureCommand())
