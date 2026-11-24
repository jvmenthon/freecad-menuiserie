# SPDX-License-Identifier: LGPL-2.1-or-later
"""Image des étiquettes de poignée (ADR 0068, maquette I « étiquette de cote »).

Une étiquette est une pastille arrondie : double flèche dans l'axe de la cote (cadenas pour une
poignée impossible) puis la valeur de la cote. Elle est peinte par Qt avec lissage, ombre et halo
de survol, puis posée telle quelle dans la vue (``overlay.py``, ``SoImage`` : taille fixe à
l'écran). Les images sont gardées (mêmes texte, état, angle et échelle : même image) ;
:func:`clear_badge_cache` les oublie.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.gui.drag.drawing import BADGE_H_PX, BADGE_W_PX, BadgeState

__all__ = ["badge_pixels", "clear_badge_cache"]

MARGIN_PX: Final = 6.0  # marge autour de la pastille : ombre et halo
ICON_X_PX: Final = 14.0  # centre de l'icône depuis le bord gauche de la pastille
TEXT_GAP_PX: Final = 10.0  # du centre de l'icône au début de la zone du texte
TEXT_RIGHT_PX: Final = 6.0  # retrait du texte avant le bord droit
MIN_TEXT_PAD_PX: Final = 21.0  # place laissée à droite de l'icône en plus du texte
TEXT_PX: Final = 13  # taille du texte de la cote
EDGE_PX: Final = 1.2  # bord de la pastille
SHADOW_ALPHA: Final = 55  # ombre portée, décalée vers le bas
SHADOW_DROP_PX: Final = 1.5
HALO_RINGS: Final = ((3, 40), (2, 70), (1, 110))  # halo de survol : couronne et opacité
HALO_STEP_PX: Final = 1.6  # largeur d'une couronne du halo
ARROW_SCALE: Final = 0.85  # icônes dessinées sur une grille d'environ 20 pixels
ARROW_PEN: Final = 2.4
LOCK_SCALE: Final = 0.75
LOCK_PEN: Final = 2.2
_CACHE: Final = 128
MAX_SIDE_PX: Final = 2048  # côté d'une étiquette au plus (SbVec2s : 16 bits)


@dataclass(frozen=True)
class _Look:
    """Couleurs d'un état : fond, bord, texte et icône, halo (``None`` : aucun)."""

    fill: str
    edge: str
    ink: str
    glow: str | None = None


_LOOKS: Final = {
    BadgeState.NORMAL: _Look("#ff8a00", "#b04a00", "#ffffff"),
    BadgeState.HOVER: _Look("#ffc400", "#b88600", "#3d2a00", "#ffc400"),
    BadgeState.LOCKED: _Look("#f3f5f7", "#9aa2ab", "#6d7680"),
    BadgeState.LOCKED_HOVER: _Look("#ffffff", "#6d7680", "#4a5563", "#9aa2ab"),
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
    painter.scale(scale * ARROW_SCALE, scale * ARROW_SCALE)
    pen = QtGui.QPen(color, ARROW_PEN)
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
    painter.scale(scale * LOCK_SCALE, scale * LOCK_SCALE)
    pen = QtGui.QPen(color, LOCK_PEN)
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


def _halo(painter: QtGui.QPainter, body: QtCore.QRectF, glow: str, scale: float) -> None:
    """Halo de survol : couronnes de plus en plus claires autour de la pastille ``body``."""
    radius = body.height() / 2
    for step, alpha in HALO_RINGS:
        color = QtGui.QColor(glow)
        color.setAlpha(alpha)
        painter.setBrush(color)
        grow = step * HALO_STEP_PX * scale
        halo = body.adjusted(-grow, -grow, grow, grow)
        painter.drawRoundedRect(halo, radius + grow, radius + grow)


def _body(painter: QtGui.QPainter, body: QtCore.QRectF, look: _Look, scale: float) -> None:
    """Ombre portée puis pastille ``body`` (fond et bord de ``look``)."""
    radius = body.height() / 2
    painter.setBrush(QtGui.QColor(0, 0, 0, SHADOW_ALPHA))
    painter.drawRoundedRect(body.translated(0.0, SHADOW_DROP_PX * scale), radius, radius)
    painter.setBrush(QtGui.QColor(look.fill))
    painter.setPen(QtGui.QPen(QtGui.QColor(look.edge), EDGE_PX * scale))
    painter.drawRoundedRect(body, radius, radius)


def _content(  # pylint: disable=too-many-arguments
    painter: QtGui.QPainter,
    body: QtCore.QRectF,
    text: str,
    state: BadgeState,
    angle: float,
    scale: float,
) -> None:
    """Icône (cadenas ou double flèche tournée de ``angle``) puis texte de la cote."""
    ink = QtGui.QColor(_LOOKS[state].ink)
    painter.save()
    painter.translate(body.left() + ICON_X_PX * scale, body.center().y())
    if state.locked:
        _lock(painter, ink, scale)
    else:
        _arrow(painter, ink, angle, scale)
    painter.restore()
    painter.setFont(_font(scale))
    painter.setPen(ink)
    left = body.left() + (ICON_X_PX + TEXT_GAP_PX) * scale
    area = QtCore.QRectF(
        left, body.top(), body.right() - left - TEXT_RIGHT_PX * scale, body.height()
    )
    painter.drawText(area, QtCore.Qt.AlignCenter, text)


def _paint(text: str, state: BadgeState, angle: float, scale: float) -> QtGui.QImage:
    look = _LOOKS[state]
    text_w = QtGui.QFontMetricsF(_font(scale)).horizontalAdvance(text)
    height = BADGE_H_PX * scale
    width = max(BADGE_W_PX * scale, (ICON_X_PX + MIN_TEXT_PAD_PX) * scale + text_w)
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
        painter.setPen(QtCore.Qt.NoPen)
        if look.glow is not None:
            _halo(painter, body, look.glow, scale)
        _body(painter, body, look, scale)
        _content(painter, body, text, state, angle, scale)
    finally:
        painter.end()
    return image


def clear_badge_cache() -> None:
    """Oublie les images gardées (au retrait du glissement : police ou thème peuvent changer)."""
    badge_pixels.cache_clear()


@lru_cache(maxsize=_CACHE)
def badge_pixels(
    text: str, state: BadgeState, angle: float, scale: float
) -> tuple[int, int, bytes]:
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
