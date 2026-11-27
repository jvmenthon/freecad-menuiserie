# SPDX-License-Identifier: LGPL-2.1-or-later
"""Doublures des dialogues de l'échange de réglages, pour les scénarios QTest (ADR 0069).

Aucune fenêtre modale : les fichiers sont choisis d'avance, l'aperçu est joué par la vraie
fenêtre (:class:`ImportPreview`) sans ``exec``, les messages sont notés.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide import QtCore, QtGui

from freecad.menuiserie.kit.config.import_model import ImportRow
from freecad.menuiserie.kit.config.page_dialogs import Dialogs
from freecad.menuiserie.kit.config.page_import import ImportPreview
from tests.qtest.qttest import QTest

__all__ = ["Doublures", "cliquer"]


def cliquer(widget: Any) -> None:
    """Clic gauche sur ``widget``, événements traités."""
    QTest.mouseClick(widget, QtCore.Qt.MouseButton.LeftButton)
    QtGui.QApplication.processEvents()


class Doublures:
    """Dialogues remplacés : fichiers choisis d'avance, aperçu joué par la vraie fenêtre (cases
    décochées avant « Reprendre »), messages notés."""

    def __init__(self) -> None:
        self.fichier: Path | None = None
        self.decocher: set[str] = set()
        self.annuler_apercu = False
        self.messages: list[tuple[str, bool]] = []
        self.apercus: list[tuple[list[ImportRow], str, str]] = []

    def enregistrer(self, _parent: Any, _titre: str, _depart: Path) -> Path | None:
        return self.fichier

    def ouvrir(self, _parent: Any, _titre: str, _depart: Path) -> Path | None:
        return self.fichier

    def apercu(
        self, parent: Any, rows: list[ImportRow], header: str, warning: str
    ) -> list[str] | None:
        self.apercus.append((rows, header, warning))
        fenetre = ImportPreview(rows, header, warning, parent=parent)
        for index, row in enumerate(rows):
            if row.key in self.decocher:
                fenetre.table.item(index, 0).setCheckState(QtCore.Qt.CheckState.Unchecked)
        if self.annuler_apercu:
            cliquer(fenetre.cancel_button)
            return None
        cliquer(fenetre.take_button)
        return fenetre.checked_keys() if fenetre.result() else None

    def message(self, _parent: Any, texte: str, erreur: bool) -> None:
        self.messages.append((texte, erreur))

    def dialogues(self) -> Dialogs:
        return Dialogs(self.enregistrer, self.ouvrir, self.apercu, self.message)
