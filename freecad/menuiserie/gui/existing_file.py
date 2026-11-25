# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fichier d'export déjà présent (retour de jv du 25/11) : l'écraser, écrire « <nom> 2 » à côté,
ou annuler. La fenêtre est remplaçable (``chooser``) pour les vérifications sans interface."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import escaped_text
from freecad.menuiserie.features.cutlist_export import numbered_path
from freecad.menuiserie.features.i18n import translated

__all__ = ["NUMBERED", "OVERWRITE", "ask", "chooser", "free_target"]

OVERWRITE: Final = "overwrite"
NUMBERED: Final = "numbered"
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
    box = QtGui.QMessageBox(Gui.getMainWindow())
    box.setIcon(QtGui.QMessageBox.Question)
    box.setWindowTitle(translated(_TITLE))
    box.setText(translated(_TEXT, names))
    overwrite = box.addButton(translated(_OVERWRITE), QtGui.QMessageBox.DestructiveRole)
    numbered = box.addButton(translated(_NUMBERED, names), QtGui.QMessageBox.AcceptRole)
    cancel = box.addButton(translated(_CANCEL), QtGui.QMessageBox.RejectRole)
    box.setDefaultButton(numbered)
    box.setEscapeButton(cancel)
    box.exec()
    return {overwrite: OVERWRITE, numbered: NUMBERED}.get(box.clickedButton())


chooser: Callable[[Path, Path], str | None] = ask


def free_target(path: Path) -> Path | None:
    """``path`` s'il est libre ; sinon le choix de l'utilisateur : ``path`` à écraser, le
    premier « <nom> N » libre, ou ``None`` s'il annule. ``ValueError`` traduite sans nom
    libre."""
    if not path.exists():
        return path
    other = numbered_path(path)
    choice = chooser(path, other)
    if choice == OVERWRITE:
        return path
    return other if choice == NUMBERED else None
