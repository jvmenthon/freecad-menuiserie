# SPDX-License-Identifier: LGPL-2.1-or-later
"""Image des étiquettes de cote (ADR 0068, maquette K « une étiquette par cote »).

Une étiquette est une pastille arrondie blanche bordée de la couleur de l'axe : à gauche le nom
court de la cote (« Long. », « Larg. », « Ép. »…) en blanc sur la couleur de l'axe, à droite sa
valeur ; une cote figée est grise, avec un cadenas. Elle est peinte par Qt avec lissage, ombre
et halo de survol, puis posée telle quelle dans la vue (``overlay.py``, ``SoImage`` : taille fixe
à l'écran). Ses largeurs viennent de :func:`badge_width_px`, la mesure de la saisie. Le rond du
chaque face (:func:`knob_pixels`) est peint de même, à la couleur de l'étiquette,
avec une petite double flèche blanche dans la direction de l'axe à l'écran. Les
images sont gardées (mêmes arguments : même image) ; :func:`clear_badge_cache` les oublie.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Final

from PySide import QtCore, QtGui

from freecad.menuiserie.gui.drag.badge_place import BADGE_H_PX, LOCK_PX, badge_width_px
from freecad.menuiserie.gui.drag.drawing import AXIS_COLORS, LOCKED_COLOR, BadgeState, Color

__all__ = ["badge_pixels", "clear_badge_cache", "knob_pixels"]

MARGIN_PX: Final = 6.0  # marge autour de la pastille : ombre et halo
NAME_PX: Final = 11.5  # taille du nom
VALUE_PX: Final = 13.0  # taille de la valeur
EDGE_PX: Final = 1.4  # bord de la pastille
HOT_EDGE_PX: Final = 2.2  # bord d'une pastille survolée
SHADOW_ALPHA: Final = 55  # ombre portée, décalée vers le bas
SHADOW_DROP_PX: Final = 1.5
HALO_RINGS: Final = ((3, 40), (2, 70), (1, 110))  # halo de survol : couronne et opacité
HALO_STEP_PX: Final = 1.6  # largeur d'une couronne du halo
LOCK_SCALE: Final = 0.75
LOCK_PEN: Final = 2.2
VALUE_INK: Final = "#1d2733"
LOCKED_INK: Final = "#4a5563"
_CACHE: Final = 256
KNOB_PX: Final = 16.0  # diamètre du rond d'une face, survolé ensuite
KNOB_HOT_PX: Final = 20.0
KNOB_ARROW: Final = 0.32  # demi-longueur de la flèche du rond, part du diamètre
KNOB_HEAD: Final = 0.16  # barbes de la flèche, part du diamètre
KNOB_ARROW_PEN: Final = 1.6
KNOB_RING_PX: Final = 1.6  # liseré blanc du rond
MAX_SIDE_PX: Final = 2048  # côté d'une étiquette au plus (SbVec2s : 16 bits)


def _font(size: float, scale: float) -> QtGui.QFont:
    font = QtGui.QFont()
    font.setPixelSize(max(1, round(size * scale)))
    font.setBold(True)
    return font


def _color(rgb: Color) -> QtGui.QColor:
    return QtGui.QColor.fromRgbF(*rgb)


def _axis_color(axis: int, locked: bool) -> QtGui.QColor:
    """Couleur d'une cote : celle de son axe, grise si elle est figée (étiquette et rond)."""
    return _color(LOCKED_COLOR if locked else AXIS_COLORS[axis % 3])


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


def _halo(painter: QtGui.QPainter, body: QtCore.QRectF, glow: QtGui.QColor, scale: float) -> None:
    """Halo de survol : couronnes de plus en plus claires autour de la pastille ``body``."""
    radius = body.height() / 2
    for step, alpha in HALO_RINGS:
        color = QtGui.QColor(glow)
        color.setAlpha(alpha)
        painter.setBrush(color)
        grow = step * HALO_STEP_PX * scale
        halo = body.adjusted(-grow, -grow, grow, grow)
        painter.drawRoundedRect(halo, radius + grow, radius + grow)


def _body(
    painter: QtGui.QPainter, body: QtCore.QRectF, name_w: float, color: QtGui.QColor, hot: bool
) -> None:
    """Ombre portée, pastille blanche bordée de ``color``, puis partie du nom (largeur
    ``name_w``) remplie de ``color``."""
    radius = body.height() / 2
    scale = body.height() / BADGE_H_PX
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor(0, 0, 0, SHADOW_ALPHA))
    painter.drawRoundedRect(body.translated(0.0, SHADOW_DROP_PX * scale), radius, radius)
    painter.setBrush(QtGui.QColor("#ffffff"))
    painter.drawRoundedRect(body, radius, radius)
    name = QtGui.QPainterPath()
    name.addRoundedRect(body, radius, radius)
    clip = QtGui.QPainterPath()
    clip.addRect(QtCore.QRectF(body.left(), body.top(), name_w, body.height()))
    painter.setBrush(color)
    painter.drawPath(name.intersected(clip))
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.setPen(QtGui.QPen(color, (HOT_EDGE_PX if hot else EDGE_PX) * scale))
    painter.drawRoundedRect(body, radius, radius)


def _texts(  # pylint: disable=too-many-arguments
    painter: QtGui.QPainter,
    body: QtCore.QRectF,
    name_w: float,
    name: str,
    text: str,
    locked: bool,
) -> None:
    """Nom en blanc sur la partie colorée, valeur à droite, cadenas au bout si la cote est
    figée."""
    scale = body.height() / BADGE_H_PX
    painter.setFont(_font(NAME_PX, scale))
    painter.setPen(QtGui.QColor("#ffffff"))
    name_area = QtCore.QRectF(body.left(), body.top(), name_w, body.height())
    painter.drawText(name_area, QtCore.Qt.AlignCenter, name)
    ink = QtGui.QColor(LOCKED_INK if locked else VALUE_INK)
    lock_w = LOCK_PX * scale if locked else 0.0
    painter.setFont(_font(VALUE_PX, scale))
    painter.setPen(ink)
    left = body.left() + name_w
    value_area = QtCore.QRectF(left, body.top(), body.right() - left - lock_w, body.height())
    painter.drawText(value_area, QtCore.Qt.AlignCenter, text)
    if locked:
        painter.save()
        painter.translate(body.right() - lock_w * 0.75, body.center().y() - 1.0 * scale)
        _lock(painter, ink, scale)
        painter.restore()


def _paint(name: str, text: str, state: BadgeState, axis: int, scale: float) -> QtGui.QImage:
    locked = state.locked
    hot = state in (BadgeState.HOVER, BadgeState.LOCKED_HOVER)
    name_w, width = (w * scale for w in badge_width_px(name, text, locked))
    height = BADGE_H_PX * scale
    margin = MARGIN_PX * scale
    if max(width, height) + 2 * margin > MAX_SIDE_PX:  # jamais d'image démesurée
        return QtGui.QImage()
    image = QtGui.QImage(
        math.ceil(width + 2 * margin),
        math.ceil(height + 2 * margin),
        QtGui.QImage.Format_ARGB32_Premultiplied,
    )
    image.fill(QtCore.Qt.transparent)
    color = _axis_color(axis, locked)
    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        body = QtCore.QRectF(margin, margin, width, height)
        painter.setPen(QtCore.Qt.NoPen)
        if hot:
            _halo(painter, body, color, scale)
        _body(painter, body, name_w, color, hot)
        _texts(painter, body, name_w, name, text, locked)
    finally:
        painter.end()
    return image


def _knob_arrow(painter: QtGui.QPainter, body: QtCore.QRectF, angle: float, scale: float) -> None:
    """Double flèche blanche au centre du rond ``body``, dans la direction ``angle`` (degrés,
    sens trigonométrique à l'écran ; l'image Qt a son y vers le bas, d'où le signe)."""
    half = body.width() * KNOB_ARROW
    head = body.width() * KNOB_HEAD
    painter.save()
    painter.translate(body.center())
    painter.rotate(-angle)
    pen = QtGui.QPen(QtGui.QColor("#ffffff"), KNOB_ARROW_PEN * scale)
    pen.setCapStyle(QtCore.Qt.RoundCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(QtCore.Qt.NoBrush)
    painter.drawLine(QtCore.QPointF(-half, 0.0), QtCore.QPointF(half, 0.0))
    for tip in (half, -half):
        back = tip - head if tip > 0 else tip + head
        barbs = QtGui.QPolygonF(
            [QtCore.QPointF(back, -head), QtCore.QPointF(tip, 0.0), QtCore.QPointF(back, head)]
        )
        painter.drawPolyline(barbs)
    painter.restore()


def _paint_knob(
    axis: int, locked: bool, hot: bool, scale: float, angle: float | None
) -> QtGui.QImage:
    """Rond plein à la couleur de l'étiquette, liseré blanc, ombre, double flèche de l'axe
    (``angle``, aucune si ``None``) ; halo s'il est survolé."""
    diameter = (KNOB_HOT_PX if hot else KNOB_PX) * scale
    margin = MARGIN_PX * scale
    side = math.ceil(diameter + 2 * margin)
    if side > MAX_SIDE_PX:  # jamais d'image démesurée
        return QtGui.QImage()
    image = QtGui.QImage(side, side, QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    color = _axis_color(axis, locked)
    offset = (side - diameter) / 2
    body = QtCore.QRectF(offset, offset, diameter, diameter)
    painter = QtGui.QPainter(image)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        if hot:
            _halo(painter, body, color, scale)
        painter.setBrush(QtGui.QColor(0, 0, 0, SHADOW_ALPHA))
        painter.drawEllipse(body.translated(0.0, SHADOW_DROP_PX * scale))
        painter.setBrush(QtGui.QColor("#ffffff"))
        painter.drawEllipse(body)
        ring = KNOB_RING_PX * scale
        painter.setBrush(color)
        painter.drawEllipse(body.adjusted(ring, ring, -ring, -ring))
        if angle is not None:
            _knob_arrow(painter, body, angle, scale)
    finally:
        painter.end()
    return image


def _coin_pixels(image: QtGui.QImage) -> tuple[int, int, bytes]:
    """Largeur, hauteur et pixels RVBA de ``image``, lignes du bas vers le haut (l'ordre de
    Coin) ; un pixel transparent si l'image est ratée, jamais un tampon trop court."""
    image = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    flip = getattr(image, "flipped", None)  # Qt ≥ 6.9 ; ``mirrored`` avant
    image = flip(QtCore.Qt.Vertical) if flip is not None else image.mirrored(False, True)
    width, height = image.width(), image.height()
    data = bytes(image.constBits())[: width * height * 4]
    if (
        not (0 < width <= MAX_SIDE_PX and 0 < height <= MAX_SIDE_PX)
        or len(data) != 4 * width * height
    ):
        return 1, 1, bytes(4)
    return width, height, data


def clear_badge_cache() -> None:
    """Oublie les images gardées (au retrait du glissement : police ou thème peuvent changer)."""
    badge_pixels.cache_clear()
    knob_pixels.cache_clear()


@lru_cache(maxsize=_CACHE)
def knob_pixels(
    axis: int, locked: bool, hot: bool, scale: float, angle: float | None = None
) -> tuple[int, int, bytes]:
    """Largeur, hauteur et pixels RVBA (ordre de Coin) du rond d'une face de poignée : couleur de
    l'axe ``axis`` (celle de son étiquette), gris si ``locked``, plus gros avec un halo si
    ``hot``, à l'échelle ``scale``, double flèche dans la direction ``angle`` (degrés à
    l'écran ; aucune si ``None`` ou non fini)."""
    if angle is not None and not math.isfinite(angle):
        angle = None
    if locked and axis != 0:  # rond gris : le même pour tous les axes
        return knob_pixels(0, locked, hot, scale, angle)
    return _coin_pixels(_paint_knob(axis, locked, hot, scale, angle))


@lru_cache(maxsize=_CACHE)
def badge_pixels(
    name: str, text: str, state: BadgeState, axis: int, scale: float
) -> tuple[int, int, bytes]:
    """Largeur, hauteur et pixels RVBA (lignes du bas vers le haut, l'ordre de Coin) de
    l'étiquette de la cote ``name`` de valeur ``text``, dans l'état ``state``
    (:class:`BadgeState`), à la couleur de l'axe ``axis``, à l'échelle ``scale`` (rapport de
    pixels de l'écran)."""
    return _coin_pixels(_paint(name, text, state, axis, scale))
