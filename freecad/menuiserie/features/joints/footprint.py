# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contour réel d'une pièce en bois, vu par ``core`` (pieds sous une pièce dessinée)."""

from __future__ import annotations

from typing import Final

import FreeCAD as App

from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.shaped_part import base_shape_of, is_shaped_part

__all__ = ["footprint_of"]

_OUTLINE_DEFLECTION_MM: Final = 0.5  # écart maximal du contour discrétisé à la courbe réelle
_OUTLINE_FILL: Final = 0.999  # contour remplissant l'encombrement : pièce rectangulaire


def footprint_of(obj: DocumentObject) -> tuple[tuple[tuple[float, float], ...], ...] | None:
    """Contour réel de la pièce dans son plan XY local (boucles : extérieure puis trous), coupe à
    mi-épaisseur de sa forme de base ; ``None`` pour une pièce rectangulaire ou si la coupe ne
    donne rien d'exploitable (la pièce est alors vue comme son encombrement)."""
    if not is_shaped_part(obj):
        return None
    try:
        shape = base_shape_of(obj)
        wires = shape.slice(App.Vector(0.0, 0.0, 1.0), obj.Thickness.Value / 2)
        loops = tuple(
            tuple(
                (point.x, point.y)
                for point in wire.discretize(Deflection=_OUTLINE_DEFLECTION_MM)[:-1]
            )
            for wire in wires
        )
    except (RuntimeError, ValueError, AttributeError):
        return None
    if not loops or any(len(loop) < 3 for loop in loops):
        return None
    loops = tuple(sorted(loops, key=lambda loop: -abs(_loop_area(loop))))
    area = abs(_loop_area(loops[0])) - sum(abs(_loop_area(loop)) for loop in loops[1:])
    if len(loops) == 1 and area >= _OUTLINE_FILL * obj.Length.Value * obj.Width.Value:
        return None
    return loops


def _loop_area(loop: tuple[tuple[float, float], ...]) -> float:
    """Aire algébrique d'une boucle (formule du lacet)."""
    return (
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(loop, loop[1:] + loop[:1], strict=True)) / 2
    )
