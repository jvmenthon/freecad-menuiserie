# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle commun des commandes de l'atelier : :class:`TransactionCommand` (ressources d'une
commande qui porte une entrée d'annulation) et affichage d'un refus (:func:`report_refusal`).

Une commande qui attend une sélection reste active dès qu'un document est ouvert et qu'aucun
panneau de tâche ne l'est : lancée sans la bonne sélection, elle dit quoi sélectionner
(:func:`explain_selection`, issue #221) au lieu de rester grisée sans explication.

Un refus de l'api est expliqué dans une boîte d'avertissement non modale, la barre d'état et la
vue rapport, sans rien créer (demande de jv) ; les commandes d'assemblage, d'ensemble et de
liste de débit le signalent toutes de la même façon.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, ClassVar, Final

import FreeCAD as App
import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import Document
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.gui.task_panels.base import close_transaction

REFUSAL_DISPLAY_MS: Final = 15_000  # durée d'affichage d'un refus dans la barre d'état
REFUSAL_BOX_NAME: Final = "MenuiserieRefusal"
REFUSAL_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : action refusée")
SELECTION_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : sélection attendue")
_REFUSAL_BOX: dict[str, Any] = {}  # boîte réutilisée, gardée en vie entre deux refus
_COMMANDS: dict[str, Any] = {}  # commandes à sélection enregistrées par add_command


def command_ready() -> bool:
    """Vrai s'il y a un document et aucun panneau de tâche ouvert : la commande est active."""
    return App.ActiveDocument is not None and not Gui.Control.activeDialog()


def add_command(name: str, command: Any) -> None:
    """Enregistre ``command`` auprès de FreeCAD et la retient pour :func:`would_run`."""
    Gui.addCommand(name, command)
    _COMMANDS[name] = command


def would_run(name: str) -> bool:
    """Vrai si la commande ``name`` agirait sur la sélection actuelle (active et sélection
    acceptée) ; faux si elle se contenterait de dire quoi sélectionner."""
    return command_ready() and bool(_COMMANDS[name].selection_ok())


class TransactionCommand:
    """Base des commandes de l'atelier qui portent une entrée d'annulation (assemblages,
    ensembles, liste de débit) : nom (aussi celui de l'icône), textes et nom de la
    transaction."""

    NAME: ClassVar[str]
    MENU_TEXT: ClassVar[str]
    TOOL_TIP: ClassVar[str]
    TRANSACTION: ClassVar[str]
    SELECTION_HINT: ClassVar[str] = ""  # ce qu'il faut sélectionner avant de lancer la commande

    def IsActive(self) -> bool:
        """Active s'il y a un document et aucun panneau ouvert, quelle que soit la sélection :
        une sélection qui ne convient pas est expliquée au clic (issue #221)."""
        return command_ready()

    def selection_ok(self) -> bool:
        """Vrai si la sélection actuelle convient à la commande (lecture seule)."""
        return True

    def explain_selection(self) -> None:
        """Dit quoi sélectionner, sans rien créer ni modifier."""
        explain_selection(self.NAME, self.MENU_TEXT, self.SELECTION_HINT)

    def GetResources(self) -> dict[str, str]:
        """Icône, libellé et infobulle (traduits par FreeCAD, contexte = nom de la commande)."""
        return {
            "Pixmap": icon_path(f"{self.NAME}.svg"),
            "MenuText": self.MENU_TEXT,
            "ToolTip": self.TOOL_TIP,
        }


@contextmanager
def refusable_transaction(doc: Document, title: str) -> Iterator[None]:
    """Bloc exécuté dans une transaction de ``doc`` (``title``, gabarit traduisible) : validée
    (une entrée d'annulation) à la sortie normale ; sur un refus de l'api (``TypeError`` ou
    ``ValueError``), abandonnée et signalée par :func:`report_refusal`, le bloc étant alors
    interrompu sans exception ; toute autre exception l'abandonne et se propage."""
    doc.openTransaction(translated(title))
    transaction = App.getActiveTransaction()
    try:
        yield
    except (TypeError, ValueError) as error:
        close_transaction(transaction, abort=True)
        report_refusal(str(error))
        return
    except BaseException:
        close_transaction(transaction, abort=True)
        raise
    close_transaction(transaction, abort=False)


def report_refusal(message: str) -> None:
    """Refus de la fabrique : boîte d'avertissement (non modale, au premier plan), barre d'état
    de la fenêtre principale et vue rapport."""
    report_warning(message)
    window = Gui.getMainWindow()
    if window is not None:
        window.statusBar().showMessage(message, REFUSAL_DISPLAY_MS)
        show_refusal_box(window, message)


def explain_selection(name: str, menu_text: str, hint: str) -> None:
    """Commande ``name`` lancée sans la sélection attendue : « libellé : quoi sélectionner » dans
    la barre d'état et dans la boîte de l'atelier (information, non modale). Ce n'est pas une
    erreur : rien dans la vue rapport."""
    message = f"{App.Qt.translate(name, menu_text)} : {translated(hint)}"
    window = Gui.getMainWindow()
    if window is not None:
        window.statusBar().showMessage(message, REFUSAL_DISPLAY_MS)
        show_refusal_box(window, message, title=SELECTION_TITLE, warning=False)


def show_refusal_box(
    window: Any, message: str, *, title: str = REFUSAL_TITLE, warning: bool = True
) -> Any:
    """Affiche ``message`` dans la boîte de l'atelier (une seule à la fois, remplacée au message
    suivant) ; non modale, elle ne bloque ni FreeCAD ni les scripts. ``title`` (gabarit
    traduisible) et ``warning`` (avertissement, sinon information) distinguent un refus d'une
    sélection attendue."""
    from PySide import QtCore, QtGui

    box = _REFUSAL_BOX.get("box")
    if box is None:
        box = QtGui.QMessageBox(window)
        box.setObjectName(REFUSAL_BOX_NAME)
        box.setModal(False)
        _REFUSAL_BOX["box"] = box
    box.setIcon(QtGui.QMessageBox.Warning if warning else QtGui.QMessageBox.Information)
    box.setWindowTitle(translated(title))
    box.setTextFormat(QtCore.Qt.PlainText)
    box.setText(message)
    box.show()
    box.raise_()
    return box
