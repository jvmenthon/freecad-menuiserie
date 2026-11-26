# SPDX-License-Identifier: LGPL-2.1-or-later
"""Page de repli des préférences : affichée si la vraie page ne peut pas être construite.

Module volontairement minimal (``PySide`` seul, aucun import de l'atelier) : il doit rester
importable quand le reste de l'atelier est en panne. La page n'enregistre rien.
"""

from __future__ import annotations

from PySide import QtGui

__all__ = ["FallbackPage"]


class FallbackPage:
    """Page qui affiche un libellé d'erreur ; ``loadSettings`` et ``saveSettings`` sont sans effet,
    comme l'attend FreeCAD d'une page de préférences."""

    def __init__(self, message: str) -> None:
        self.form = QtGui.QWidget()
        self.form.setObjectName("SettingsPageFallback")
        layout = QtGui.QVBoxLayout(self.form)
        label = QtGui.QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)

    def loadSettings(self) -> None:
        """Rien à afficher."""

    def saveSettings(self) -> None:
        """Rien à enregistrer : aucun réglage n'est écrit par la page de repli."""
