# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choix des arêtes du panneau « Finition des chants » (issue #5) : consigne tant qu'aucune
pièce n'est désignée, sélecteurs visuels des faces (une face choisie dans la vue 3D, ou les
faces qui portent les arêtes déjà profilées), raccourcis et liste des arêtes concernées avec
une croix pour retirer chacune.

Douze cases à cocher invisibles restent la seule source de vérité (une par arête) : le sélecteur
visuel et la liste les actionnent, ``changed`` est appelé à chaque changement.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from typing import Final

from PySide import QtGui

from freecad.menuiserie.core.edges import all_edges, faces_covering
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.gui.task_panels.base import Widget, connect
from freecad.menuiserie.gui.task_panels.face_edge_selector import FaceEdgeSelector

__all__ = ["EdgeTargets"]

_LIST: Final = QT_TRANSLATE_NOOP("Menuiserie", "Arêtes concernées")
_HINT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Sélectionnez dans la vue 3D une pièce, une face ou une arête à profiler."
)
_NONE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Aucune arête")
_CROSS: Final = QT_TRANSLATE_NOOP("Menuiserie", "✕")
_REMOVE: Final = QT_TRANSLATE_NOOP("Menuiserie", "Retirer cette arête")
_EMPTY: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cliquez sur une face, une arête ou un sommet de la pièce dans la vue 3D, ou choisissez "
    "« Toutes ».",
)
_SHORTCUTS: Final = (
    (QT_TRANSLATE_NOOP("Menuiserie", "Toutes"), "all"),
    (QT_TRANSLATE_NOOP("Menuiserie", "Aucune"), "none"),
)


class EdgeTargets:
    """Les arêtes choisies d'une pièce ; ``changed()`` après chaque changement de case."""

    def __init__(self, layout: Widget, changed: Callable[[], None]) -> None:
        self._changed = changed
        self._muted = False  # changements groupés : ``changed`` n'est appelé qu'à la fin
        self._selectors: dict[str, FaceEdgeSelector] = {}
        self.hint = QtGui.QLabel(translated(_HINT))
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.widget = QtGui.QWidget()
        inner = QtGui.QVBoxLayout(self.widget)
        inner.setContentsMargins(0, 0, 0, 0)
        self._faces = QtGui.QVBoxLayout()
        inner.addLayout(self._faces)
        self._empty = QtGui.QLabel(translated(_EMPTY))
        self._empty.setObjectName("empty_hint")
        self._empty.setWordWrap(True)
        inner.addWidget(self._empty)
        self.boxes = self._edge_boxes()
        self._add_shortcuts(inner)
        self._listed = QtGui.QGroupBox(translated(_LIST))
        self._listed.setObjectName("edge_list")
        self._rows = QtGui.QVBoxLayout(self._listed)
        inner.addWidget(self._listed)
        layout.addWidget(self.widget)
        self.show_for(has_part=False)
        self.refresh()

    def _edge_boxes(self) -> dict[str, Widget]:
        """Les douze cases à cocher, invisibles : l'état des arêtes choisies."""
        boxes: dict[str, Widget] = {}
        for edge in all_edges():
            box = QtGui.QCheckBox(edge.name, self.widget)
            box.setObjectName(edge.code)
            box.hide()
            connect(box, "toggled(bool)", self._box_toggled)
            boxes[edge.code] = box
        return boxes

    def _add_shortcuts(self, layout: Widget) -> None:
        row = QtGui.QHBoxLayout()
        for text, key in _SHORTCUTS:
            button = QtGui.QPushButton(translated(text))
            button.setObjectName(f"shortcut_{key}")
            connect(button, "clicked()", partial(self._shortcut, key))
            row.addWidget(button)
        layout.addLayout(row)

    def show_for(self, *, has_part: bool) -> None:
        """Choix des arêtes si une pièce est désignée, consigne sinon."""
        self.widget.setVisible(has_part)
        self.hint.setVisible(not has_part)

    def codes(self) -> list[str]:
        """Codes des arêtes cochées, dans l'ordre des douze arêtes."""
        return [edge.code for edge in all_edges() if self.boxes[edge.code].isChecked()]

    def check(self, codes: Sequence[str]) -> None:
        """Cases cochées pour ``codes`` (les autres ne changent pas) ; un seul ``changed``."""
        self._muted = True
        try:
            for code in codes:
                if code in self.boxes:
                    self.boxes[code].setChecked(True)
        finally:
            self._muted = False
        self.refresh()
        self._changed()

    def set_silently(self, codes: Sequence[str]) -> None:
        """Cases cochées pour ``codes``, sans ``changed`` (état initial d'un panneau)."""
        self._muted = True
        try:
            for code in codes:
                if code in self.boxes:
                    self.boxes[code].setChecked(True)
        finally:
            self._muted = False
        self.refresh()

    def add_face(self, face: str) -> None:
        """Sélecteur visuel d'une face choisie, à la place des cases à cocher."""
        if face in self._selectors:
            return
        selector = FaceEdgeSelector(face, self.toggle)
        self._selectors[face] = selector
        self._faces.addWidget(selector)
        self._empty.hide()

    def toggle(self, code: str) -> None:
        """Clic sur un côté d'un sélecteur de face : l'arête change d'état."""
        box = self.boxes.get(code)
        if box is not None:
            box.setChecked(not box.isChecked())

    def refresh(self) -> None:
        """Sélecteurs (ceux des faces qui portent des arêtes cochées s'ajoutent) et liste remis
        d'après les cases cochées."""
        codes = self.codes()
        shown = frozenset().union(*(selector.codes for selector in self._selectors.values()))
        for face in faces_covering([code for code in codes if code not in shown]):
            self.add_face(face)
        for selector in self._selectors.values():
            selector.show_checked(codes)
        self._refresh_list(codes)

    def _box_toggled(self, *_checked: object) -> None:
        if self._muted:
            return
        self.refresh()
        self._changed()

    def _shortcut(self, key: str) -> None:
        self._muted = True
        try:
            for box in self.boxes.values():
                box.setChecked(key == "all")
        finally:
            self._muted = False
        self.refresh()
        self._changed()

    def _refresh_list(self, codes: Sequence[str]) -> None:
        """Liste des arêtes concernées : une ligne par arête, avec une croix pour la retirer."""
        while self._rows.count():
            widget = self._rows.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for edge in all_edges():
            if edge.code not in codes:
                continue
            row = QtGui.QWidget()
            line = QtGui.QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.addWidget(QtGui.QLabel(edge.name))
            line.addStretch()
            remove = QtGui.QToolButton()
            remove.setObjectName(f"remove_{edge.code}")
            remove.setText(translated(_CROSS))
            remove.setToolTip(translated(_REMOVE))
            connect(remove, "clicked()", partial(self.remove, edge.code))
            line.addWidget(remove)
            self._rows.addWidget(row)
        if not codes:
            self._rows.addWidget(QtGui.QLabel(translated(_NONE)))

    def remove(self, code: str) -> None:
        """Croix d'une ligne de la liste : case décochée (l'arête perd son profil)."""
        box = self.boxes.get(code)
        if box is not None:
            box.setChecked(False)
