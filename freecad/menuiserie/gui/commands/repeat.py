# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de la répétition (R-c, ADR 0043) : « Répéter » (pièces sélectionnées), « Modifier la
répétition » (une répétition ou une de ses copies) et « Dissocier la copie » (copies liées).

« Répéter » et « Modifier la répétition » ouvrent le panneau de tâche, qui montre les copies en
direct et appelle l'api ; « Dissocier la copie » appelle l'api dans sa propre transaction (une
entrée d'annulation). Un refus de l'api n'en laisse aucune et s'affiche dans la barre d'état et
la vue rapport. ``IsActive`` n'examine que la sélection.
"""

from __future__ import annotations

from typing import Final

import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import is_machined_part
from freecad.menuiserie.features.repeat import is_copy
from freecad.menuiserie.features.repeat_copies import checked_sources
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.gui.commands import hints
from freecad.menuiserie.gui.commands.base import (
    TransactionCommand,
    add_command,
    refusable_transaction,
    report_refusal,
)
from freecad.menuiserie.gui.task_panels.repeat import open_panel
from freecad.menuiserie.gui.view_providers.repeat import ensure_view_provider

REPEAT: Final = "Menuiserie_Repeat"
REPEAT_EDIT: Final = "Menuiserie_RepeatEdit"
REPEAT_DISSOCIATE: Final = "Menuiserie_RepeatDissociate"
COMMANDS: Final = (REPEAT, REPEAT_EDIT, REPEAT_DISSOCIATE)


def is_repeatable(obj: DocumentObject) -> bool:
    """Vrai pour une pièce de bois ou un ensemble qui n'est pas déjà une copie liée, ou pour la
    pièce usinée d'une pièce de bois (la répétition porte sur la pièce brute)."""
    blank = obj.Base if is_machined_part(obj) else obj
    return (is_wood_part(blank) or is_furniture(blank)) and not is_copy(blank)


def selected_repeatable() -> list[DocumentObject] | None:
    """Sélection, si elle n'est faite que de pièces à répéter (``None`` sinon)."""
    selection = Gui.Selection.getSelection()
    if not selection or not all(is_repeatable(obj) for obj in selection):
        return None
    return list(selection)


def selected_repeat() -> DocumentObject | None:
    """Répétition de l'unique objet sélectionné (la répétition ou une de ses copies), ``None``
    sinon."""
    selection = Gui.Selection.getSelection()
    if len(selection) != 1:
        return None
    chosen = selection[0]
    return api.repeat_of(chosen.Base if is_machined_part(chosen) else chosen)


def selected_copies() -> list[DocumentObject] | None:
    """Sélection, si elle n'est faite que de copies liées (``None`` sinon)."""
    selection = Gui.Selection.getSelection()
    if not selection or not all(is_copy(obj) for obj in selection):
        return None
    return list(selection)


class RepeatCommand(TransactionCommand):
    """Ouvre le panneau « Répéter » sur les pièces sélectionnées."""

    NAME = REPEAT
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Repeat", "Répéter")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Repeat",
        "Répète les pièces sélectionnées (nombre et pas, nombre sur une longueur, pas sur une "
        "longueur) : les copies suivent l'original, avec ses assemblages, et se modifient "
        "ensuite par « Modifier la répétition ».",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Répéter")
    SELECTION_HINT = hints.REPEAT

    def selection_ok(self) -> bool:
        """Vrai si des pièces à répéter sont sélectionnées."""
        return selected_repeatable() is not None

    def Activated(self) -> None:
        """Pièces contrôlées d'emblée (refus signalé, rien créé), puis panneau ouvert dans la
        transaction « Répéter » que « OK » valide et « Annuler » abandonne."""
        selection = selected_repeatable()
        if selection is None:
            self.explain_selection()
            return
        try:
            sources = checked_sources(selection)
        except (TypeError, ValueError, KeyError) as error:
            report_refusal(str(error.args[0] if isinstance(error, KeyError) else error))
            return
        doc = sources[0].Document
        doc.openTransaction(translated(self.TRANSACTION))
        open_panel(sources)


class EditRepeatCommand(TransactionCommand):
    """Rouvre le panneau d'une répétition, depuis elle ou depuis l'une de ses copies."""

    NAME = REPEAT_EDIT
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_RepeatEdit", "Modifier la répétition")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_RepeatEdit",
        "Rouvre le panneau de la répétition sélectionnée (ou de la répétition dont la copie "
        "est sélectionnée) : nombre, pas, longueur, axe, assemblages.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Modifier la répétition")
    SELECTION_HINT = hints.REPEAT_EDIT

    def selection_ok(self) -> bool:
        """Vrai si une répétition ou une copie liée est sélectionnée."""
        return selected_repeat() is not None

    def Activated(self) -> None:
        """Mode d'édition de la répétition : son ViewProvider ouvre le panneau prérempli, dans
        la transaction « Modifier la répétition »."""
        repeat = selected_repeat()
        if repeat is None:
            self.explain_selection()
            return
        ensure_view_provider(repeat)
        Gui.getDocument(repeat.Document.Name).setEdit(repeat, 0)


class DissociateCommand(TransactionCommand):
    """Dissocie les copies sélectionnées : elles deviennent des pièces libres."""

    NAME = REPEAT_DISSOCIATE
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_RepeatDissociate", "Dissocier la copie")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_RepeatDissociate",
        "Détache la copie sélectionnée de sa répétition : elle garde ses valeurs actuelles et "
        "devient une pièce libre, avec ses assemblages ; l'original ne la suit plus.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Dissocier la copie")
    SELECTION_HINT = hints.REPEAT_DISSOCIATE

    def selection_ok(self) -> bool:
        """Vrai si seules des copies liées sont sélectionnées."""
        return selected_copies() is not None

    def Activated(self) -> None:
        """Copies dissociées dans une seule transaction, validée ou, sur un refus (signalé dans
        la barre d'état et la vue rapport), abandonnée."""
        copies = selected_copies()
        if copies is None:
            self.explain_selection()
            return
        with refusable_transaction(copies[0].Document, self.TRANSACTION):
            for copy in copies:
                if is_copy(copy):  # un ensemble copie dissocié a déjà dissocié ses membres
                    api.dissociate(copy, transaction=False)


def register() -> None:
    """Enregistre les commandes auprès de FreeCAD."""
    add_command(REPEAT, RepeatCommand())
    add_command(REPEAT_EDIT, EditRepeatCommand())
    add_command(REPEAT_DISSOCIATE, DissociateCommand())
