# SPDX-License-Identifier: LGPL-2.1-or-later
"""Solide ``Part`` d'une section balayée (profil d'arête, ADR 0029).

La section de ``core`` (segments et arcs d'ellipse) devient une face plane, puis le solide balayé
le long de l'arête. Un arc circulaire est un arc de cercle exact ; un arc elliptique (quart de rond
aux deux cotes différentes, doucine) est interpolé par une B-spline de 33 points (écart de l'ordre
du micromètre).
"""

from __future__ import annotations

from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core._extrusion import Arc, Extrusion, Point2, Segment
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.features.i18n import translated

__all__ = ["extrusion_shape"]

_SPLINE_POINTS: Final = 33
_INVALID_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Profil impossible : la forme obtenue n'est pas un solide valide."
)


def _vector(extrusion: Extrusion, point: Point2) -> Any:
    placed = extrusion.point(point[0], point[1])
    return App.Vector(placed.x, placed.y, placed.z)


def _edge(extrusion: Extrusion, element: Segment | Arc) -> Any:
    if isinstance(element, Segment):
        return Part.LineSegment(
            _vector(extrusion, element.start), _vector(extrusion, element.end)
        ).toShape()
    if element.rx == element.ry:
        return Part.Arc(
            _vector(extrusion, element.start),
            _vector(extrusion, element.middle),
            _vector(extrusion, element.end),
        ).toShape()
    step = (element.last - element.first) / (_SPLINE_POINTS - 1)
    points = [
        _vector(extrusion, element.point(element.first + step * i)) for i in range(_SPLINE_POINTS)
    ]
    curve = Part.BSplineCurve()
    curve.interpolate(points)
    return curve.toShape()


def extrusion_shape(extrusion: Extrusion) -> Any:
    """Solide balayé de ``extrusion``, dans le repère où elle est exprimée (``ValueError`` traduite
    si le noyau géométrique ne donne pas un solide valide)."""
    edges = [_edge(extrusion, element) for element in extrusion.section.elements]
    direction = extrusion.direction.scaled(extrusion.length)
    try:
        face = Part.Face(Part.Wire(edges))
        shape = face.extrude(App.Vector(direction.x, direction.y, direction.z))
    except Part.OCCError as error:
        raise ValueError(translated(_INVALID_SHAPE)) from error
    if shape.isNull() or not shape.Solids or not shape.isValid():
        raise ValueError(translated(_INVALID_SHAPE))
    return shape
