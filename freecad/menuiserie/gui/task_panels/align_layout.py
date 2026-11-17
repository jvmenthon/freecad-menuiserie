# SPDX-License-Identifier: LGPL-2.1-or-later
"""Grille « Parallèle et aligner sur » du panneau « Aligner deux faces » (ADR 0054, maquette 2
choisie par jv le 2026-11-16, logo F du 2026-11-17).

Une ligne par axe X, Y, Z du conteneur de la pièce déplacée : un bouton « // » (le grand côté de
la pièce devient parallèle à cet axe ; un seul axe à la fois) puis trois boutons début, centre,
fin (où la face déplacée se place le long de cet axe, par rapport à l'autre face ; un seul par
ligne). Recliquer un bouton coché l'éteint. La ligne d'un axe qui suit la normale des faces est
grisée, avec une infobulle qui dit pourquoi.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie import icon_path
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import Widget, connect

__all__ = ["AXES", "LayoutGrid"]

AXES: Final = ("X", "Y", "Z")
# Couleurs des axes, celles des rotations et des icônes.
_COLORS: Final = {"X": "#cc0000", "Y": "#4e9a06", "Z": "#3465a4"}
_TITLE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Parallèle et aligner sur")
_PARALLEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "//")
_PARALLEL_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Rendre parallèle à {axis} : la pièce déplacée tourne dans le plan des faces pour que son "
    "grand côté soit parallèle à l'axe {axis} (du Std Part de la pièce déplacée, ou du "
    "document). Un seul axe à la fois ; grisé quand le déplacement se fait sur un axe.",
)
_ANCHORS: Final = (
    ("start", "Start", QT_TRANSLATE_NOOP("Menuiserie", "Début")),
    ("center", "Center", QT_TRANSLATE_NOOP("Menuiserie", "Centre")),
    ("end", "End", QT_TRANSLATE_NOOP("Menuiserie", "Fin")),
)
_ANCHOR_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{anchor} sur {axis} : le long de l'axe {axis}, la face déplacée se place au même {anchor} "
    "que l'autre face (début : côté moins de l'axe ; fin : côté plus). Recliquer l'éteint.",
)
_ACROSS_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "{axis} suit la normale des faces alignées : la pièce ne peut pas y être rendue parallèle "
    "ni alignée. La distance entre les faces se règle avec « Position » et le 3e décalage.",
)
_ICON_SIZE: Final = 28


def _tool_button(name: str, icon: str, tip: str, accessible: str) -> Widget:
    button = QtGui.QToolButton()
    button.setObjectName(name)
    button.setCheckable(True)
    button.setIcon(QtGui.QIcon(icon_path(icon)))
    button.setIconSize(QtCore.QSize(_ICON_SIZE, _ICON_SIZE))
    button.setToolTip(tip)
    button.setAccessibleName(accessible)
    return button


class LayoutGrid:
    """Grille des axes ; ``changed`` est appelé à chaque bouton coché ou décoché par
    l'utilisateur (pas pendant :meth:`set_across` ni :meth:`set_parallel_allowed`)."""

    def __init__(self, layout: Widget, changed: Callable[[], None]) -> None:
        self._changed = changed
        self._quiet = False
        self._parallel: dict[str, Widget] = {}
        self._anchors: dict[str, dict[str, Widget]] = {}
        self._labels: dict[str, Widget] = {}
        self._across = ""
        self._parallel_allowed = True
        title = QtGui.QLabel(translated(_TITLE))
        title.setObjectName("layoutTitle")
        layout.addWidget(title)
        grid = QtGui.QGridLayout()
        grid.addWidget(_header(translated(_PARALLEL)), 0, 1)
        for column, (_value, _icon, text) in enumerate(_ANCHORS, start=2):
            grid.addWidget(_header(translated(text)), 0, column)
        for row, axis in enumerate(AXES, start=1):
            self._add_row(grid, row, axis)
        grid.setColumnStretch(len(_ANCHORS) + 2, 1)
        layout.addLayout(grid)

    def _add_row(self, grid: Widget, row: int, axis: str) -> None:
        label = QtGui.QLabel(axis)
        label.setObjectName(f"layoutAxis{axis}")
        label.setStyleSheet(f"color: {_COLORS[axis]}; font-weight: bold;")
        grid.addWidget(label, row, 0)
        self._labels[axis] = label
        parallel = _tool_button(
            f"parallel{axis}Button",
            f"Menuiserie_Parallel{axis}.svg",
            translated(_PARALLEL_TIP, {"axis": axis}),
            f"{translated(_PARALLEL)} {axis}",
        )
        connect(parallel, "toggled(bool)", lambda on, a=axis: self._parallel_toggled(a, on))
        grid.addWidget(parallel, row, 1)
        self._parallel[axis] = parallel
        self._anchors[axis] = {}
        for column, (value, icon, text) in enumerate(_ANCHORS, start=2):
            shown = translated(text)
            button = _tool_button(
                f"{value}{axis}Button",
                f"Menuiserie_Align{icon}.svg",
                translated(_ANCHOR_TIP, {"anchor": shown.lower(), "axis": axis}),
                f"{shown} {axis}",
            )
            connect(
                button,
                "toggled(bool)",
                lambda on, a=axis, v=value: self._anchor_toggled(a, v, on),
            )
            grid.addWidget(button, row, column)
            self._anchors[axis][value] = button

    # --- Lecture ------------------------------------------------------------------------

    def layout(self) -> dict[str, str]:
        """Disposition cochée, au format de ``FaceAlign.plan`` (``{"parallel": "X", "Y":
        "center"}``…)."""
        chosen: dict[str, str] = {}
        for axis in AXES:
            if self._parallel[axis].isChecked():
                chosen["parallel"] = axis
            for value, button in self._anchors[axis].items():
                if button.isChecked():
                    chosen[axis] = value
        return chosen

    # --- Réglages venus du panneau ------------------------------------------------------

    def set_across(self, across: str) -> None:
        """Grise (et décoche) les lignes des axes ``across`` qui suivent la normale des faces."""
        self._across = across
        self._refresh()

    def set_parallel_allowed(self, allowed: bool) -> None:
        """Grise (et décoche) la colonne « // » quand la pièce ne peut pas tourner (sur un axe)."""
        self._parallel_allowed = allowed
        self._refresh()

    def _refresh(self) -> None:
        self._quiet = True
        try:
            for axis in AXES:
                usable = axis not in self._across
                tip = translated(_ACROSS_TIP, {"axis": axis}) if not usable else ""
                self._labels[axis].setEnabled(usable)
                self._labels[axis].setToolTip(tip)
                parallel_ok = usable and self._parallel_allowed
                self._enable(self._parallel[axis], parallel_ok)
                for button in self._anchors[axis].values():
                    self._enable(button, usable)
        finally:
            self._quiet = False

    @staticmethod
    def _enable(button: Widget, enabled: bool) -> None:
        if not enabled:
            button.setChecked(False)
        button.setEnabled(enabled)

    # --- Exclusions ---------------------------------------------------------------------

    def _parallel_toggled(self, axis: str, on: bool) -> None:
        if self._quiet:
            return
        if on:
            self._uncheck(button for other, button in self._parallel.items() if other != axis)
        self._changed()

    def _anchor_toggled(self, axis: str, value: str, on: bool) -> None:
        if self._quiet:
            return
        if on:
            row = self._anchors[axis]
            self._uncheck(button for other, button in row.items() if other != value)
        self._changed()

    def _uncheck(self, buttons: Iterable[Widget]) -> None:
        self._quiet = True
        try:
            for button in buttons:
                button.setChecked(False)
        finally:
            self._quiet = False


def _header(text: str) -> Widget:
    label = QtGui.QLabel(text)
    label.setAlignment(QtCore.Qt.AlignCenter)
    return label
