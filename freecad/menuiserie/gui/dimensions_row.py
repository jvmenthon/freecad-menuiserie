# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ligne « Épaisseurs et formats personnels » de la page de préférences (ADR 0028, 0069).

Un résumé (« 3 épaisseurs, 1 format ») et le bouton « Modifier… » qui ouvre l'éditeur. Les
modifications restent en attente dans la ligne : elles sont écrites dans ``dimensions.json`` à
``saveSettings`` (OK ou Appliquer de la page), jamais avant ; « Annuler » ou ``loadSettings`` les
abandonne. « Rétablir tout » de la page ne touche pas à ce fichier.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.user_dimensions import UserDimensions
from freecad.menuiserie.features import dimensions_edit as edit
from freecad.menuiserie.features.i18n import translate_text
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.user_dimensions import read_dimensions, write_dimensions
from freecad.menuiserie.gui.dimensions_dialog import edit_dimensions
from freecad.menuiserie.kit.config.page_dialogs import plain_message
from freecad.menuiserie.kit.config.page_model import ExtraRow, Widget
from freecad.menuiserie.kit.config.page_rows import ignoring_arguments

__all__ = ["TEXTS", "DimensionsRow"]

_MODIFY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier…")
_NOT_SAVED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Dimensions personnelles non enregistrées")
TEXTS: Final = (_MODIFY, _NOT_SAVED)

Editor = Callable[[Widget, UserDimensions, tuple[float, ...]], UserDimensions | None]


def library_thicknesses() -> tuple[float, ...]:
    """Épaisseurs intégrées : celles des matériaux de la bibliothèque (vides si elle est
    illisible : la fenêtre s'ouvre quand même)."""
    try:
        return edit.builtin_thicknesses([material.thicknesses for material in get_library()])
    except (OSError, ValueError):
        return ()


class DimensionsRow:
    """Résumé et bouton de la ligne, avec l'état en attente. ``editor`` ouvre la fenêtre
    d'édition (remplaçable en test)."""

    def __init__(self, group: str, before_group: str, editor: Editor = edit_dimensions) -> None:
        self._group = group
        self._before = before_group
        self._editor = editor
        self._saved = read_dimensions()
        self._pending: UserDimensions | None = None
        self.widget = QtGui.QWidget()
        layout = QtGui.QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QtGui.QLabel()
        self.summary.setObjectName("dimensionsSummary")
        self.button = QtGui.QPushButton(translate_text(_MODIFY))
        self.button.setObjectName("dimensionsEdit")
        self.button.clicked.connect(ignoring_arguments(self.edit))
        layout.addWidget(self.summary)
        layout.addWidget(self.button)
        layout.addStretch(1)
        self._show()

    def extra_row(self) -> ExtraRow:
        """Ligne à donner à la page de préférences."""
        return ExtraRow(
            self._group,
            edit.ROW_LABEL,
            self.widget,
            edit.ROW_TIP,
            self._before,
            self.load,
            self.save,
            self.has_pending,
        )

    def shown(self) -> UserDimensions:
        """Dimensions affichées : celles en attente, sinon celles du fichier."""
        return self._pending if self._pending is not None else self._saved

    def has_pending(self) -> bool:
        """Vrai si des modifications attendent OK ou Appliquer."""
        return self._pending is not None

    def set_pending(self, dimensions: UserDimensions) -> None:
        """Met ``dimensions`` en attente (reprise d'un import) ; sans effet si elles sont déjà
        celles du fichier."""
        self._pending = None if dimensions == self._saved else dimensions
        self._show()

    def edit(self) -> None:
        """Ouvre l'éditeur ; son résultat est mis en attente."""
        result = self._editor(self.widget, self.shown(), library_thicknesses())
        if result is not None:
            self.set_pending(result)

    def load(self) -> None:
        """Relit le fichier et abandonne les modifications en attente."""
        self._saved = read_dimensions()
        self._pending = None
        self._show()

    def save(self) -> None:
        """Écrit les modifications en attente (écriture atomique). Si l'écriture échoue, le
        message s'affiche et les modifications restent en attente."""
        if self._pending is None:
            return
        try:
            write_dimensions(self._pending)
        except ValueError as error:
            plain_message(self.widget, translate_text(_NOT_SAVED), str(error), error=True)
            return
        self._saved, self._pending = self._pending, None
        self._show()

    def _show(self) -> None:
        self.summary.setText(edit.summary(self.shown()))
        self.summary.setStyleSheet("font-weight: bold;" if self._pending is not None else "")
