# SPDX-License-Identifier: LGPL-2.1-or-later
"""Commandes d'assemblage : une classe par type sur la base commune :class:`JointCommand`.

Chaque commande relie les deux pièces sélectionnées (pièces de bois ou pièces usinées) par la
fabrique ``FACTORY`` de :mod:`freecad.menuiserie.api`, puis ouvre le panneau de l'assemblage
(J3e) ; « Annuler » ne laisse rien. Un refus de la fabrique, ou un assemblage impossible entre
les pièces telles qu'elles sont posées (pièces qui ne se touchent pas, mi-bois sans croisement…),
est expliqué dans une boîte d'avertissement, la barre d'état et la vue rapport, sans rien créer
ni ouvrir de panneau (demande de jv). L'assemblage est essayé par ``feasible_joint`` avant son
premier recalcul (mot-clé ``check`` de la fabrique) : un assemblage impossible ne fait jamais
imprimer de trace à FreeCAD (ADR 0026). Les rôles (hôte, invitée) sont devinés d'après la
position des pièces (``guess_roles``) ; si c'est ambigu, la première pièce sélectionnée reçoit
la mortaise, la rainure ou la feuillure.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar, Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import api
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import guess_roles
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.base import placed_blank
from freecad.menuiserie.features.joints.feasible import feasible_joint
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.gui.commands.base import TransactionCommand, report_refusal
from freecad.menuiserie.gui.task_panels.base import aborted_on_error
from freecad.menuiserie.gui.task_panels.joint import show_panel

Factory = Callable[..., DocumentObject]  # (hôte, invitée, *, check=…)

PAIR: Final = 2
# Noms des commandes, aussi noms de leurs icônes (``<nom>.svg``) et contextes de traduction.
MORTISE_TENON: Final = "Menuiserie_MortiseTenon"
TONGUE_GROOVE: Final = "Menuiserie_TongueGroove"
RABBET: Final = "Menuiserie_Rabbet"
DOWELS: Final = "Menuiserie_Dowels"
HALF_LAP: Final = "Menuiserie_HalfLap"
DOVETAIL: Final = "Menuiserie_Dovetail"
MITER: Final = "Menuiserie_Miter"


class JointCommand(TransactionCommand):
    """Base des commandes d'assemblage (Command) : chaque sous-classe fournit son nom, la
    fabrique de l'api, ses textes et le nom de sa transaction."""

    FACTORY: ClassVar[Factory]  # fabrique de freecad.menuiserie.api, lue sur la classe

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
        par la fabrique ou un assemblage impossible est expliqué sans rien créer ni ouvrir de
        panneau."""
        parts = selected_parts()
        if parts is None:
            return
        host, guest = ordered_roles(*parts)
        doc = App.ActiveDocument
        doc.openTransaction(translated(self.TRANSACTION))
        try:
            with aborted_on_error(App.getActiveTransaction()):
                joint = type(self).FACTORY(host, guest, check=feasible_joint)
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return
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


class HalfLapCommand(JointCommand):
    """Mi-bois : deux pièces qui se croisent, entaillées chacune sur une part de l'épaisseur."""

    NAME = HALF_LAP
    FACTORY = api.make_half_lap
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_HalfLap", "Mi-bois")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_HalfLap",
        "Relie à mi-bois les deux pièces sélectionnées, de même épaisseur et à fleur, qui se "
        "croisent : la première sélectionnée est entaillée par-dessus, l'autre par-dessous.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage à mi-bois")


class DovetailCommand(JointCommand):
    """Queue d'aronde traversante : queues au bout d'une pièce, logements dans l'autre."""

    NAME = DOVETAIL
    FACTORY = api.make_dovetail
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Dovetail", "Queue d'aronde")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Dovetail",
        "Relie à queues d'aronde traversantes les deux pièces sélectionnées : la pièce dont le "
        "bout touche l'autre porte les queues, l'autre (à fleur de sa face extérieure) les "
        "griffes.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage à queue d'aronde")


class MiterCommand(JointCommand):
    """Onglet : deux pièces d'angle coupées du coin extérieur au coin intérieur."""

    NAME = MITER
    FACTORY = api.make_miter
    MENU_TEXT = QT_TRANSLATE_NOOP("Menuiserie_Miter", "Onglet")
    TOOL_TIP = QT_TRANSLATE_NOOP(
        "Menuiserie_Miter",
        "Coupe d'onglet les deux pièces sélectionnées, dessinées à leur longueur hors tout et "
        "qui se chevauchent au coin : 45° pour deux largeurs égales.",
    )
    TRANSACTION = QT_TRANSLATE_NOOP("Menuiserie", "Créer un assemblage d'onglet")


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


def _is_part(obj: DocumentObject) -> bool:
    return is_timber(obj) or (is_machined_part(obj) and is_timber(obj.Base))


def register() -> None:
    """Enregistre les commandes d'assemblage auprès de FreeCAD."""
    Gui.addCommand(MORTISE_TENON, MortiseTenonCommand())
    Gui.addCommand(TONGUE_GROOVE, TongueGrooveCommand())
    Gui.addCommand(RABBET, RabbetCommand())
    Gui.addCommand(DOWELS, DowelsCommand())
    Gui.addCommand(HALF_LAP, HalfLapCommand())
    Gui.addCommand(DOVETAIL, DovetailCommand())
    Gui.addCommand(MITER, MiterCommand())
