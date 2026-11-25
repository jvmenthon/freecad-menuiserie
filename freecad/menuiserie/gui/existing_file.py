# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre « Le fichier existe déjà » d'un export : l'écraser, écrire « <nom> 2 » à côté, ou
annuler (voir :func:`cutlist_export.free_target`)."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.cutlist_export import NUMBERED, OVERWRITE
from freecad.menuiserie.features.i18n import translated

__all__ = ["ask"]

_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Le fichier existe déjà")
_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {name} » existe déjà. L'écraser, ou écrire « {other} » à côté ?"
)
_OVERWRITE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Écraser")
_NUMBERED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Écrire « {other} »")
_CANCEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Annuler")


def ask(path: Path, other: Path) -> str | None:
    """Fenêtre modale : ``OVERWRITE``, ``NUMBERED`` (écrire ``other``), ou ``None`` pour
    « Annuler », Échap ou la fermeture."""
    names = {"name": escaped_text(path.name), "other": escaped_text(other.name)}
    button = {"other": other.name.replace("&", "&&")}  # texte brut : « & » marque un raccourci
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Question)
    box.setWindowTitle(translated(_TITLE))
    box.setText(translated(_TEXT, names))
    overwrite = box.addButton(translated(_OVERWRITE), QtGui.QMessageBox.DestructiveRole)
    numbered = box.addButton(translated(_NUMBERED, button), QtGui.QMessageBox.AcceptRole)
    cancel = box.addButton(translated(_CANCEL), QtGui.QMessageBox.RejectRole)
    box.setDefaultButton(numbered)
    box.setEscapeButton(cancel)
    box.exec()
    return {overwrite: OVERWRITE, numbered: NUMBERED}.get(box.clickedButton())
