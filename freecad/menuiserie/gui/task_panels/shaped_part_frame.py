# SPDX-License-Identifier: LGPL-2.1-or-later
"""Groupe « Repère de la pièce » du panneau de la pièce en bois (D2) : trois boutons de quart de
tour qui changent quel axe de la forme est la longueur, la largeur ou l'épaisseur, et le bouton
« Repère automatique ».

La pièce ne bouge pas : son ``Placement`` est corrigé en même temps que ``SourceAxes``
(:func:`.shaped_create.reframe`). Les widgets sont créés ici et ajoutés au formulaire par le
panneau ; le groupe ne garde que ses propres widgets et l'objet du panneau.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any, Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.shaped import turned_axes
from freecad.menuiserie.core.snap import Turn
from freecad.menuiserie.features.freecad_types import DocumentObject, placement_expression
from freecad.menuiserie.features.i18n import report_warning, translated
from freecad.menuiserie.features.shaped_create import reframe, reset_axes
from freecad.menuiserie.features.shaped_frame import placement_axes
from freecad.menuiserie.gui.task_panels.base import connect, weak_callback

__all__ = ["FRAME_TURNS", "FrameRows"]

Widget = Any
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Repère de la pièce")
_LEGEND: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Dans la vue : longueur L en rouge, largeur l en vert, épaisseur e en bleu, fil en orange. "
    "Un quart de tour change l'axe de la forme pris pour L, l ou e ; la pièce ne bouge pas.",
)
_AUTOMATIC: Final = QT_TRANSLATE_NOOP("Menuiserie", "Repère automatique")
_AUTOMATIC_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Recalcule le repère d'après la forme actuelle : la plus grande étendue devient la longueur, "
    "la plus petite l'épaisseur.",
)
_DRIVEN: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "La position de cette pièce est pilotée par une expression : retirez l'expression pour "
    "changer son repère.",
)
# Boutons : nom du widget, axe de la pièce tourné, libellé et infobulle.
FRAME_TURNS: Final = (
    (
        "turnLengthButton",
        Turn.X,
        QT_TRANSLATE_NOOP("Menuiserie", "Autour de L"),
        QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Quart de tour autour de la longueur : la largeur et l'épaisseur changent.",
        ),
    ),
    (
        "turnWidthButton",
        Turn.Y,
        QT_TRANSLATE_NOOP("Menuiserie", "Autour de l"),
        QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Quart de tour autour de la largeur : la longueur et l'épaisseur changent.",
        ),
    ),
    (
        "turnThicknessButton",
        Turn.Z,
        QT_TRANSLATE_NOOP("Menuiserie", "Autour de e"),
        QT_TRANSLATE_NOOP(
            "Menuiserie",
            "Quart de tour autour de l'épaisseur : la longueur et la largeur changent.",
        ),
    ),
)


class FrameRows:
    """Groupe « Repère de la pièce » de la pièce en bois ``obj``. ``on_changed`` : appelé après un
    changement de repère (le panneau recalcule l'aperçu et relit les cotes)."""

    def __init__(self, obj: DocumentObject, on_changed: Callable[[], None]) -> None:
        self._obj = obj
        self._on_changed = weak_callback(on_changed)
        self.group = QtGui.QGroupBox(translated(_TITLE))
        self.group.setObjectName("frameGroup")
        layout = QtGui.QVBoxLayout(self.group)
        legend = QtGui.QLabel(translated(_LEGEND))
        legend.setObjectName("frameLegend")
        legend.setWordWrap(True)
        legend.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(legend)
        turns = QtGui.QHBoxLayout()
        layout.addLayout(turns)
        self._buttons: list[Widget] = []
        for name, _turn, label, tip in FRAME_TURNS:
            button = QtGui.QToolButton()
            button.setObjectName(name)
            button.setText(translated(label))
            button.setToolTip(translated(tip))
            turns.addWidget(button)
            self._buttons.append(button)
        self._automatic = QtGui.QPushButton(translated(_AUTOMATIC))
        self._automatic.setObjectName("automaticAxesButton")
        self._automatic.setToolTip(translated(_AUTOMATIC_TIP))
        self._automatic.setAutoDefault(False)
        layout.addWidget(self._automatic)
        if placement_expression(obj) is not None:
            for button in (*self._buttons, self._automatic):
                button.setEnabled(False)
                button.setToolTip(translated(_DRIVEN))

    def connect_signals(self) -> None:
        """Boutons de quart de tour et « Repère automatique »."""
        for button, (_name, turn, _label, _tip) in zip(self._buttons, FRAME_TURNS, strict=True):
            connect(button, "clicked()", partial(self._on_turn, turn))
        connect(self._automatic, "clicked()", self._on_automatic)

    def _on_turn(self, turn: Turn) -> None:
        """Quart de tour du repère ; la source illisible ou refusée est signalée, rien n'est
        changé."""
        try:
            axes = turned_axes(placement_axes(self._obj.SourceAxes), turn)
            reframe(self._obj, axes)
        except (TypeError, ValueError) as error:
            report_warning(str(error))
            return
        self._on_changed()

    def _on_automatic(self) -> None:
        """Repère automatique d'après la forme actuelle (avertissement si elle est trop
        détaillée : les axes de la source sont gardés)."""
        try:
            reset_axes(self._obj)
        except (TypeError, ValueError) as error:
            report_warning(str(error))
            return
        self._on_changed()
