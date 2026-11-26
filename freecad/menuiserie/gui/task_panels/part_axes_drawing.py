# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin du repère de la pièce en bois (D3), pur et dans le repère de la pièce : trièdre longueur L
(rouge), largeur l (vert), épaisseur e (bleu) à l'origine, et marque orange du sens du fil posée
sur la face du dessus : double flèche évidée, tige en tirets (le signe ↔ des plans de débit, le fil
n'a pas de sens). La marque suit le contour réel de la pièce (:mod:`.core.grain_band`), pour
qu'elle reste sur le bois d'une pièce convertie qui n'est pas une boîte. Aucun import de FreeCAD,
de Qt ni de pivy : :mod:`.part_axes` le pose dans la vue.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.grain_band import (
    MARK_LENGTH_RATIO,
    GrainBand,
    Loop,
    grain_band,
    mark_half_width,
    rectangle,
)
from freecad.menuiserie.gui.drag.drawing import AXIS_COLORS, HEAD_RATIO, Drawing, Solid, Stroke

__all__ = [
    "GRAIN_COLOR",
    "GRAIN_OUTLINE_COLOR",
    "axes_drawing",
    "dash_spans",
    "grain_axis",
    "grain_marking",
]

GRAIN_COLOR: Final = (1.0, 0.55, 0.0)  # fond de la double flèche
GRAIN_OUTLINE_COLOR: Final = (0.77, 0.37, 0.0)  # contour et tirets
GRAIN_FILL_TRANSPARENCY: Final = 0.7
AXIS_LENGTH_RATIO: Final = 0.3  # part de la plus grande cote
MIN_AXIS_MM: Final = 40.0
MAX_AXIS_MM: Final = 400.0
GRAIN_MARGIN: Final = 0.1  # marge à chaque bout de la bande de bois, part de sa longueur
# longueur maximale d'une pointe, part de la flèche
HEAD_LENGTH_RATIO: Final = 2 * MARK_LENGTH_RATIO
SHAFT_RATIO: Final = 0.3  # demi-largeur de la tige, part de celle d'une pointe
DASH_RATIO: Final = 0.55  # part de tiret dans chaque période de la tige
DASH_GAP: Final = 0.05  # écart entre une pointe et les tirets, part de la flèche
MIN_DASHES: Final = 3  # tirets de la tige, au moins
MAX_DASHES: Final = 12  # tirets de la tige, au plus
DASH_SPACING: Final = 6.0  # période minimale des tirets, en demi-largeurs de tige
AXIS_WIDTH: Final = 3.0  # épaisseur des traits du trièdre (pixels)
OUTLINE_WIDTH: Final = 3.0  # épaisseur du contour de la double flèche (pixels)
DASH_WIDTH: Final = 2.0  # épaisseur des tirets de la tige (pixels)
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


def dash_spans(start: float, end: float, shaft: float) -> tuple[tuple[float, float], ...]:
    """Tirets de la tige entre ``start`` et ``end`` (le long du fil), de ``MIN_DASHES`` à
    ``MAX_DASHES`` selon la place, chacun ``DASH_RATIO`` de sa période ; aucun tiret sans place
    ou sans tige."""
    if not (end > start and shaft > 0):  # aussi faux pour NaN
        return ()
    count = min(max(int((end - start) / (DASH_SPACING * shaft)), MIN_DASHES), MAX_DASHES)
    period = (end - start) / count
    return tuple((start + k * period, start + (k + DASH_RATIO) * period) for k in range(count))


def grain_marking(band: GrainBand, axis: int, height: float) -> tuple[Solid, Stroke, Stroke]:
    """Double flèche du fil sur la bande de bois ``band`` (axe du fil ``axis``), à la hauteur
    ``height`` : fond orange translucide (deux pointes et la tige, polygones convexes), contour
    fermé, et tirets au milieu de la tige."""
    margin = GRAIN_MARGIN * band.length
    start, end = band.start + margin, band.end - margin
    length = end - start
    head = mark_half_width(length, band.width)
    head_length = min(HEAD_LENGTH_RATIO * length, 2.0 * head)
    shaft = SHAFT_RATIO * head
    mid = band.across

    def at(along: float, offset: float) -> Vec3:
        """Point du dessus à ``along`` sur le fil, décalé de ``offset`` du milieu de la bande."""
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
    dashes = tuple((at(a, 0.0), at(b, 0.0)) for a, b in dash_spans(left + gap, right - gap, shaft))
    return (
        fill,
        Stroke(GRAIN_OUTLINE_COLOR, OUTLINE_WIDTH, (contour,)),
        Stroke(GRAIN_OUTLINE_COLOR, DASH_WIDTH, dashes),
    )


def _drawable(band: GrainBand, height: float) -> bool:
    """Vrai si la double flèche se dessine : cotes finies, longueur et largeur assez grandes pour
    une tige non nulle (une bande minuscule ou un contour hostile donnent le trièdre seul)."""
    values = (band.start, band.end, band.across, band.width, height)
    return all(math.isfinite(value) for value in values) and min(band.length, band.width) > 1e-6


def axes_drawing(
    extents: Extents,
    grain: int | None = None,
    outline: Sequence[Loop] | None = None,
    *,
    axes: bool = True,
) -> Drawing:
    """Trièdre L / l / e à l'origine de la pièce (repère de la pièce), de la taille de ses cotes
    ``extents`` (bornée), et double flèche du fil le long de l'axe ``grain`` (0 ou 1), posée sur
    la face du dessus dans la plus longue bande de bois du contour ``outline`` (plan XY local,
    boucles : extérieure puis trous ; ``None`` ou vide : l'encombrement, pièce rectangulaire).
    ``axes`` faux : la flèche seule (pièce de bois, dont le panneau montre déjà ses axes)."""
    size = min(max(AXIS_LENGTH_RATIO * max(extents), MIN_AXIS_MM), MAX_AXIS_MM)
    origin = Vec3(0.0, 0.0, 0.0)
    shown = range(3) if axes else range(0)
    strokes = [Stroke(AXIS_COLORS[a], AXIS_WIDTH, _arrow(origin, a, size)) for a in shown]
    if grain is None or grain not in (0, 1) or not min(extents) > 0:  # NaN : faux
        return Drawing(tuple(strokes))
    band = grain_band(outline or rectangle(extents[0], extents[1]), grain)
    if band is None or not _drawable(band, extents[2]):
        return Drawing(tuple(strokes))
    fill, contour, dashes = grain_marking(band, grain, extents[2])
    return Drawing((*strokes, contour, dashes), solids=(fill,))
