# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de l'ensemble (J4c, critère P1) : créer un ensemble depuis la sélection, y ajouter
des pièces, les en retirer, « Relier les pièces ».

Chaque commande appelle l'api dans sa propre transaction (une entrée d'annulation) ; un refus
de l'api n'en laisse aucune et s'affiche dans la barre d'état et la vue rapport ; les
avertissements des liaisons vont dans la vue rapport (api) et la barre d'état. Les pièces
sélectionnées peuvent être des pièces de bois, des pièces usinées ou des ensembles.
"""

from __future__ import annotations

from collections.abc import Sequence
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
from freecad.menuiserie.features.furniture_members import member_object
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.gui.commands.base import (
    REFUSAL_DISPLAY_MS,
    TransactionCommand,
    report_refusal,
)
from freecad.menuiserie.gui.task_panels.base import close_transaction

# Noms des commandes, aussi noms de leurs icônes (``<nom>.svg``) et contextes de traduction.
FURNITURE: Final = "Menuiserie_Furniture"
FURNITURE_ADD: Final = "Menuiserie_FurnitureAdd"
FURNITURE_REMOVE: Final = "Menuiserie_FurnitureRemove"
FURNITURE_REBIND: Final = "Menuiserie_FurnitureRebind"
COMMANDS: Final = (FURNITURE, FURNITURE_ADD, FURNITURE_REMOVE, FURNITURE_REBIND)


def is_candidate(obj: DocumentObject) -> bool:
    """Vrai pour ce qui peut être membre d'un ensemble : pièce de bois ou pièce en bois, pièce
    usinée de l'une d'elles, ensemble."""
    return is_timber(obj) or is_furniture(obj) or (is_machined_part(obj) and is_timber(obj.Base))


def selected_candidates() -> list[DocumentObject] | None:
    """Sélection, si elle n'est faite que de pièces et d'ensembles (``None`` sinon)."""
    selection = Gui.Selection.getSelection()
    if not selection or not all(is_candidate(obj) for obj in selection):
        return None
    return list(selection)


def target_and_others(
    selection: Sequence[DocumentObject],
) -> tuple[DocumentObject, list[DocumentObject]] | None:
    """Ensemble choisi (le premier de ``selection``) et les autres objets de ``selection``."""
    target = next((obj for obj in selection if is_furniture(obj)), None)
    others = [obj for obj in selection if obj is not target]
    return (target, others) if target is not None and others else None


class FurnitureCommand(TransactionCommand):
    """Base des commandes de l'ensemble (Command) : chaque sous-classe fournit ses textes,
    l'objet de sa transaction, :meth:`accepts` (la sélection convient-elle ?) et :meth:`apply`
    (l'action sur une sélection acceptée)."""

    def IsActive(self) -> bool:
        """Active s'il y a un document, aucun panneau ouvert et une sélection qui convient.
        Appelée à chaque rafraîchissement de l'interface : la sélection est seulement
        examinée, aucune action n'est préparée."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and self._accepted_selection() is not None
        )

    def Activated(self) -> None:
        """Action dans la transaction de la commande, validée (une entrée d'annulation) ou
        abandonnée sur un refus, signalé dans la barre d'état et la vue rapport."""
        selection = self._accepted_selection()
        if selection is None:
            return
        doc = App.ActiveDocument
        shown = concerned_furniture()
        doc.openTransaction(translated(self.TRANSACTION))
        transaction = App.getActiveTransaction()
        try:
            messages = self.apply(selection)
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

    def _accepted_selection(self) -> list[DocumentObject] | None:
        """Sélection actuelle si elle ne contient que des pièces et des ensembles et que la
        commande l'accepte, ``None`` sinon."""
        selection = selected_candidates()
        return selection if selection is not None and self.accepts(selection) else None

    def accepts(self, selection: Sequence[DocumentObject]) -> bool:
        """Vrai si la commande peut agir sur ``selection`` (pièces et ensembles seulement)."""
        raise NotImplementedError

    def apply(self, selection: Sequence[DocumentObject]) -> Sequence[str]:
        """Action sur ``selection`` acceptée ; renvoie les avertissements traduits."""
        raise NotImplementedError


def concerned_furniture() -> list[DocumentObject]:
    """Ensembles sélectionnés et ensembles des membres sélectionnés."""
    found = []
    for obj in selected_candidates() or []:
        member = member_object(obj)
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

    def accepts(self, selection: Sequence[DocumentObject]) -> bool:
        """Toute sélection de pièces et d'ensembles."""
        return bool(selection)

    def apply(self, selection: Sequence[DocumentObject]) -> Sequence[str]:
        """``make_furniture`` sur la sélection."""
        return api.make_furniture(selection)[1]


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

    def accepts(self, selection: Sequence[DocumentObject]) -> bool:
        """Un ensemble et au moins un autre objet."""
        return target_and_others(selection) is not None

    def apply(self, selection: Sequence[DocumentObject]) -> Sequence[str]:
        """``add_to_furniture`` : premier ensemble sélectionné, autres objets."""
        chosen = target_and_others(selection)
        return api.add_to_furniture(*chosen) if chosen is not None else ()


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

    def accepts(self, selection: Sequence[DocumentObject]) -> bool:
        """Sélection faite de membres seulement."""
        return all(has_member_properties(member_object(obj)) for obj in selection)

    def apply(self, selection: Sequence[DocumentObject]) -> Sequence[str]:
        """``remove_from_furniture`` sur la sélection."""
        return api.remove_from_furniture(selection)


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

    def accepts(self, selection: Sequence[DocumentObject]) -> bool:
        """Un seul ensemble sélectionné."""
        return len(selection) == 1 and is_furniture(selection[0])

    def apply(self, selection: Sequence[DocumentObject]) -> Sequence[str]:
        """``rebind_furniture`` sur l'ensemble sélectionné."""
        return api.rebind_furniture(selection[0])


def register() -> None:
    """Enregistre les commandes de l'ensemble auprès de FreeCAD."""
    Gui.addCommand(FURNITURE, CreateFurnitureCommand())
    Gui.addCommand(FURNITURE_ADD, AddToFurnitureCommand())
    Gui.addCommand(FURNITURE_REMOVE, RemoveFromFurnitureCommand())
    Gui.addCommand(FURNITURE_REBIND, RebindFurnitureCommand())
