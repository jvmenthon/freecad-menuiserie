# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ligne « Matériau de toutes les pièces » du panneau de l'ensemble (issue #77) : liste des
matériaux de la bibliothèque et bouton « Appliquer ». L'écriture est faite par le panneau
(transaction, aperçu) ; ce module ne construit que les champs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from PySide import QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.library import display_language, get_library
from freecad.menuiserie.gui.task_panels.base import Widget, connect

__all__ = ["MaterialRow"]

_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "Matériau de toutes les pièces")
_APPLY: Final = QT_TRANSLATE_NOOP("Menuiserie", "Appliquer")
_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Donne ce matériau à toutes les pièces de l'ensemble, sous-ensembles compris. Une pièce dont "
    "le matériau suit une expression est laissée telle quelle.",
)


class MaterialRow:
    """Matériaux et bouton « Appliquer » ; ``applied(material_id)`` est appelée au clic."""

    def __init__(self, layout: Widget, applied: Callable[[str], None]) -> None:
        self._applied = applied
        layout.addWidget(QtGui.QLabel(translated(_LABEL)))
        row = QtGui.QHBoxLayout()
        self.combo = QtGui.QComboBox()
        self.combo.setObjectName("furnitureMaterialCombo")
        for material in get_library().by_kind():
            self.combo.addItem(material.name(display_language()), material.id)
        self.button = QtGui.QPushButton(translated(_APPLY))
        self.button.setObjectName("furnitureMaterialButton")
        self.button.setToolTip(translated(_TIP))
        self.button.setEnabled(self.combo.count() > 0)
        row.addWidget(self.combo, 1)
        row.addWidget(self.button)
        layout.addLayout(row)
        connect(self.button, "clicked()", self._clicked)

    def _clicked(self) -> None:
        material_id = self.combo.currentData()
        if isinstance(material_id, str):
            self._applied(material_id)
