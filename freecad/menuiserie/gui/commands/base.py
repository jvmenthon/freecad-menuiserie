# SPDX-License-Identifier: LGPL-2.1-or-later
"""Socle commun des commandes de l'atelier : :class:`TransactionCommand` (ressources d'une
commande qui porte une entrée d'annulation) et affichage d'un refus (:func:`report_refusal`).

Un refus de l'api est expliqué dans une boîte d'avertissement non modale, la barre d'état et la
vue rapport, sans rien créer (demande de jv) ; les commandes d'assemblage, d'ensemble et de
liste de débit le signalent toutes de la même façon.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final

import FreeCADGui as Gui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import report_warning, translated

REFUSAL_DISPLAY_MS: Final = 15_000  # durée d'affichage d'un refus dans la barre d'état
REFUSAL_BOX_NAME: Final = "MenuiserieRefusal"
REFUSAL_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Menuiserie : action refusée")
_REFUSAL_BOX: dict[str, Any] = {}  # boîte réutilisée, gardée en vie entre deux refus


class TransactionCommand:
    """Base des commandes de l'atelier qui portent une entrée d'annulation (assemblages,
    ensembles, liste de débit) : nom (aussi celui de l'icône), textes et nom de la
    transaction."""

    NAME: ClassVar[str]
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


def report_refusal(message: str) -> None:
    """Refus de la fabrique : boîte d'avertissement (non modale, au premier plan), barre d'état
    de la fenêtre principale et vue rapport."""
    report_warning(message)
    window = Gui.getMainWindow()
    if window is not None:
        window.statusBar().showMessage(message, REFUSAL_DISPLAY_MS)
        show_refusal_box(window, message)


def show_refusal_box(window: Any, message: str) -> Any:
    """Affiche ``message`` dans la boîte d'avertissement de l'atelier (une seule à la fois,
    remplacée au refus suivant) ; non modale, elle ne bloque ni FreeCAD ni les scripts."""
    from PySide import QtGui

    box = _REFUSAL_BOX.get("box")
    if box is None:
        box = QtGui.QMessageBox(window)
        box.setObjectName(REFUSAL_BOX_NAME)
        box.setIcon(QtGui.QMessageBox.Warning)
        box.setWindowTitle(translated(REFUSAL_TITLE))
        box.setModal(False)
        _REFUSAL_BOX["box"] = box
    box.setText(message)
    box.show()
    box.raise_()
    return box
