# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boîte « Déverrouiller et appliquer » d'un glissement refusé par une rangée bloquée (ADR 0019).

Le refus, les cases des pièces verrouillées et le bouton sont ceux du composant partagé
(:class:`~freecad.menuiserie.gui.task_panels.unlock_widgets.UnlockBox`), dans une boîte modale :
hors panneau, il n'y a pas de panneau pour les porter.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import connect
from freecad.menuiserie.gui.task_panels.unlock_widgets import UnlockBox

__all__ = ["ask_unlock"]

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Déplacement refusé")


class _Choice:
    """Pièces choisies par « Déverrouiller et appliquer » (UnlockBox ne garde que des références
    faibles vers sa méthode : cet objet vit le temps de la boîte)."""

    def __init__(self, dialog: QtGui.QDialog) -> None:
        self.dialog = dialog
        self.pieces: list[DocumentObject] | None = None

    def apply(self, pieces: Sequence[DocumentObject]) -> None:
        self.pieces = list(pieces)
        self.dialog.accept()


def ask_unlock(error: ValueError) -> list[DocumentObject] | None:
    """Montre le refus ``error`` ; renvoie les pièces à déverrouiller si le menuisier choisit
    « Déverrouiller et appliquer », ``None`` s'il ferme la boîte (le déplacement est annulé)."""
    dialog = QtGui.QDialog(Gui.getMainWindow())
    dialog.setWindowTitle(translated(_TITLE))
    layout = QtGui.QVBoxLayout(dialog)
    choice = _Choice(dialog)
    unlock = UnlockBox(layout, choice.apply)
    unlock.refuse(error)
    buttons = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Cancel)
    connect(buttons, "rejected()", dialog.reject)
    layout.addWidget(buttons)
    dialog.exec_()
    return choice.pieces
