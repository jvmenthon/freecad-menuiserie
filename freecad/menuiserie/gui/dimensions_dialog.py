# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fenêtre d'édition des épaisseurs et formats personnels (``dimensions.json``) (ADR 0028, 0069).

Deux listes : les épaisseurs (mm) et les formats de panneaux L x l (mm). Les valeurs de l'atelier
sont en gris et ne se suppriment pas ; les valeurs personnelles s'ajoutent (saisie bornée selon
``core/user_dimensions.py``) et se suppriment. La fenêtre travaille sur une copie : rien n'est
écrit, l'appelant reçoit le résultat à « OK » (écriture à OK ou Appliquer de la page).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.materials import MAX_THICKNESS_MM
from freecad.menuiserie.core.part_model import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.user_dimensions import (
    UserDimensions,
    with_sheet,
    with_thickness,
    without_sheet,
    without_thickness,
)
from freecad.menuiserie.features import dimensions_edit as edit
from freecad.menuiserie.features.i18n import translate_text, translated_errors
from freecad.menuiserie.kit.config.page_rows import ignoring_arguments

__all__ = ["TEXTS", "DimensionsDialog", "edit_dimensions"]

_THICKNESSES: Final = QT_TRANSLATE_NOOP("Menuiserie", "Épaisseurs (mm)")
_SHEETS: Final = QT_TRANSLATE_NOOP("Menuiserie", "Formats de panneaux L x l (mm)")
_ADD: Final = QT_TRANSLATE_NOOP("Menuiserie", "Ajouter la valeur saisie")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Supprimer la valeur sélectionnée")
_NOTE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les valeurs de l'atelier, en gris, ne se suppriment pas."
)
_REFUSED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Valeur refusée")
TEXTS: Final = (_THICKNESSES, _SHEETS, _ADD, _REMOVE, _NOTE, _REFUSED)

_GREY: Final = "gray"
_INDEX_ROLE: Final = QtCore.Qt.ItemDataRole.UserRole
_DEFAULT_THICKNESS: Final = 19.0
_DEFAULT_SHEET: Final = (2500.0, 1250.0)


def _spin(maximum: float, value: float) -> QtGui.QDoubleSpinBox:
    """Saisie en mm bornée comme le modèle ; valeur prise en fin de frappe (Entrée, Tab)."""
    box = QtGui.QDoubleSpinBox()
    box.setRange(MIN_DIMENSION_MM, maximum)
    box.setDecimals(2)
    box.setSuffix(" mm")
    box.setKeyboardTracking(False)
    box.setValue(value)
    return box


def _mini_button(text: str, name: str, tip: str) -> QtGui.QPushButton:
    button = QtGui.QPushButton(text)
    button.setObjectName(name)
    button.setToolTip(tip)
    button.setAccessibleName(tip)
    button.setFixedWidth(30)
    button.setAutoDefault(False)
    return button


class _Section:
    """Une liste (épaisseurs ou formats), ses champs de saisie et ses boutons + et -."""

    def __init__(self, name: str, title: str, spins: list[QtGui.QDoubleSpinBox]) -> None:
        self.entries: list[edit.Entry] = []
        self.spins = spins
        self.frame = QtGui.QVBoxLayout()
        self.frame.addWidget(QtGui.QLabel(title))
        self.list = QtGui.QListWidget()
        self.list.setObjectName(name + "List")
        self.frame.addWidget(self.list)
        bar = QtGui.QHBoxLayout()
        for spin in spins:
            bar.addWidget(spin)
        tip_add, tip_remove = translate_text(_ADD), translate_text(_REMOVE)
        self.add = _mini_button("+", name + "Add", tip_add)
        self.remove = _mini_button("-", name + "Remove", tip_remove)
        self.remove.setEnabled(False)
        bar.addWidget(self.add)
        bar.addWidget(self.remove)
        self.frame.addLayout(bar)
        self.list.itemSelectionChanged.connect(ignoring_arguments(self._selection_changed))

    def fill(self, entries: list[edit.Entry]) -> None:
        """Affiche ``entries`` : les valeurs de l'atelier en gris, non sélectionnables."""
        self.entries = entries
        blocked = self.list.blockSignals(True)  # la sélection d'avant ne vise plus rien
        try:
            self.list.clear()
            for index, entry in enumerate(entries):
                self.list.addItem(self._item(index, entry))
        finally:
            self.list.blockSignals(blocked)
        self._selection_changed()

    @staticmethod
    def _item(index: int, entry: edit.Entry) -> QtGui.QListWidgetItem:
        item = QtGui.QListWidgetItem(entry.text)
        item.setData(_INDEX_ROLE, index)
        if not entry.personal:
            item.setForeground(QtGui.QBrush(QtGui.QColor(_GREY)))
            item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
        return item

    def selected(self) -> edit.Entry | None:
        """Valeur personnelle sélectionnée, ``None`` s'il n'y en a pas."""
        items = self.list.selectedItems()
        entry = self.entries[items[0].data(_INDEX_ROLE)] if items else None
        return entry if entry is not None and entry.personal else None

    def _selection_changed(self) -> None:
        self.remove.setEnabled(self.selected() is not None)


class DimensionsDialog(QtGui.QDialog):  # type: ignore[misc]  # PySide sans annotations
    """Édition des dimensions personnelles ; :meth:`result` donne la copie modifiée."""

    def __init__(
        self,
        dimensions: UserDimensions,
        builtin_thicknesses: tuple[float, ...] = (),
        parent: QtGui.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dimensions = dimensions
        self._builtin = builtin_thicknesses
        self.setWindowTitle(translate_text(edit.ROW_LABEL))
        self.thickness_spin = _spin(MAX_THICKNESS_MM, _DEFAULT_THICKNESS)
        self.sheet_spins = [_spin(MAX_DIMENSION_MM, value) for value in _DEFAULT_SHEET]
        self.thicknesses = _Section(
            "thickness", translate_text(_THICKNESSES), [self.thickness_spin]
        )
        self.sheets = _Section("sheet", translate_text(_SHEETS), self.sheet_spins)
        self._connect(self.thicknesses, self._add_thickness, self._remove_thickness)
        self._connect(self.sheets, self._add_sheet, self._remove_sheet)
        layout = QtGui.QVBoxLayout(self)
        columns = QtGui.QHBoxLayout()
        columns.addLayout(self.thicknesses.frame)
        columns.addLayout(self.sheets.frame)
        layout.addLayout(columns)
        note = QtGui.QLabel(translate_text(_NOTE))
        note.setStyleSheet("color: gray;")
        layout.addWidget(note)
        layout.addWidget(self._buttons())
        self._show()

    @staticmethod
    def _connect(section: _Section, add: Callable[[], None], remove: Callable[[], None]) -> None:
        section.add.clicked.connect(ignoring_arguments(add))
        section.remove.clicked.connect(ignoring_arguments(remove))

    def _buttons(self) -> QtGui.QDialogButtonBox:
        box = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.StandardButton.Ok | QtGui.QDialogButtonBox.StandardButton.Cancel
        )
        box.setObjectName("dimensionsButtons")
        for kind in (
            QtGui.QDialogButtonBox.StandardButton.Ok,
            QtGui.QDialogButtonBox.StandardButton.Cancel,
        ):
            box.button(kind).setAutoDefault(False)  # Entrée valide un champ, pas la fenêtre
        box.accepted.connect(ignoring_arguments(self.accept))
        box.rejected.connect(ignoring_arguments(self.reject))
        self.buttons = box
        return box

    def result_dimensions(self) -> UserDimensions:
        """Dimensions personnelles telles qu'éditées."""
        return self._dimensions

    def _show(self) -> None:
        self.thicknesses.fill(edit.thickness_entries(self._builtin, self._dimensions))
        self.sheets.fill(edit.sheet_entries(self._dimensions))

    def _change(self, action: Callable[[], UserDimensions]) -> None:
        """Applique ``action`` à la copie ; un refus du modèle s'affiche et ne change rien."""
        try:
            with translated_errors():
                self._dimensions = action()
        except ValueError as error:
            QtGui.QMessageBox.warning(self, translate_text(_REFUSED), str(error))
            return
        self._show()

    def _add_thickness(self) -> None:
        self._change(partial(with_thickness, self._dimensions, self.thickness_spin.value()))

    def _add_sheet(self) -> None:
        length, width = (spin.value() for spin in self.sheet_spins)
        self._change(partial(with_sheet, self._dimensions, length, width))

    def _remove_thickness(self) -> None:
        entry = self.thicknesses.selected()
        if entry is not None and isinstance(entry.value, float):
            self._change(partial(without_thickness, self._dimensions, entry.value))

    def _remove_sheet(self) -> None:
        entry = self.sheets.selected()
        if entry is not None and isinstance(entry.value, tuple):
            self._change(partial(without_sheet, self._dimensions, *entry.value))


def edit_dimensions(
    parent: QtGui.QWidget, dimensions: UserDimensions, builtin_thicknesses: tuple[float, ...]
) -> UserDimensions | None:
    """Ouvre la fenêtre ; les dimensions éditées à « OK », ``None`` à « Annuler »."""
    dialog = DimensionsDialog(dimensions, builtin_thicknesses, parent)
    return dialog.result_dimensions() if dialog.exec() else None
