# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sélecteur visuel des chants d'une face (issue #5) : la face vue de face, ses quatre côtés
cliquables, orange quand l'arête est profilée, grisés sinon.

Le widget ne garde aucun état : il montre les codes cochés qu'on lui donne
(:meth:`FaceEdgeSelector.show_checked`) et signale le code de l'arête cliquée, que le panneau
coche ou décoche (une seule source de vérité : les cases du panneau).
"""

from __future__ import annotations

from collections.abc import Callable, Collection

from PySide import QtCore, QtGui

from freecad.menuiserie.core.edges import FACE_NAMES, face_sides, parse_face
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated

__all__ = ["FaceEdgeSelector"]

_BORDER = 16  # épaisseur cliquable d'un côté, en pixels
_ON = "#f57900"
_OFF = "#d3d7cf"
_FACE = "#f6d7a3"
_LINE = "#4e2f12"
_TIP: str = QT_TRANSLATE_NOOP("Menuiserie", "Cliquez sur un côté pour profiler ou non cette arête.")


def side_at(x: float, y: float, width: float, height: float, border: float = _BORDER) -> str | None:
    """Côté (``"top"``, ``"left"``, ``"right"``, ``"bottom"``) du rectangle ``width`` x
    ``height`` touché en ``(x, y)`` : le plus proche des quatre bords si le point est dans la
    bande de ``border`` pixels qui borde le rectangle, ``None`` ailleurs (au centre ou dehors)."""
    if not (0 <= x <= width and 0 <= y <= height):
        return None
    distances = {"top": y, "bottom": height - y, "left": x, "right": width - x}
    side = min(distances, key=lambda name: distances[name])
    return side if distances[side] <= border else None


class FaceEdgeSelector(QtGui.QWidget):  # type: ignore[misc]
    """Une face dessinée à plat avec ses 4 arêtes ; ``toggled(code)`` à chaque clic sur un côté."""

    def __init__(self, face: str, toggled: Callable[[str], None]) -> None:
        super().__init__()
        self.face = face
        self._toggled = toggled
        self._sides = {side: (neighbour, edge.code) for side, neighbour, edge in face_sides(face)}
        self._checked: frozenset[str] = frozenset()
        self.setObjectName(f"face_{face}")
        self.setMinimumSize(150, 110)
        self.setSizePolicy(QtGui.QSizePolicy.Policy.Expanding, QtGui.QSizePolicy.Policy.Fixed)
        self.setToolTip(translated(_TIP))

    @property
    def codes(self) -> frozenset[str]:
        """Codes des 4 arêtes de la face."""
        return frozenset(code for _, code in self._sides.values())

    def code_of(self, side: str) -> str:
        """Code de l'arête du côté ``side``."""
        return self._sides[side][1]

    def toggle_side(self, side: str) -> None:
        """Clic sur un côté (aussi appelé par les vérifications d'interface)."""
        self._toggled(self.code_of(side))

    def show_checked(self, codes: Collection[str]) -> None:
        """Côtés colorés pour les arêtes de ``codes``."""
        checked = frozenset(code for _, code in self._sides.values() if code in codes)
        if checked != self._checked:
            self._checked = checked
            self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Clic gauche sur un côté : l'arête change d'état."""
        point = event.pos()
        side = side_at(point.x(), point.y(), self.width(), self.height())
        if side is not None and event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.toggle_side(side)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Rectangle de la face, côtés colorés et noms des faces voisines."""
        del event
        painter = QtGui.QPainter(self)
        width, height = self.width() - 1, self.height() - 1
        rects = {
            "top": QtCore.QRect(0, 0, width, _BORDER),
            "bottom": QtCore.QRect(0, height - _BORDER, width, _BORDER),
            "left": QtCore.QRect(0, 0, _BORDER, height),
            "right": QtCore.QRect(width - _BORDER, 0, _BORDER, height),
        }
        painter.setPen(QtGui.QPen(QtGui.QColor(_LINE), 1))
        painter.setBrush(QtGui.QColor(_FACE))
        painter.drawRect(0, 0, width, height)
        for side, rect in rects.items():
            neighbour, code = self._sides[side]
            on = code in self._checked
            painter.setBrush(QtGui.QColor(_ON if on else _OFF))
            painter.drawRect(rect)
            painter.setPen(QtGui.QColor("#ffffff" if on else "#555753"))
            label = FACE_NAMES[parse_face(neighbour)]
            painter.save()
            painter.translate(rect.center())
            if side in ("left", "right"):  # texte couché le long du côté vertical
                painter.rotate(-90)
                rect = QtCore.QRect(
                    -rect.height() // 2, -rect.width() // 2, rect.height(), rect.width()
                )
            else:
                rect = QtCore.QRect(
                    -rect.width() // 2, -rect.height() // 2, rect.width(), rect.height()
                )
            painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, label)
            painter.restore()
            painter.setPen(QtGui.QPen(QtGui.QColor(_LINE), 1))
        painter.setPen(QtGui.QColor(_LINE))
        title = FACE_NAMES[parse_face(self.face)]
        painter.drawText(
            QtCore.QRect(_BORDER, _BORDER, width - 2 * _BORDER, height - 2 * _BORDER),
            QtCore.Qt.AlignmentFlag.AlignCenter,
            title,
        )
        painter.end()
