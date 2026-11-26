# SPDX-License-Identifier: LGPL-2.1-or-later
"""Éditeurs et ligne d'un réglage de la page de préférences (ADR 0069).

Qt par la couche ``PySide`` de FreeCAD. Un éditeur (:class:`Editor`) lit, écrit et signale la
valeur de son widget ; une ligne (:class:`Row`) y ajoute le libellé, la valeur par défaut en gris,
la case « Dernier utilisé » et le bouton « Rétablir ».
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from PySide import QtCore, QtGui

from . import page_model as model
from .catalog import MAX_TEXT_LENGTH, Kind, Setting, Value

__all__ = ["Editor", "Row", "ignoring_arguments", "make_editor"]

_WIDE: Final = 1.0e9  # borne d'un nombre sans minimum ni maximum
_DECIMALS: Final = 2
_FIELD_WIDTH: Final = 220
_GREY: Final = "color: gray;"
_BOLD: Final = "font-weight: bold;"
Widget = Any


@dataclass(frozen=True)
class Editor:
    """Widget d'édition d'une valeur : lecture, écriture (sans signal) et abonnement."""

    widget: Widget
    get: Callable[[], Value]
    set: Callable[[Value], None]
    subscribe: Callable[[Callable[[], None]], None]


def ignoring_arguments(call: Callable[[], None]) -> Callable[..., None]:
    """Fonction à brancher sur un signal Qt : elle ignore les arguments du signal et appelle
    ``call`` sans argument."""

    def slot(*_arguments: object) -> None:
        call()

    return slot


def _subscriber(signal: Any) -> Callable[[Callable[[], None]], None]:
    """Abonnement d'un éditeur au signal de modification de son widget."""

    def subscribe(call: Callable[[], None]) -> None:
        signal.connect(ignoring_arguments(call))

    return subscribe


def _quiet(widget: Widget, write: Callable[[Value], None]) -> Callable[[Value], None]:
    """Écriture qui n'émet aucun signal de modification."""

    def write_quietly(value: Value) -> None:
        blocked = widget.blockSignals(True)
        try:
            write(value)
        finally:
            widget.blockSignals(blocked)

    return write_quietly


def _bool_editor(_setting: Setting, _choices: Sequence[tuple[Value, str]], _tr: Any) -> Editor:
    box = QtGui.QCheckBox()

    def write(value: Value) -> None:
        box.setChecked(bool(value))

    return Editor(box, box.isChecked, _quiet(box, write), _subscriber(box.toggled))


def _spin_range(setting: Setting) -> tuple[float, float]:
    low = -_WIDE if setting.minimum is None else setting.minimum
    high = _WIDE if setting.maximum is None else setting.maximum
    return low, high


def _suffix(setting: Setting, translate: model.Translate) -> str:
    return f" {translate(setting.unit)}" if setting.unit else ""


def _int_editor(setting: Setting, _choices: Sequence[tuple[Value, str]], tr: Any) -> Editor:
    box = QtGui.QSpinBox()
    low, high = _spin_range(setting)
    box.setRange(int(max(low, -(2**31))), int(min(high, 2**31 - 1)))
    box.setSuffix(_suffix(setting, tr))
    box.setKeyboardTracking(False)

    def write(value: Value) -> None:
        box.setValue(int(value))

    return Editor(box, box.value, _quiet(box, write), _subscriber(box.valueChanged))


def _float_editor(setting: Setting, _choices: Sequence[tuple[Value, str]], tr: Any) -> Editor:
    box = QtGui.QDoubleSpinBox()
    box.setRange(*_spin_range(setting))
    box.setDecimals(_DECIMALS)
    box.setSuffix(_suffix(setting, tr))
    box.setKeyboardTracking(False)  # la valeur est prise en fin de frappe (CONTRIBUTING)

    def write(value: Value) -> None:
        box.setValue(float(value))

    return Editor(box, box.value, _quiet(box, write), _subscriber(box.valueChanged))


def _combo_editor(setting: Setting, choices: Sequence[tuple[Value, str]], tr: Any) -> Editor:
    combo = QtGui.QComboBox()
    for stored, label in choices or [(value, value) for value in setting.choices]:
        combo.addItem(label, stored)
    absent: list[Value] = []  # valeur enregistrée hors de la liste, ajoutée comme élément

    def write(value: Value) -> None:
        while absent:  # l'élément « absent » précédent n'a plus lieu d'être
            combo.removeItem(combo.findData(absent.pop()))
        index = combo.findData(value)
        if index < 0:
            label = tr(model.ABSENT_VALUE).replace("{value}", str(value))
            combo.addItem(label, value)
            absent.append(value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)

    def read() -> Value:
        data = combo.currentData()
        return data if data is not None else setting.default

    return Editor(combo, read, _quiet(combo, write), _subscriber(combo.currentIndexChanged))


def _text_editor(_setting: Setting, _choices: Sequence[tuple[Value, str]], _tr: Any) -> Editor:
    field = QtGui.QLineEdit()
    field.setMaxLength(MAX_TEXT_LENGTH)

    def write(value: Value) -> None:
        field.setText(str(value))

    return Editor(field, field.text, _quiet(field, write), _subscriber(field.textChanged))


def _path_editor(setting: Setting, choices: Sequence[tuple[Value, str]], tr: Any) -> Editor:
    """Champ de texte et bouton « … » qui ouvre le choix d'un dossier."""
    inner = _text_editor(setting, choices, tr)
    holder = QtGui.QWidget()
    layout = QtGui.QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    button = QtGui.QPushButton(model.BROWSE)
    button.setToolTip(tr(model.BROWSE_TIP))
    button.setFixedWidth(32)
    layout.addWidget(inner.widget)
    layout.addWidget(button)

    def browse() -> None:
        start = str(inner.get())
        folder = QtGui.QFileDialog.getExistingDirectory(holder, tr(model.BROWSE_TIP), start)
        if folder:
            inner.widget.setText(folder)

    button.clicked.connect(ignoring_arguments(browse))
    return Editor(holder, inner.get, inner.set, inner.subscribe)


def _choice_or_text(setting: Setting, choices: Sequence[tuple[Value, str]], tr: Any) -> Editor:
    """Texte libre, sauf si l'atelier fournit des choix (liste déroulante)."""
    return _combo_editor(setting, choices, tr) if choices else _text_editor(setting, choices, tr)


def make_editor(
    setting: Setting, translate: model.Translate, choices: Sequence[tuple[Value, str]] = ()
) -> Editor:
    """Éditeur du réglage selon sa nature ; ``choices`` (valeur, libellé traduit) remplace les
    valeurs d'un choix, ou donne une liste à un texte."""
    builders = {
        Kind.BOOL: _bool_editor,
        Kind.INT: _int_editor,
        Kind.FLOAT: _float_editor,
        Kind.CHOICE: _combo_editor,
        Kind.TEXT: _choice_or_text,
        Kind.PATH: _path_editor,
    }
    editor = builders[setting.kind](setting, choices, translate)
    if setting.kind is not Kind.BOOL:
        editor.widget.setMinimumWidth(_FIELD_WIDTH)
    return editor


class Row:
    """Ligne d'un réglage : libellé, éditeur, défaut en gris, « Dernier utilisé », « Rétablir »."""

    def __init__(
        self,
        setting: Setting,
        translate: model.Translate,
        choices: Sequence[tuple[Value, str]],
        changed: Callable[[], None],
    ) -> None:
        self.setting = setting
        self.editor = make_editor(setting, translate, choices)
        self.label = QtGui.QLabel(translate(setting.label))
        tip = translate(setting.tooltip)
        for widget in (self.label, self.editor.widget):
            widget.setToolTip(tip)
        shown = model.format_value(setting, setting.default, translate, choices)
        self.default_label = QtGui.QLabel(translate(model.DEFAULT_VALUE).replace("{value}", shown))
        self.default_label.setStyleSheet(_GREY)
        self.remember = (
            QtGui.QCheckBox(translate(model.LAST_USED)) if setting.remember_last else None
        )
        if self.remember is not None:
            self.remember.setToolTip(translate(model.LAST_USED_TIP))
            self.remember.toggled.connect(self._remember_toggled)
        self.reset_button = _reset_button(translate)
        self.reset_button.clicked.connect(self._reset_clicked)
        self._changed = changed
        self.dirty = False  # vrai si l'utilisateur a touché à la ligne depuis le dernier chargement
        self.editor.subscribe(self._edited)
        self.modified_shown = False  # libellé en gras : ligne modifiée
        self._bold(False)

    def widgets(self) -> list[Widget | None]:
        """Widgets des colonnes de la grille : libellé, éditeur, défaut, case, bouton."""
        return [
            self.label,
            self.editor.widget,
            self.default_label,
            self.remember,
            self.reset_button,
        ]

    def all_widgets(self) -> list[Widget]:
        """Widgets présents, à montrer ou masquer ensemble."""
        return [widget for widget in self.widgets() if widget is not None]

    def value(self) -> Value:
        """Valeur affichée dans l'éditeur."""
        return self.editor.get()

    def remembers(self) -> bool:
        """Vrai si la case « Dernier utilisé » est cochée."""
        return self.remember is not None and bool(self.remember.isChecked())

    def load(self, value: Value, remembers: bool, *, dirty: bool = False) -> None:
        """Affiche ``value`` et l'état de la case, sans signal ; la ligne n'est « modifiée »
        (à écrire) que si ``dirty``."""
        self.dirty = dirty
        self.editor.set(value)
        if self.remember is not None:
            blocked = self.remember.blockSignals(True)
            self.remember.setChecked(remembers)
            self.remember.blockSignals(blocked)
        self._refresh()

    def reset(self) -> None:
        """Valeur par défaut, case décochée (écrit à l'enregistrement de la page)."""
        self.load(self.setting.default, False, dirty=True)
        self._changed()

    def _reset_clicked(self, *_arguments: object) -> None:
        self.reset()

    def _remember_toggled(self, *_arguments: object) -> None:
        self.dirty = True
        self._changed()

    def is_modified(self) -> bool:
        """Vrai si la valeur affichée diffère du défaut."""
        return self.value() != self.setting.default

    def _edited(self) -> None:
        self.dirty = True
        self._refresh()
        self._changed()

    def _refresh(self) -> None:
        self._bold(self.is_modified())

    def _bold(self, bold: bool) -> None:
        """Libellé en gras si la ligne est modifiée. La feuille de style s'impose à celle de
        FreeCAD, qui ignore ``setFont`` ; ``modified_shown`` donne l'état affiché."""
        self.modified_shown = bold
        self.label.setStyleSheet(_BOLD if bold else "")


def _reset_button(translate: model.Translate) -> Widget:
    button = QtGui.QToolButton()
    style = button.style()
    icon = style.standardIcon(QtGui.QStyle.StandardPixmap.SP_BrowserReload)
    if icon.isNull():
        button.setText("↺")
    else:
        button.setIcon(icon)
    button.setToolTip(translate(model.RESET_TIP))
    button.setAccessibleName(translate(model.RESET))
    button.setAutoRaise(True)
    button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
    return button
