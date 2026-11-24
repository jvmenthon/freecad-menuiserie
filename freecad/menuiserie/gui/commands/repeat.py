# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes de la répétition (R-c, ADR 0043) : « Répéter » (pièces sélectionnées), « Modifier la
répétition » (une répétition ou une de ses copies) et « Dissocier la répétition » (toutes les
copies d'une répétition deviennent libres, la répétition est supprimée).

« Répéter » et « Modifier la répétition » ouvrent le panneau de tâche, qui montre les copies en
direct et appelle l'api ; « Dissocier la répétition » appelle l'api dans sa propre transaction (une
entrée d'annulation). Un refus de l'api n'en laisse aucune et s'affiche dans la barre d'état et
la vue rapport. ``IsActive`` n'examine que la sélection.
"""

from __future__ import annotations

from typing import Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.furniture import is_furniture
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.machined_part import blank_or_self
from freecad.menuiserie.features.repeat import is_copy
from freecad.menuiserie.features.repeat_copies import checked_sources
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.gui.commands import hints
from freecad.menuiserie.gui.commands.base import (
    TransactionCommand,
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
    """Vrai pour une pièce de bois, une pièce en bois ou un ensemble qui n'est pas déjà une copie
    liée, ou pour la pièce usinée d'une pièce de bois (la répétition porte sur la pièce brute)."""
    blank = blank_or_self(obj)
    return (is_timber(blank) or is_furniture(blank)) and not is_copy(blank)


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
    return api.repeat_of(blank_or_self(chosen))


def selected_repeats() -> list[DocumentObject] | None:
    """Répétitions des objets sélectionnés (une répétition ou ses copies liées), chacune une
    fois, ou ``None`` si la sélection contient autre chose. Une pièce usinée compte pour sa
    brute : une copie assemblée est affichée et choisie par sa pièce usinée."""
    found = [api.repeat_of(blank_or_self(obj)) for obj in Gui.Selection.getSelection()]
    if not found or any(rep is None for rep in found):
        return None
    unique = {rep.Name: rep for rep in found if rep is not None}  # copies d'une même répétition
    return list(unique.values())


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
    PREREQUISITE = hints.REPEAT

    def IsActive(self) -> bool:
        """Active avec un document, aucun panneau ouvert et des pièces à répéter sélectionnées."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and selected_repeatable() is not None
        )

    def Activated(self) -> None:
        """Pièces contrôlées d'emblée (refus signalé, rien créé), puis panneau ouvert dans la
        transaction « Répéter » que « OK » valide et « Annuler » abandonne."""
        selection = selected_repeatable()
        if selection is None:
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
    PREREQUISITE = hints.REPEAT_EDIT

    def IsActive(self) -> bool:
        """Active avec un document, aucun panneau ouvert et une répétition ou une copie liée
        sélectionnée."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and selected_repeat() is not None
        )

    def Activated(self) -> None:
        """Mode d'édition de la répétition : son ViewProvider ouvre le panneau prérempli, dans
        la transaction « Modifier la répétition »."""
        repeat = selected_repeat()
        if repeat is None:
            return
        ensure_view_provider(repeat)
        Gui.getDocument(repeat.Document.Name).setEdit(repeat, 0)


class DissociateCommand(TransactionCommand):
    """Dissocie les répétitions sélectionnées (par elles-mêmes ou par l'une de leurs copies) :
    toutes leurs copies deviennent des pièces libres et les répétitions sont supprimées."""

    NAME = REPEAT_DISSOCIATE
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_RepeatDissociate", "Dissocier la répétition")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_RepeatDissociate",
        "Détache toutes les copies de la répétition sélectionnée (ou de la répétition dont la "
        "copie est sélectionnée) : elles gardent leurs valeurs actuelles et deviennent des "
        "pièces libres, avec leurs assemblages ; l'original ne les pilote plus et la "
        "répétition est supprimée.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Dissocier la répétition")
    PREREQUISITE = hints.REPEAT_DISSOCIATE

    def IsActive(self) -> bool:
        """Active avec un document, aucun panneau ouvert et seulement des répétitions ou des
        copies liées sélectionnées."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and selected_repeats() is not None
        )

    def Activated(self) -> None:
        """Répétitions dissociées dans une seule transaction, validée ou, sur un refus (signalé
        dans la barre d'état et la vue rapport), abandonnée."""
        repeats = selected_repeats()
        if repeats is None:
            return
        with refusable_transaction(repeats[0].Document, self.TRANSACTION):
            for rep in repeats:
                api.dissociate(rep, transaction=False)


def register() -> None:
    """Enregistre les commandes auprès de FreeCAD."""
    Gui.addCommand(REPEAT, RepeatCommand())
    Gui.addCommand(REPEAT_EDIT, EditRepeatCommand())
    Gui.addCommand(REPEAT_DISSOCIATE, DissociateCommand())
