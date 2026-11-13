# SPDX-License-Identifier: LGPL-2.1-or-later
"""Panneau « Aligner deux faces » (AL-c, ADR 0054).

Le panneau montre les deux faces, la pièce déplacée (la pilotée) avec un bouton « Inverser » qui
échange la pilotée et la pilotante, le mode (automatique, au ras, face contre face, d'équerre) et
un décalage sur les trois axes de la face de référence (deux dans son plan, le 3e le long de sa
normale). La pièce suit les saisies en direct (:class:`FaceAlign` écrit son ``Placement`` sans
recalculer le document) ; « OK » relie l'ensemble éventuel et valide la transaction de la
commande, « Annuler » l'abandonne : rien n'a changé.
"""

from __future__ import annotations

from functools import partial
from typing import Final

import FreeCADGui as Gui
from PySide import QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.align import AlignMode
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.text import quoted_value
from freecad.menuiserie.features.drag_joints import DragCancelledError
from freecad.menuiserie.features.furniture_bindings import report
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.part_align import FaceAlign
from freecad.menuiserie.gui import joint_choice
from freecad.menuiserie.gui.commands.base import report_refusal
from freecad.menuiserie.gui.task_panels.base import (
    DeletionWatcher,
    TransactionTaskPanel,
    UpdateGuard,
    Widget,
    connect,
    show_panel,
)
from freecad.menuiserie.gui.task_panels.furniture_widgets import (
    message_label,
    quantity_field,
    show_message,
)

__all__ = ["AlignTaskPanel", "open_panel"]

FORM_NAME: Final = "AlignTaskPanel"
ICON: Final = "Menuiserie_AlignFaces.svg"
TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aligner deux faces")
_BETWEEN: Final = QT_TRANSLATE_NOOP("Menuiserie", "Entre : {first} et {second}")
_MOVED: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce déplacée (pilotée) : {label}")
_REFERENCE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Pièce de référence (pilotante) : {label}")
_SWAP: Final = QT_TRANSLATE_NOOP("Menuiserie", "Inverser")
_SWAP_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Échange la pièce pilotée et la pièce pilotante : l'autre pièce est déplacée. Annuler remet "
    "tout en place.",
)
_SWAP_IMPOSSIBLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "L'autre objet n'est pas une pièce de l'atelier : il ne peut pas être déplacé."
)
_MODE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Position")
_MODE_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Automatique : au ras ou face contre face, selon la plus petite rotation. Au ras : les deux "
    "faces regardent du même côté. Face contre face : les pièces se touchent. D'équerre : les "
    "deux faces sont perpendiculaires.",
)
_MODES: Final = (
    (AlignMode.AUTO, QT_TRANSLATE_NOOP("Menuiserie", "Automatique")),
    (AlignMode.FLUSH, QT_TRANSLATE_NOOP("Menuiserie", "Au ras")),
    (AlignMode.FACING, QT_TRANSLATE_NOOP("Menuiserie", "Face contre face")),
    (AlignMode.PERPENDICULAR, QT_TRANSLATE_NOOP("Menuiserie", "D'équerre")),
)
_OFFSET_ROWS: Final = (
    ("offsetX", QT_TRANSLATE_NOOP("Menuiserie", "Décalage 1er axe (dans le plan)")),
    ("offsetY", QT_TRANSLATE_NOOP("Menuiserie", "Décalage 2e axe (dans le plan)")),
    ("offsetZ", QT_TRANSLATE_NOOP("Menuiserie", "Décalage 3e axe (normale à la face)")),
)
_OFFSET_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Décalage de la pièce déplacée, mesuré dans le repère de la face de référence, avec une "
    "unité (« 5 mm ») ou un calcul. La pièce suit la saisie.",
)


class AlignTaskPanel(TransactionTaskPanel):
    """Panneau de tâche d'un alignement ; ``align`` est lu et déplacé par le panneau, qui doit
    être affiché dans la transaction ouverte par la commande."""

    def __init__(self, align: FaceAlign) -> None:
        part = align.moving_part
        watcher = DeletionWatcher(part, Gui.Control.closeDialog)
        super().__init__(part.Document, creating=True, watcher=watcher)
        self._align = align
        self._guard = UpdateGuard()
        self.form: Widget = QtGui.QWidget()
        self.form.setObjectName(FORM_NAME)
        self.form.setWindowIcon(QtGui.QIcon(icon_path(ICON)))
        self.form.setWindowTitle(translated(TITLE))
        self._build()
        self._start()

    # --- Formulaire -----------------------------------------------------------------------

    def _build(self) -> None:
        layout = QtGui.QVBoxLayout(self.form)
        self._between = message_label("betweenLabel")
        self._moved = message_label("movedLabel")
        self._reference = message_label("referenceLabel")
        layout.addWidget(self._between)
        layout.addWidget(self._moved)
        layout.addWidget(self._reference)
        self._swap = QtGui.QPushButton(translated(_SWAP))
        self._swap.setObjectName("swapButton")
        self._swap.setToolTip(translated(_SWAP_TIP if self._align.can_swap else _SWAP_IMPOSSIBLE))
        layout.addWidget(self._swap)
        row = QtGui.QHBoxLayout()
        row.addWidget(QtGui.QLabel(translated(_MODE)))
        self._mode = QtGui.QComboBox()
        self._mode.setObjectName("modeCombo")
        self._mode.setToolTip(translated(_MODE_TIP))
        for mode, text in _MODES:
            self._mode.addItem(translated(text), mode.value)
        row.addWidget(self._mode, 1)
        layout.addLayout(row)
        self._offsets = []
        for name, text in _OFFSET_ROWS:
            line = QtGui.QHBoxLayout()
            line.addWidget(QtGui.QLabel(translated(text)))
            field = quantity_field(name, 0.0)
            field.setToolTip(translated(_OFFSET_TIP))
            line.addWidget(field)
            layout.addLayout(line)
            self._offsets.append(field)
            connect(field, "valueChanged(double)", self._edited)
        self._error = message_label("errorLabel", error=True)
        layout.addWidget(self._error)
        layout.addStretch(1)
        connect(self._swap, "clicked()", self._swapped)
        connect(self._mode, "currentIndexChanged(int)", self._edited)

    def _show_labels(self) -> None:
        first, second = self._align.elements
        self._between.setText(
            translated(_BETWEEN, {"first": first.label(), "second": second.label()})
        )
        moved = quoted_value(self._align.moving_part.Label)
        self._moved.setText(translated(_MOVED, {"label": moved}))
        other = self._align.elements[1 - self._align.moving_index].label()
        self._reference.setText(translated(_REFERENCE, {"label": quoted_value(other)}))
        self._swap.setEnabled(self._align.can_swap)

    def _start(self) -> None:
        with self._guard:
            self._show_labels()
        try:
            self._align.begin()
        except ValueError as error:
            show_message(self._error, str(error))
            return
        self._preview()

    # --- Saisies --------------------------------------------------------------------------

    def _chosen_mode(self) -> AlignMode:
        return AlignMode(str(self._mode.currentData()))

    def _offset(self) -> Vec3:
        x, y, z = (round(float(field.property("rawValue")), 6) for field in self._offsets)
        return Vec3(x, y, z)

    def _preview(self) -> bool:
        """La pièce est placée d'après les champs ; un refus s'affiche en rouge."""
        try:
            self._align.preview(self._chosen_mode(), self._offset())
        except (TypeError, ValueError, RuntimeError) as error:
            show_message(self._error, str(error))
            return False
        show_message(self._error, "")
        return True

    def _edited(self, *_value: object) -> None:
        if not self._guard.active:
            self._preview()

    def _swapped(self) -> None:
        """Inverser : l'autre pièce est déplacée avec les mêmes réglages ; la première revient."""
        self._align.swap()
        with self._guard:
            self._show_labels()
        try:
            self._align.begin()
        except ValueError as error:
            show_message(self._error, str(error))
            return
        self._preview()

    # --- Fermeture ------------------------------------------------------------------------

    def accept(self) -> bool:
        """« OK » : la pièce est placée, l'ensemble relié et la transaction validée ; un refus
        s'affiche sans fermer le panneau."""
        if not self._preview():
            return False
        try:
            messages = self._align.finish(joint_choice.choose)
        except DragCancelledError:  # assemblages défaits, « Annuler le déplacement » (ADR 0026)
            return self.reject()
        except (TypeError, ValueError) as error:
            report_refusal(str(error))
            return self.reject()
        report(messages)
        return super().accept()

    def reject(self) -> bool:
        """« Annuler » : la pièce revient et la transaction est abandonnée."""
        self._align.cancel()
        return super().reject()


def open_panel(align: FaceAlign) -> None:
    """Affiche le panneau de ``align`` dans la transaction ouverte par la commande ; une
    exception l'abandonne."""
    show_panel(partial(AlignTaskPanel, align))
