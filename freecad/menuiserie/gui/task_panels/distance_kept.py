# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau d'une Distance gardée existante (DI-c, critère F8, ADR 0022).

Double-clic sur la Distance dans l'arborescence : les deux pièces, le champ « Distance » (la
``Value`` de l'objet, unités et calculs de FreeCAD) et la case « Garder cette distance », cochée.
Les pièces suivent la saisie en direct (leurs expressions citent ``Name.Value``) ; « OK » valide
la transaction, « Annuler » l'abandonne. Décocher la case puis « OK » supprime la Distance : les
pièces restent où elles sont et l'ensemble est relié sans elle. Une ``Value`` pilotée par une
expression de l'utilisateur (tableur) n'est pas modifiable ici.
"""

from __future__ import annotations

from functools import partial
from typing import Final

from PySide import QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.distance import distance_furniture
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels import base
from freecad.menuiserie.gui.task_panels.base import ObjectTaskPanel, UpdateGuard, Widget, connect
from freecad.menuiserie.gui.task_panels.furniture_widgets import (
    message_label,
    quantity_field,
    show_message,
)

__all__ = ["KeptDistancePanel", "start_editing"]

FORM_NAME: Final = "KeptDistancePanel"
ICON: Final = "Menuiserie_Distance.svg"
EDIT_TRANSACTION: Final = QT_TRANSLATE_NOOP("Menuiserie", "Modifier une distance")
_BETWEEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Entre : {first} et {second}")
_MISSING: Final = QT_TRANSLATE_NOOP("Menuiserie", "(pièce supprimée)")
_DISTANCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Distance")
_DISTANCE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Distance gardée entre les deux faces, avec une unité (« 320 mm ») ou un calcul "
    "(« 300 mm + 20 mm »). Les pièces de l'ensemble suivent la saisie.",
)
_DRIVEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La valeur de cette distance suit une expression : modifiez l'expression.",
)
_KEEP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Garder cette distance")
_KEEP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cochée : les pièces gardent cette distance quand l'ensemble change. Décochée, « OK » "
    "supprime la distance ; les pièces restent où elles sont.",
)


def _label(piece: DocumentObject | None) -> str:
    return quoted_value(piece.Label) if piece is not None else translated(_MISSING)


class KeptDistancePanel(ObjectTaskPanel):
    """Panneau de tâche de la Distance ``obj`` (modification seulement)."""

    def __init__(self, obj: DocumentObject) -> None:
        super().__init__(obj, creating=False)
        self._guard = UpdateGuard()
        self.form: Widget = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(base.panel_title(quoted_value(obj.Label), False, ""))
        self._build()

    def _build(self) -> None:
        layout = QtGui.QVBoxLayout(self.form)
        pieces = {"first": _label(self.obj.PieceA), "second": _label(self.obj.PieceB)}
        between = message_label("betweenLabel")
        between.setText(translated(_BETWEEN, pieces))
        layout.addWidget(between)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(translated(_DISTANCE)))
        self._field = quantity_field("distanceEdit", 0.0)
        driven = has_expression(self.obj, "Value")
        self._field.setToolTip(translated(_DRIVEN if driven else _DISTANCE_TIP))
        self._field.setEnabled(not driven)
        with self._guard:
            self._field.setProperty("rawValue", self.obj.Value.Value)
        row.addWidget(self._field)
        layout.addLayout(row)
        self._keep = QtGui.QCheckBox(translated(_KEEP))
        self._keep.setObjectName("keepCheck")
        self._keep.setToolTip(translated(_KEEP_TIP))
        self._keep.setChecked(True)
        layout.addWidget(self._keep)
        self._error = message_label("errorLabel", error=True)
        layout.addWidget(self._error)
        layout.addStretch(1)
        connect(self._field, "valueChanged(double)", self._edited)

    def _value(self) -> float:
        return round(float(self._field.property("rawValue")), 6)

    def _edited(self, *_value: object) -> None:
        """La ``Value`` est écrite et les pièces qui la citent recalculées (aperçu)."""
        if self._guard.active:
            return
        try:
            self.obj.Value = self._value()
            self.preview()
        except (TypeError, ValueError, RuntimeError) as error:
            show_message(self._error, str(error))
            return
        show_message(self._error, "")

    def accept(self) -> bool:
        """« OK » : la Distance est supprimée si la case est décochée (l'ensemble est relié sans
        elle), sinon sa valeur est gardée ; la transaction est validée."""
        if not self._keep.isChecked():
            self._stop_watching()  # la suppression n'est pas un abandon du panneau
            self.obj.Document.removeObject(self.obj.Name)
        elif distance_furniture(self.obj) is None:
            show_message(self._error, translated(_MISSING))
            return False
        return super().accept()


def start_editing(obj: DocumentObject) -> bool:
    """Ouvre le panneau sur une Distance (double-clic), dans la transaction « Modifier une
    distance » ; faux si un autre panneau de tâche est déjà ouvert."""
    return base.start_editing(obj.Document, EDIT_TRANSACTION, partial(KeptDistancePanel, obj), obj)
