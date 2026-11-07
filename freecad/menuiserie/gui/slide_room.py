# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre « Jeu manquant » à la pose d'une coulisse de tiroir (ADR 0033).

Quand le côté du tiroir touche (ou chevauche) celui du caisson, la coulisse est posée mais il
manque du jeu pour la loger : :func:`choose` propose de réduire le tiroir (son côté s'éloigne),
d'élargir le meuble (le côté du caisson s'éloigne) ou de laisser tel quel.

La fenêtre est modale et ne peut pas être cliquée hors écran : ``chooser`` est un attribut de
module que les tests remplacent par une fonction ``manque (mm) -> "drawer" | "cabinet" | None``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.joints import mm_text
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.joints.slide_room import CABINET, DRAWER

__all__ = ["ask", "choose", "chooser", "message_for"]

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : jeu manquant pour la coulisse")
_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Les côtés du caisson et du tiroir se touchent : il manque {missing} mm de jeu pour loger la "
    "coulisse.\n\nRéduire le tiroir éloigne son côté de {missing} mm ; élargir le meuble éloigne "
    "le côté du caisson de {missing} mm.",
)
_DRAWER: Final = QT_TRANSLATE_NOOP("Menuiserie", "Réduire le tiroir")
_CABINET: Final = QT_TRANSLATE_NOOP("Menuiserie", "Élargir le meuble")
_KEEP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Laisser tel quel")


def message_for(missing: float) -> str:
    """Texte de la fenêtre pour ``missing`` mm de jeu manquant."""
    return translated(_TEXT, {"missing": mm_text(missing)})


def ask(missing: float) -> str | None:
    """Ouvre la fenêtre modale ; ``"drawer"``, ``"cabinet"``, ou ``None`` pour « Laisser tel
    quel », Échap ou la fermeture de la fenêtre."""
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Warning)
    box.setWindowTitle(translated(_TITLE))
    box.setText(message_for(missing))
    drawer = box.addButton(translated(_DRAWER), QtGui.QMessageBox.AcceptRole)
    cabinet = box.addButton(translated(_CABINET), QtGui.QMessageBox.AcceptRole)
    keep = box.addButton(translated(_KEEP), QtGui.QMessageBox.RejectRole)
    box.setDefaultButton(drawer)
    box.setEscapeButton(keep)
    box.exec()
    return {drawer: DRAWER, cabinet: CABINET}.get(box.clickedButton())


chooser: Callable[[float], str | None] = ask


def choose(missing: float) -> str | None:
    """Choix de l'utilisateur pour ``missing`` mm de jeu manquant, par ``chooser``."""
    return chooser(missing)
