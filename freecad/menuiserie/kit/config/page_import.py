# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre d'aperçu d'un import de réglages : tableau à cocher, avertissement, note (ADR 0069).

Qt par la couche ``PySide`` de FreeCAD, sans texte propre à un atelier : les lignes viennent de
:mod:`.import_model`, les textes de la fenêtre sont traduits par la fonction injectée. La fenêtre
ne modifie rien : elle rend les clés des lignes cochées (:meth:`ImportPreview.checked_keys`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from PySide import QtCore, QtGui

from . import import_model as model
from .import_model import ImportRow
from .page_model import Translate, identity
from .page_rows import ignoring_arguments

__all__ = ["ImportPreview"]

_COLUMNS: Final = (model.COLUMN_GROUP, model.COLUMN_SETTING, model.COLUMN_CURRENT)
_IMPORTED_COLOR: Final = "#0b5cad"  # valeur importée en bleu, comme la maquette
_WARNING_STYLE: Final = (
    "background: #fff4ce; border: 1px solid #e0c060; border-radius: 3px; "
    "padding: 6px 10px; color: #5a4a00;"
)
_NOTE_STYLE: Final = "color: gray;"
_KEY_ROLE: Final = QtCore.Qt.ItemDataRole.UserRole


class ImportPreview(QtGui.QDialog):  # type: ignore[misc]  # PySide sans annotations
    """Aperçu : « Fichier : … », tableau (case, Groupe, Réglage, Actuel, Importé), bandeau
    d'avertissement s'il y a des éléments ignorés, note, « Reprendre la sélection » (par défaut)
    et « Annuler »."""

    def __init__(
        self,
        rows: Sequence[ImportRow],
        header: str,
        warning: str = "",
        translate: Translate = identity,
        parent: QtGui.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._rows = list(rows)
        self.setWindowTitle(translate(model.TITLE))
        self.setMinimumWidth(640)
        layout = QtGui.QVBoxLayout(self)
        self.header = QtGui.QLabel(header)
        self.header.setObjectName("importHeader")
        layout.addWidget(self.header)
        self.table = self._build_table(translate)
        layout.addWidget(self.table)
        self.warning = QtGui.QLabel(warning)
        self.warning.setObjectName("importWarning")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet(_WARNING_STYLE)
        self.warning.setVisible(bool(warning))
        layout.addWidget(self.warning)
        note = QtGui.QLabel(translate(model.NOTE))
        note.setWordWrap(True)
        note.setStyleSheet(_NOTE_STYLE)
        layout.addWidget(note)
        layout.addLayout(self._buttons(translate))

    def _build_table(self, translate: Translate) -> QtGui.QTableWidget:
        table = QtGui.QTableWidget(len(self._rows), len(_COLUMNS) + 2)
        table.setObjectName("importTable")
        titles = ["", *(translate(text) for text in _COLUMNS), translate(model.COLUMN_IMPORTED)]
        table.setHorizontalHeaderLabels(titles)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QtGui.QAbstractItemView.SelectionMode.NoSelection)
        table.setEditTriggers(QtGui.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        for index, row in enumerate(self._rows):
            table.setItem(index, 0, self._check_item(row, translate))
            for column, text in enumerate((row.group, row.label, row.current), start=1):
                table.setItem(index, column, self._text_item(text))
            imported = self._text_item(row.imported)
            imported.setForeground(QtGui.QBrush(QtGui.QColor(_IMPORTED_COLOR)))
            table.setItem(index, len(_COLUMNS) + 1, imported)
        table.resizeColumnsToContents()
        return table

    @staticmethod
    def _text_item(text: str) -> QtGui.QTableWidgetItem:
        item = QtGui.QTableWidgetItem(text)
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
        return item

    @staticmethod
    def _check_item(row: ImportRow, translate: Translate) -> QtGui.QTableWidgetItem:
        item = QtGui.QTableWidgetItem()
        item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.CheckState.Checked)
        item.setData(_KEY_ROLE, row.key)
        item.setToolTip(translate(model.SELECT_TIP))
        return item

    def _buttons(self, translate: Translate) -> QtGui.QHBoxLayout:
        bar = QtGui.QHBoxLayout()
        bar.addStretch(1)
        self.take_button = QtGui.QPushButton(translate(model.TAKE))
        self.take_button.setObjectName("importTake")
        self.take_button.setDefault(True)
        self.cancel_button = QtGui.QPushButton(translate(model.CANCEL))
        self.cancel_button.setObjectName("importCancel")
        self.take_button.clicked.connect(ignoring_arguments(self.accept))
        self.cancel_button.clicked.connect(ignoring_arguments(self.reject))
        bar.addWidget(self.take_button)
        bar.addWidget(self.cancel_button)
        return bar

    def checked_keys(self) -> list[str]:
        """Clés des lignes cochées, dans l'ordre du tableau."""
        keys: list[str] = []
        for index in range(self.table.rowCount()):
            item = self.table.item(index, 0)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                keys.append(str(item.data(_KEY_ROLE)))
        return keys
