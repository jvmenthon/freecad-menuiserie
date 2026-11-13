# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin cliquable des arêtes d'une pièce (issue #5) : patron déplié ou boîte en perspective.

Patron : les six faces à plat en croix, chaque côté de case est une arête. Boîte : la pièce en
perspective (avant, droite, dessus), arêtes cliquables ; les faces cachées (dessous, arrière,
gauche) sont hachurées en gris et écartées de la boîte avec la mention « cachée », leurs arêtes
en pointillés à leur vraie place. Les arêtes choisies et les faces dont les quatre arêtes sont
choisies prennent la couleur de la pièce. Un clic sur une arête la (dé)coche, un clic dans une
face (dé)coche ses quatre arêtes.

Le widget ne garde aucun état des arêtes : il montre les codes qu'on lui donne
(:meth:`EdgeDiagram.show_checked`) et signale ce qui est cliqué. Géométrie et clics :
:mod:`freecad.menuiserie.core.edges` (sans Qt).
"""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.core.edges import (
    FACE_NAMES,
    BoxView,
    Hit,
    box_hit,
    box_view,
    face_edges,
    face_ring_codes,
    face_sides,
    net_cells,
    net_hit,
    parse_face,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.features.i18n import translated

__all__ = ["BOX", "NET", "VIEWS", "EdgeDiagram"]

NET: Final = "net"
BOX: Final = "box"
VIEWS: Final = (NET, BOX)
_FACE: Final = "#f6d7a3"
_SHADES: Final = {"Z+": "#f6d7a3", "Y-": "#e0b377", "X+": "#c79657"}
_LINE: Final = "#7a5a30"
_OFF: Final = "#d3d7cf"
_HIDDEN_LINE: Final = "#9a9a9a"
_TINT_WHITE: Final = 0.6  # part de blanc dans la teinte d'une face choisie
_HEIGHT: Final = 180
_HIDDEN_NOTE: Final = QT_TRANSLATE_NOOP("Menuiserie", "cachée")
_TIP: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "Cliquez sur une arête pour la profiler ou non, dans une face pour ses quatre arêtes.",
)


def _qpoint(point: tuple[float, float]) -> QtCore.QPointF:
    return QtCore.QPointF(point[0], point[1])


class EdgeDiagram(QtGui.QWidget):  # type: ignore[misc]
    """Les arêtes de la boîte ``dimensions`` dessinées en ``view`` (:data:`NET` ou
    :data:`BOX`) à la couleur ``color`` ; ``on_edge(code)`` ou ``on_face(face)`` à chaque clic."""

    def __init__(
        self,
        dimensions: Dimensions,
        color: str,
        view: str,
        on_edge: Callable[[str], None],
        on_face: Callable[[str], None],
    ) -> None:
        super().__init__()
        self.setObjectName("diagram")
        self._dimensions = dimensions
        self._color = QtGui.QColor(color)
        self._view = view if view in VIEWS else NET
        self._on_edge = on_edge
        self._on_face = on_face
        self._checked: frozenset[str] = frozenset()
        self.setMinimumSize(200, _HEIGHT)
        self.setSizePolicy(QtGui.QSizePolicy.Policy.Expanding, QtGui.QSizePolicy.Policy.Fixed)
        self.setToolTip(translated(_TIP))

    @property
    def view(self) -> str:
        """Dessin montré : :data:`NET` ou :data:`BOX`."""
        return self._view

    def set_view(self, view: str) -> None:
        """Change de dessin (patron ou boîte)."""
        if view in VIEWS and view != self._view:
            self._view = view
            self.update()

    def show_checked(self, codes: Collection[str]) -> None:
        """Arêtes ``codes`` montrées choisies."""
        checked = frozenset(codes)
        if checked != self._checked:
            self._checked = checked
            self.update()

    def hit(self, x: float, y: float) -> Hit | None:
        """Arête ou face sous le point ``(x, y)`` du widget (aussi pour les vérifications)."""
        if self._view == BOX:
            return box_hit(self._box(), x, y)
        return net_hit(net_cells(self.width(), self.height()), x, y)

    def click(self, hit: Hit) -> None:
        """Clic sur ``hit`` : l'arête, ou les quatre arêtes de la face, changent d'état."""
        if hit.kind == "edge":
            self._on_edge(hit.code)
        else:
            self._on_face(hit.code)

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """Clic gauche : arête ou face sous la souris."""
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        point = event.pos()
        hit = self.hit(point.x(), point.y())
        if hit is not None:
            self.click(hit)

    def _box(self) -> BoxView:
        return box_view(self._dimensions, self.width(), self.height())

    def _face_chosen(self, face: str) -> bool:
        return all(edge.code in self._checked for edge in face_edges(parse_face(face)))

    def _tint(self) -> QtGui.QColor:
        """Teinte d'une face choisie : la couleur de la pièce mêlée de blanc."""
        mix = _TINT_WHITE
        return QtGui.QColor(
            *(
                round(c + (255 - c) * mix)
                for c in (self._color.red(), self._color.green(), self._color.blue())
            )
        )

    # --- Peinture -------------------------------------------------------------------------

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Patron ou boîte, arêtes choisies à la couleur de la pièce."""
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if self._view == BOX:
            self._paint_box(painter)
        else:
            self._paint_net(painter)
        painter.end()

    def _paint_net(self, painter: QtGui.QPainter) -> None:
        for cell in net_cells(self.width(), self.height()):
            rect = QtCore.QRectF(cell.x, cell.y, cell.size, cell.size)
            painter.setPen(QtGui.QPen(QtGui.QColor(_LINE), 1))
            painter.setBrush(QtGui.QColor(_FACE))
            painter.drawRect(rect)
            if self._face_chosen(cell.face):
                painter.setBrush(self._tint())
                painter.drawRect(rect)
            band = max(3.0, cell.size * 0.12)
            ends = cell.sides()
            for side, _neighbour, edge in face_sides(cell.face):
                on = edge.code in self._checked
                pen = QtGui.QPen(self._color if on else QtGui.QColor(_OFF), band if on else 3.0)
                pen.setCapStyle(QtCore.Qt.PenCapStyle.FlatCap)
                painter.setPen(pen)
                start, end = ends[side]
                inset = band / 2 if on else 1.5
                painter.drawLine(*_inset_segment(start, end, side, inset))
            painter.setPen(QtGui.QColor(_LINE))
            painter.drawText(
                rect, QtCore.Qt.AlignmentFlag.AlignCenter, FACE_NAMES[parse_face(cell.face)]
            )

    def _paint_box(self, painter: QtGui.QPainter) -> None:
        view = self._box()
        hatch = QtGui.QBrush(QtGui.QColor(_HIDDEN_LINE), QtCore.Qt.BrushStyle.BDiagPattern)
        for face in view.faces:
            polygon = QtGui.QPolygonF([_qpoint(p) for p in face.outline])
            if face.hidden:
                pen = QtGui.QPen(QtGui.QColor(_HIDDEN_LINE), 1, QtCore.Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(self._tint() if self._face_chosen(face.code) else hatch)
                painter.drawPolygon(polygon)
                self._paint_ghost_sides(painter, face.code, face.outline)
                continue
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(_SHADES[face.code]))
            painter.drawPolygon(polygon)
            if self._face_chosen(face.code):
                painter.setBrush(self._tint())
                painter.drawPolygon(polygon)
        for edge in view.edges:
            on = edge.code in self._checked
            color = self._color if on else QtGui.QColor(_HIDDEN_LINE if edge.hidden else _LINE)
            width = (3.0 if edge.hidden else 4.5) if on else (1.0 if edge.hidden else 1.5)
            style = QtCore.Qt.PenStyle.DashLine if edge.hidden else QtCore.Qt.PenStyle.SolidLine
            pen = QtGui.QPen(color, width, style)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(_qpoint(edge.start), _qpoint(edge.end))
        for face in view.faces:
            name = FACE_NAMES[parse_face(face.code)]
            text = f"{name}\n{translated(_HIDDEN_NOTE)}" if face.hidden else name
            _label(painter, face.outline, text, italic=face.hidden)

    def _paint_ghost_sides(
        self, painter: QtGui.QPainter, face: str, outline: tuple[tuple[float, float], ...]
    ) -> None:
        """Côtés d'une face cachée écartée : ses arêtes choisies à la couleur de la pièce."""
        sides = zip(outline, outline[1:] + outline[:1], strict=True)
        for (start, end), code in zip(sides, face_ring_codes(face), strict=True):
            if code in self._checked:
                pen = QtGui.QPen(self._color, 3.0)
                painter.setPen(pen)
                painter.drawLine(_qpoint(start), _qpoint(end))


def _label(
    painter: QtGui.QPainter, outline: tuple[tuple[float, float], ...], text: str, *, italic: bool
) -> None:
    """Texte centré sur le centre du contour, en petits caractères (italique : face cachée)."""
    x = sum(p[0] for p in outline) / len(outline)
    y = sum(p[1] for p in outline) / len(outline)
    painter.save()
    font = painter.font()
    font.setPointSizeF(max(6.0, font.pointSizeF() * 0.8))
    font.setItalic(italic)
    painter.setFont(font)
    painter.setPen(QtGui.QColor("#555753" if italic else _LINE))
    rect = QtCore.QRectF(x - 50, y - 16, 100, 32)
    painter.drawText(rect, QtCore.Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()


def _inset_segment(
    start: tuple[float, float], end: tuple[float, float], side: str, inset: float
) -> tuple[QtCore.QPointF, QtCore.QPointF]:
    """Côté de case décalé de ``inset`` vers l'intérieur (le trait reste dans sa case)."""
    dx, dy = {"top": (0, inset), "bottom": (0, -inset), "left": (inset, 0), "right": (-inset, 0)}[
        side
    ]
    return (
        QtCore.QPointF(start[0] + dx, start[1] + dy),
        QtCore.QPointF(end[0] + dx, end[1] + dy),
    )
