# SPDX-License-Identifier: LGPL-2.1-or-later
"""Image des étiquettes de poignée (ADR 0068, maquette I « étiquette de cote »).

Une étiquette est une pastille arrondie : double flèche dans l'axe de la cote (cadenas pour une
poignée impossible) puis la valeur de la cote. Elle est peinte par Qt avec lissage, ombre et halo
de survol, puis posée telle quelle dans la vue (``overlay.py``, ``SoImage`` : taille fixe à
l'écran). Les images sont gardées (mêmes texte, état, angle et échelle : même image).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.gui.drag.drawing import BADGE_H_PX, BADGE_W_PX, BadgeState

__all__ = ["badge_pixels"]

MARGIN_PX: Final = 6.0  # marge autour de la pastille : ombre et halo
ICON_X_PX: Final = 14.0  # centre de l'icône depuis le bord gauche de la pastille
TEXT_PX: Final = 13  # taille du texte de la cote
_CACHE: Final = 512
MAX_SIDE_PX: Final = 2048  # côté d'une étiquette au plus (SbVec2s : 16 bits)

# État : fond, bord, texte et icône, halo (None : aucun).
_LOOKS: Final = {
    BadgeState.NORMAL: ("#ff8a00", "#b04a00", "#ffffff", None),
    BadgeState.HOVER: ("#ffc400", "#b88600", "#3d2a00", "#ffc400"),
    BadgeState.LOCKED: ("#f3f5f7", "#9aa2ab", "#6d7680", None),
    BadgeState.LOCKED_HOVER: ("#ffffff", "#6d7680", "#4a5563", "#9aa2ab"),
}


def _font(scale: float) -> QtGui.QFont:
    font = QtGui.QFont()
    font.setPixelSize(max(1, round(TEXT_PX * scale)))
    font.setBold(True)
    return font


def _arrow(painter: QtGui.QPainter, color: QtGui.QColor, angle: float, scale: float) -> None:
    """Double flèche ↔ centrée sur l'origine du peintre, tournée de ``angle`` degrés (sens
    direct à l'écran ; l'image a son y vers le bas)."""
    painter.save()
    painter.rotate(-angle)
    painter.scale(scale * 0.85, scale * 0.85)
    pen = QtGui.QPen(color, 2.4)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    painter.setPen(pen)
    painter.drawLine(QtCore.QPointF(-5.0, 0.0), QtCore.QPointF(5.0, 0.0))
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(color)
    for sign in (1.0, -1.0):
        head = QtGui.QPolygonF(
            [
                QtCore.QPointF(sign * 3.0, -5.0),
                QtCore.QPointF(sign * 9.5, 0.0),
                QtCore.QPointF(sign * 3.0, 5.0),
            ]
        )
        painter.drawPolygon(head)
    painter.restore()


def _lock(painter: QtGui.QPainter, color: QtGui.QColor, scale: float) -> None:
    """Cadenas centré sur l'origine du peintre."""
    painter.save()
    painter.scale(scale * 0.75, scale * 0.75)
    pen = QtGui.QPen(color, 2.2)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    shackle = QtGui.QPainterPath(QtCore.QPointF(-4.5, -1.0))
    shackle.lineTo(-4.5, -4.5)
    shackle.arcTo(QtCore.QRectF(-4.5, -9.0, 9.0, 9.0), 180.0, -180.0)
    shackle.lineTo(4.5, -1.0)
    painter.drawPath(shackle)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(QtCore.QRectF(-6.5, -1.5, 13.0, 10.0), 2.5, 2.5)
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawEllipse(QtCore.QPointF(0.0, 3.2), 1.4, 1.4)
    painter.restore()


def _paint(text: str, state: str, angle: float, scale: float) -> QtGui.QImage:
    fill, edge, ink, glow = _LOOKS.get(state, _LOOKS[BadgeState.NORMAL])
    font = _font(scale)
    text_w = QtGui.QFontMetricsF(font).horizontalAdvance(text)
    height = BADGE_H_PX * scale
    width = max(BADGE_W_PX * scale, (ICON_X_PX + 12.0) * scale + text_w + 9.0 * scale)
    margin = MARGIN_PX * scale
    image = QtGui.QImage(
        math.ceil(width + 2 * margin),
        math.ceil(height + 2 * margin),
        QtGui.QImage.Format_ARGB32_Premultiplied,
    )
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        body = QtCore.QRectF(margin, margin, width, height)
        radius = height / 2
        painter.setPen(QtCore.Qt.NoPen)
        if glow is not None:  # halo de survol : trois couronnes de plus en plus claires
            for step, alpha in ((3, 40), (2, 70), (1, 110)):
                color = QtGui.QColor(glow)
                color.setAlpha(alpha)
                painter.setBrush(color)
                grow = step * 1.6 * scale
                halo = body.adjusted(-grow, -grow, grow, grow)
                painter.drawRoundedRect(halo, radius + grow, radius + grow)
        shadow = QtGui.QColor(0, 0, 0, 55)
        painter.setBrush(shadow)
        painter.drawRoundedRect(body.translated(0.0, 1.5 * scale), radius, radius)
        painter.setBrush(QtGui.QColor(fill))
        painter.setPen(QtGui.QPen(QtGui.QColor(edge), 1.2 * scale))
        painter.drawRoundedRect(body, radius, radius)
        icon = QtGui.QColor(ink)
        painter.translate(margin + ICON_X_PX * scale, margin + height / 2)
        if state in (BadgeState.LOCKED, BadgeState.LOCKED_HOVER):
            _lock(painter, icon, scale)
        else:
            _arrow(painter, icon, angle, scale)
        painter.resetTransform()
        painter.setFont(font)
        painter.setPen(icon)
        left = margin + (ICON_X_PX + 10.0) * scale
        area = QtCore.QRectF(left, margin, margin + width - left - 6.0 * scale, height)
        painter.drawText(area, QtCore.Qt.AlignCenter, text)
    finally:
        painter.end()
    return image


@lru_cache(maxsize=_CACHE)
def badge_pixels(text: str, state: str, angle: float, scale: float) -> tuple[int, int, bytes]:
    """Largeur, hauteur et pixels RVBA (lignes du bas vers le haut, l'ordre de Coin) de
    l'étiquette ``text`` dans l'état ``state`` (:class:`BadgeState`), double flèche tournée de
    ``angle`` degrés, à l'échelle ``scale`` (rapport de pixels de l'écran)."""
    image = _paint(text, state, angle, scale).convertToFormat(QtGui.QImage.Format_RGBA8888)
    flip = getattr(image, "flipped", None)  # Qt ≥ 6.9 ; ``mirrored`` avant
    image = flip(QtCore.Qt.Vertical) if flip is not None else image.mirrored(False, True)
    width, height = image.width(), image.height()
    data = bytes(image.constBits())[: width * height * 4]
    if (
        not (0 < width <= MAX_SIDE_PX and 0 < height <= MAX_SIDE_PX)
        or len(data) != 4 * width * height
    ):
        return 1, 1, bytes(4)  # image ratée : un pixel transparent, jamais un tampon trop court
    return width, height, data
