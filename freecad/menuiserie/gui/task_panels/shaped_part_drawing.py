# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin du repère de la pièce en bois (D3), pur et dans le repère de la pièce : trièdre longueur L
(rouge), largeur l (vert), épaisseur e (bleu) à l'origine, et marque orange du sens du fil posée
sur la face du dessus : double flèche évidée, tige en tirets (le signe ↔ des plans de débit, le fil
n'a pas de sens). La marque suit le contour réel de la pièce (:mod:`.core.grain_band`), pour
qu'elle reste sur le bois d'une pièce convertie qui n'est pas une boîte. Aucun import de FreeCAD,
de Qt ni de pivy : :mod:`.shaped_part_axes` le pose dans la vue.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.grain_band import (
    MARK_LENGTH_RATIO,
    MARK_WIDTH_RATIO,
    GrainBand,
    Loop,
    grain_band,
    rectangle,
)
from freecad.menuiserie.gui.drag.geometry import AXIS_COLORS, HEAD_RATIO, Drawing, Solid, Stroke

__all__ = ["GRAIN_COLOR", "GRAIN_OUTLINE_COLOR", "axes_drawing", "grain_axis", "grain_marking"]

GRAIN_COLOR: Final = (1.0, 0.55, 0.0)  # fond de la double flèche
GRAIN_OUTLINE_COLOR: Final = (0.77, 0.37, 0.0)  # contour et tirets
GRAIN_FILL_TRANSPARENCY: Final = 0.7
AXIS_LENGTH_RATIO: Final = 0.3  # part de la plus grande cote
MIN_AXIS_MM: Final = 40.0
MAX_AXIS_MM: Final = 400.0
GRAIN_MARGIN: Final = 0.1  # marge à chaque bout de la bande de bois, part de sa longueur
HEAD_LENGTH_RATIO: Final = (
    2 * MARK_LENGTH_RATIO
)  # longueur maximale d'une pointe, part de la flèche
SHAFT_RATIO: Final = 0.3  # demi-largeur de la tige, part de celle d'une pointe
DASH_RATIO: Final = 0.55  # part de tiret dans chaque période de la tige
DASH_GAP: Final = 0.05  # écart entre une pointe et les tirets, part de la flèche
MIN_DASHES, MAX_DASHES = 3, 12
_GRAIN_AXES: Final = {"Length": 0, "Width": 1}  # sens du fil -> axe de la pièce
Extents = tuple[float, float, float]


def grain_axis(grain: str) -> int | None:
    """Axe de la pièce (0 = L, 1 = l) le long duquel court le fil, ``None`` sans fil."""
    return _GRAIN_AXES.get(grain)


def _along(origin: Vec3, axis: int, distance: float) -> Vec3:
    return origin.with_component(axis, origin.component(axis) + distance)


def _arrow(start: Vec3, axis: int, length: float) -> tuple[tuple[Vec3, ...], ...]:
    """Tige le long de ``axis`` et quatre barbes, dans les deux autres directions."""
    end = _along(start, axis, length)
    back = _along(end, axis, -HEAD_RATIO * length)
    barbs = [
        (end, _along(back, other, sign * HEAD_RATIO * length / 2))
        for other in range(3)
        if other != axis
        for sign in (1.0, -1.0)
    ]
    return ((start, end), *barbs)


def _on_top(axis: int, along: float, across: float, height: float) -> Vec3:
    """Point du dessus : ``along`` sur l'axe du fil ``axis``, ``across`` sur l'autre."""
    point = Vec3(0.0, 0.0, height).with_component(axis, along)
    return point.with_component(1 - axis, across)


def grain_marking(band: GrainBand, axis: int, height: float) -> tuple[Solid, Stroke, Stroke]:
    """Double flèche du fil sur la bande de bois ``band`` (axe du fil ``axis``), à la hauteur
    ``height`` : fond orange translucide (deux pointes et la tige, polygones convexes), contour
    fermé, et tirets au milieu de la tige."""
    margin = GRAIN_MARGIN * band.length
    start, end = band.start + margin, band.end - margin
    length = end - start
    head = min(MARK_WIDTH_RATIO * band.width, MARK_LENGTH_RATIO * length)
    head_length = min(HEAD_LENGTH_RATIO * length, 2.0 * head)
    shaft = SHAFT_RATIO * head
    mid = band.across

    def at(along: float, offset: float) -> Vec3:
        return _on_top(axis, along, mid + offset, height)

    left, right = start + head_length, end - head_length
    tip_a, tip_b = at(start, 0.0), at(end, 0.0)
    fill = Solid(
        GRAIN_COLOR,
        (
            (tip_a, at(left, -head), at(left, head)),
            (at(left, -shaft), at(right, -shaft), at(right, shaft), at(left, shaft)),
            (tip_b, at(right, head), at(right, -head)),
        ),
        GRAIN_FILL_TRANSPARENCY,
    )
    contour = (
        tip_a, at(left, -head), at(left, -shaft), at(right, -shaft), at(right, -head), tip_b,
        at(right, head), at(right, shaft), at(left, shaft), at(left, head), tip_a,
    )  # fmt: skip
    gap = DASH_GAP * length
    inner_start, inner_end = left + gap, right - gap
    count = min(max(int((inner_end - inner_start) / (6.0 * shaft)), MIN_DASHES), MAX_DASHES)
    period = (inner_end - inner_start) / count
    dashes = tuple(
        (at(inner_start + k * period, 0.0), at(inner_start + (k + DASH_RATIO) * period, 0.0))
        for k in range(count)
    )
    return (
        fill,
        Stroke(GRAIN_OUTLINE_COLOR, 3.0, (contour,)),
        Stroke(GRAIN_OUTLINE_COLOR, 2.0, dashes),
    )


def axes_drawing(
    extents: Extents, grain: int | None = None, outline: Sequence[Loop] | None = None
) -> Drawing:
    """Trièdre L / l / e à l'origine de la pièce (repère de la pièce), de la taille de ses cotes
    ``extents`` (bornée), et double flèche du fil le long de l'axe ``grain`` (0 ou 1), posée sur
    la face du dessus dans la plus longue bande de bois du contour ``outline`` (plan XY local,
    boucles : extérieure puis trous ; ``None`` : l'encombrement, pièce rectangulaire)."""
    size = min(max(AXIS_LENGTH_RATIO * max(extents), MIN_AXIS_MM), MAX_AXIS_MM)
    origin = Vec3(0.0, 0.0, 0.0)
    strokes = [Stroke(AXIS_COLORS[axis], 3.0, _arrow(origin, axis, size)) for axis in range(3)]
    if grain is None or grain not in (0, 1):
        return Drawing(tuple(strokes))
    band = grain_band(outline or rectangle(extents[0], extents[1]), grain)
    if band is None:
        return Drawing(tuple(strokes))
    fill, contour, dashes = grain_marking(band, grain, extents[2])
    return Drawing((*strokes, contour, dashes), solids=(fill,))
