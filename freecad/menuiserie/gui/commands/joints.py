# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes d'assemblage : une classe par type sur la base commune :class:`JointCommand`.

Chaque commande relie les deux pièces sélectionnées (pièces de bois ou pièces usinées) par la
fabrique ``FACTORY`` de :mod:`freecad.menuiserie.api`, puis ouvre le panneau de l'assemblage
(J3e) ; « Annuler » ne laisse rien. Un refus de la fabrique est affiché dans la barre d'état et
la vue rapport. Les rôles (hôte, invitée) sont devinés d'après la
position des pièces (``guess_roles``) ; si c'est ambigu, la première pièce sélectionnée reçoit
la mortaise, la rainure ou la feuillure.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api, icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import guess_roles
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.joints.base import placed_blank
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.wood_part import is_wood_part
from freecad.menuiserie.gui.task_panels.base import close_transaction
from freecad.menuiserie.gui.task_panels.joint import show_panel

Factory = Callable[[DocumentObject, DocumentObject], DocumentObject]

PAIR: Final = 2
REFUSAL_DISPLAY_MS: Final = 15_000  # durée d'affichage d'un refus dans la barre d'état
# Noms des commandes, aussi noms de leurs icônes (``<nom>.svg``) et contextes de traduction.
MORTISE_TENON: Final = "Menuiserie_MortiseTenon"
TONGUE_GROOVE: Final = "Menuiserie_TongueGroove"
RABBET: Final = "Menuiserie_Rabbet"
DOWELS: Final = "Menuiserie_Dowels"


class JointCommand:
    """Base des commandes d'assemblage (Command) : chaque sous-classe fournit son nom, la
    fabrique de l'api, ses textes et le nom de sa transaction."""

    NAME: ClassVar[str]
    FACTORY: ClassVar[Factory]  # fabrique de freecad.menuiserie.api, lue sur la classe
    MENU_TEXT: ClassVar[str]
    TOOL_TIP: ClassVar[str]
    TRANSACTION: ClassVar[str]

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(f"{self.NAME}.svg"),
            "MenuText": self.MENU_TEXT,
            "ToolTip": self.TOOL_TIP,
        }

    def IsActive(self) -> bool:
        """Active si aucun panneau n'est ouvert et que deux pièces distinctes sont
        sélectionnées."""
        return (
            App.ActiveDocument is not None
            and not Gui.Control.activeDialog()
            and selected_parts() is not None
        )

    def Activated(self) -> None:
        """Assemblage créé dans la transaction « Créer un assemblage … », puis panneau de
        l'assemblage qui la valide (une entrée d'annulation) ou l'abandonne ; une pièce refusée
        par la fabrique est signalée sans rien créer."""
        parts = selected_parts()
        if parts is None:
            return
        host, guest = ordered_roles(*parts)
        doc = App.ActiveDocument
        doc.openTransaction(translated(self.TRANSACTION))
        transaction = App.getActiveTransaction()
        try:
            joint = type(self).FACTORY(host, guest)
        except (TypeError, ValueError) as error:
            close_transaction(transaction, abort=True)
            report_refusal(str(error))
            return
        except BaseException:
            close_transaction(transaction, abort=True)
            raise
        show_panel(joint)


class MortiseTenonCommand(JointCommand):
    """Tenon-mortaise : mortaise dans une pièce, tenon au bout de l'autre."""

    NAME = MORTISE_TENON
    FACTORY = api.make_mortise_tenon
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_MortiseTenon", "Tenon-mortaise")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_MortiseTenon",
        "Relie les deux pièces sélectionnées par un tenon-mortaise : la pièce dont le bout touche "
        "l'autre porte le tenon (à défaut, la seconde sélectionnée).",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage tenon-mortaise")


class TongueGrooveCommand(JointCommand):
    """Rainure-languette : rainure dans une pièce, languette sur le chant de l'autre."""

    NAME = TONGUE_GROOVE
    FACTORY = api.make_tongue_groove
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_TongueGroove", "Rainure-languette")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_TongueGroove",
        "Relie les deux pièces sélectionnées par une rainure-languette : la pièce qui touche "
        "l'autre par son chant porte la languette (à défaut, la seconde sélectionnée).",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage rainure-languette")


class RabbetCommand(JointCommand):
    """Feuillure (ou logement) : la pièce la plus mince se loge dans l'autre."""

    NAME = RABBET
    FACTORY = api.make_rabbet
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Rabbet", "Feuillure")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Rabbet",
        "Creuse une feuillure ou un logement dans une pièce là où l'autre la chevauche : la "
        "pièce la plus mince est logée (à épaisseur égale, la seconde sélectionnée).",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage à feuillure")


class DowelsCommand(JointCommand):
    """Tourillons : perçages en vis-à-vis dans les deux pièces."""

    NAME = DOWELS
    FACTORY = api.make_dowels
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Dowels", "Tourillons")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Dowels",
        "Relie les deux pièces sélectionnées par des tourillons : nombre, diamètre et longueur "
        "automatiques d'après la surface de contact.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage à tourillons")


def selected_parts() -> tuple[DocumentObject, DocumentObject] | None:
    """Les deux pièces sélectionnées (dans l'ordre de sélection), ou ``None`` si la sélection
    n'est pas exactement deux pièces (brutes ou usinées) de brutes distinctes."""
    selection = Gui.Selection.getSelection()
    if len(selection) != PAIR or not all(_is_part(obj) for obj in selection):
        return None
    first, second = selection
    if blank_of(first) == blank_of(second):
        return None
    return first, second


def ordered_roles(
    first: DocumentObject, second: DocumentObject
) -> tuple[DocumentObject, DocumentObject]:
    """(hôte, invitée) devinés d'après la position des brutes ; ordre de sélection si c'est
    ambigu ou si une cote est invalide."""
    try:
        host_index, guest_index = guess_roles(
            placed_blank(blank_of(first)), placed_blank(blank_of(second))
        )
    except ValueError:
        return first, second
    pair = (first, second)
    return pair[host_index], pair[guest_index]


def report_refusal(message: str) -> None:
    """Refus de la fabrique : barre d'état de la fenêtre principale et vue rapport."""
    report_warning(message)
    window = Gui.getMainWindow()
    if window is not None:
        window.statusBar().showMessage(message, REFUSAL_DISPLAY_MS)


def _is_part(obj: DocumentObject) -> bool:
    return is_wood_part(obj) or (is_machined_part(obj) and is_wood_part(obj.Base))


def register() -> None:
    """Enregistre les quatre commandes auprès de FreeCAD."""
    Gui.addCommand(MORTISE_TENON, MortiseTenonCommand())
    Gui.addCommand(TONGUE_GROOVE, TongueGrooveCommand())
    Gui.addCommand(RABBET, RabbetCommand())
    Gui.addCommand(DOWELS, DowelsCommand())
