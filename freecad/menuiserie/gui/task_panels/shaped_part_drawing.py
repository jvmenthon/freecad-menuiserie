# SPDX-License-Identifier: LGPL-2.1-or-later
"""Dessin du repère de la pièce en bois (D3), pur et dans le repère de la pièce : trièdre longueur L
(rouge), largeur l (vert), épaisseur e (bleu) à l'origine, et flèche orange du fil sur la face du
dessus. Aucun import de FreeCAD, de Qt ni de pivy : :mod:`.shaped_part_axes` le pose dans la vue.
"""

from __future__ import annotations

from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.gui.drag.geometry import AXIS_COLORS, HEAD_RATIO, Drawing, Stroke

__all__ = ["GRAIN_COLOR", "axes_drawing", "grain_axis"]

GRAIN_COLOR: Final = (1.0, 0.55, 0.0)
AXIS_LENGTH_RATIO: Final = 0.3  # part de la plus grande cote
MIN_AXIS_MM: Final = 40.0
MAX_AXIS_MM: Final = 400.0
GRAIN_SPAN: Final = (0.1, 0.9)  # début et fin de la flèche du fil, part de la longueur
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


def axes_drawing(extents: Extents, grain: int | None = None) -> Drawing:
    """Trièdre L / l / e à l'origine de la pièce (repère de la pièce), de la taille de ses cotes
    ``extents`` (bornée), et flèche du fil le long de l'axe ``grain`` (0 ou 1) sur la face du
    dessus, au milieu de la largeur ou de la longueur."""
    size = min(max(AXIS_LENGTH_RATIO * max(extents), MIN_AXIS_MM), MAX_AXIS_MM)
    origin = Vec3(0.0, 0.0, 0.0)
    strokes = [Stroke(AXIS_COLORS[axis], 3.0, _arrow(origin, axis, size)) for axis in range(3)]
    if grain in (0, 1):
        across = 1 - grain
        start = origin.with_component(grain, GRAIN_SPAN[0] * extents[grain])
        start = start.with_component(across, extents[across] / 2).with_component(2, extents[2])
        length = (GRAIN_SPAN[1] - GRAIN_SPAN[0]) * extents[grain]
        strokes.append(Stroke(GRAIN_COLOR, 4.0, _arrow(start, grain, length)))
    return Drawing(tuple(strokes))
