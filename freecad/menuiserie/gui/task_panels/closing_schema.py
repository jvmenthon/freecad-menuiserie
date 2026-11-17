# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schéma cliquable du caisson à fermer (ADR 0064, maquette B).

Le caisson est dessiné en isométrie, chaque élément d'une couleur ; un clic sur un élément
l'active ou le désactive. Un élément désactivé est en pointillé, barré d'une croix rouge, avec une
étiquette « ✕ nom » sur laquelle on clique pour le rajouter (l'avant, caché derrière les côtés,
n'a pas d'autre point cliquable). Projection et clic : :mod:`freecad.menuiserie.core.templates
.closing_schema` (sans Qt) ; le widget ne garde que ce qu'on lui montre (:meth:`ClosingSchema
.show_layout`) et signale l'élément cliqué.
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.templates import Layout
from freecad.menuiserie.core.templates.closing_schema import (
    Face,
    centroid,
    click_point,
    fit,
    hit_test,
    schema_faces,
)
from freecad.menuiserie.features.i18n import translated

__all__ = ["COLORS", "NAMES", "ClosingSchema"]

COLORS: Final = {
    "anchor": "#3573b9",
    "left": "#1f9d9d",
    "right": "#e08a1e",
    "back": "#8e44ad",
    "opposite": "#4e9a06",
    "front": "#bdbdbd",
}
NAMES: Final = {
    "left": QT_TRANSLATE_NOOP("Menuiserie", "Côté gauche"),
    "right": QT_TRANSLATE_NOOP("Menuiserie", "Côté droit"),
    "back": QT_TRANSLATE_NOOP("Menuiserie", "Fond"),
    "front": QT_TRANSLATE_NOOP("Menuiserie", "Avant"),
    "opposite": QT_TRANSLATE_NOOP("Menuiserie", "Pièce opposée"),
}
_SHADE: Final = {"top": 130, "front": 100, "right": 115}  # ``lighter`` : 100 = teinte pure
_ALPHA: Final = 120
_MARGIN: Final = 14.0
_CHIP_HEIGHT: Final = 20.0
_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cliquez sur un élément du schéma pour l'activer ou le désactiver (désactivé : pointillé et "
    "croix rouge).",
)


class ClosingSchema(QtGui.QWidget):  # type: ignore[misc]
    """Dessin du caisson fermé ; ``on_toggle(élément)`` à chaque clic sur un élément."""

    def __init__(self, on_toggle: Callable[[str], None]) -> None:
        super().__init__()
        self.setObjectName("closingSchema")
        self._on_toggle = on_toggle
        self._faces: tuple[Face, ...] = ()
        self._enabled: frozenset[str] = frozenset()
        self.setMinimumSize(280, 230)
        self.setSizePolicy(QtGui.QSizePolicy.Policy.Expanding, QtGui.QSizePolicy.Policy.Minimum)
        self.setToolTip(translated(_TIP))

    def show_layout(self, layout: Layout, enabled: Collection[str]) -> None:
        """Dessine toutes les pièces de ``layout`` (même désactivées) ; ``enabled`` : clés des
        éléments actifs."""
        self._faces = schema_faces(layout)
        self._enabled = frozenset(enabled) | {"anchor"}
        self.update()

    # --- Géométrie ------------------------------------------------------------------------

    def _fitted(self) -> tuple[Face, ...]:
        return fit(self._faces, self.width(), self.height(), _MARGIN)

    def _chips(self) -> dict[str, QtCore.QRectF]:
        """Étiquette cliquable de chaque élément désactivé, au centre de sa plus grande face."""
        faces = self._fitted()
        chips: dict[str, QtCore.QRectF] = {}
        for key in NAMES:
            mine = [face for face in faces if face.element == key]
            if key in self._enabled or not mine:
                continue
            x, y = centroid(max(mine, key=Face.area))
            width = 20.0 + 7.0 * len(translated(NAMES[key]))
            chips[key] = QtCore.QRectF(x - width / 2, y - _CHIP_HEIGHT / 2, width, _CHIP_HEIGHT)
        return _spread(chips)

    def element_at(self, x: float, y: float) -> str | None:
        """Élément sous le point ``(x, y)`` du widget : une étiquette d'élément désactivé, sinon le
        dessin (:func:`~freecad.menuiserie.core.templates.closing_schema.hit_test`)."""
        for key, chip in self._chips().items():
            if chip.contains(x, y):
                return key
        return hit_test(self._fitted(), self._enabled, (x, y))

    def position_of(self, element: str) -> tuple[int, int] | None:
        """Point du widget où cliquer pour désigner ``element`` (étiquette, sinon dessin) ; ``None``
        s'il est caché. Pour les vérifications."""
        chip = self._chips().get(element)
        if chip is not None:
            return round(chip.center().x()), round(chip.center().y())
        found = click_point(self._fitted(), self._enabled, element)
        return None if found is None else (round(found[0]), round(found[1]))

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Clic gauche : l'élément touché change d'état (l'ancre ne se désactive pas)."""
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        point = event.pos()
        element = self.element_at(point.x(), point.y())
        if element is not None and element != "anchor":
            self._on_toggle(element)

    # --- Peinture -------------------------------------------------------------------------

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        """Faces de l'arrière vers l'avant, puis croix et étiquettes des éléments désactivés."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        faces = self._fitted()
        for face in faces:
            self._paint_face(painter, face)
        self._paint_disabled(painter, faces)
        painter.end()

    def _paint_face(self, painter: QtGui.QPainter, face: Face) -> None:
        polygon = QtGui.QPolygonF([QtCore.QPointF(x, y) for x, y in face.points])
        base = QtGui.QColor(COLORS[face.element])
        if face.element in self._enabled:
            fill = base.lighter(_SHADE[face.side])
            fill.setAlpha(_ALPHA if face.element != "anchor" else 200)
            painter.setBrush(QtGui.QBrush(fill))
            painter.setPen(QtGui.QPen(QtGui.QColor("#2e3436"), 1.0))
        else:
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(QtGui.QColor("#888a85"), 1.0, QtCore.Qt.PenStyle.DashLine))
        painter.drawPolygon(polygon)

    def _paint_disabled(self, painter: QtGui.QPainter, faces: tuple[Face, ...]) -> None:
        for key, chip in self._chips().items():
            mine = [face for face in faces if face.element == key]
            x, y = centroid(max(mine, key=Face.area))
            painter.setPen(QtGui.QPen(QtGui.QColor("#cc0000"), 2.5))
            painter.drawLine(QtCore.QPointF(x - 8, y - 38), QtCore.QPointF(x + 8, y - 22))
            painter.drawLine(QtCore.QPointF(x + 8, y - 38), QtCore.QPointF(x - 8, y - 22))
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 220)))
            painter.setPen(QtGui.QPen(QtGui.QColor("#888a85"), 1.0, QtCore.Qt.PenStyle.DashLine))
            painter.drawRoundedRect(chip, 4, 4)
            painter.setPen(QtGui.QColor("#555753"))
            painter.drawText(
                chip, QtCore.Qt.AlignmentFlag.AlignCenter, f"✕ {translated(NAMES[key])}"
            )


def _spread(chips: dict[str, QtCore.QRectF]) -> dict[str, QtCore.QRectF]:
    """Étiquettes décalées vers le bas quand elles se recouvrent (dans l'ordre d'insertion)."""
    placed: list[QtCore.QRectF] = []
    for key, chip in chips.items():
        while any(chip.intersects(other) for other in placed):
            chip.translate(0.0, _CHIP_HEIGHT + 2.0)
        placed.append(chip)
        chips[key] = chip
    return chips
