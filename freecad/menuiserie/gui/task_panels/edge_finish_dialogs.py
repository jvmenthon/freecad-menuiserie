# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boîte de confirmation et textes d'arêtes du panneau « Finition des chants »."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.edge_frames import edge_index, edge_label
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.i18n import translated

__all__ = ["confirm_replacement", "piece_edges"]

_REPLACE_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Arêtes déjà profilées")
_REPLACE_TEXT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Ces arêtes ont déjà un profil : {edges}. Le nouveau profil le remplace. Continuer ?",
)
_PIECE_EDGES: Final = QT_TRANSLATE_NOOP("Menuiserie", "{piece} : {edges}")


def piece_edges(part: DocumentObject, codes: Sequence[str]) -> str:
    """« Pièce : arêtes » : libellé de ``part`` et arêtes ``codes`` nommées pour l'utilisateur."""
    shown = [edge_label(index) if (index := edge_index(c)) else c for c in codes]
    return translated(_PIECE_EDGES, {"piece": quoted_value(part.Label), "edges": ", ".join(shown)})


def confirm_replacement(parent: QtGui.QWidget, conflicts: str) -> bool:
    """Vrai si l'utilisateur accepte de remplacer le profil des arêtes ``conflicts``."""
    box = QtGui.QMessageBox(parent)
    box.setIcon(QtGui.QMessageBox.Icon.Question)
    box.setWindowTitle(translated(_REPLACE_TITLE))
    box.setTextFormat(QtCore.Qt.TextFormat.PlainText)  # libellés venus du document
    box.setText(translated(_REPLACE_TEXT, {"edges": conflicts}))
    box.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
    return bool(box.exec() == QtGui.QMessageBox.Yes)
