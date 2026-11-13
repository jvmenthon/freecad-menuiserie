# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ce que la face du plan de l'ouvrage cote en détail (retour de jv du 2026-11-13) : où commence
et finit chaque pièce en largeur et en hauteur, et l'angle des pièces en biais.

La face regarde l'ouvrage de devant (direction -Y) : la largeur de la feuille suit X, sa hauteur
suit Z. Les points viennent de l'encombrement global de chaque objet dessiné ; l'angle d'une
pièce de bois est celui de sa longueur (ou de sa largeur si elle se voit mieux) avec
l'horizontale de la feuille.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import FreeCAD as App
import Part

from freecad.menuiserie.core.drawing import slant_angle
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.machined_part import blank_of, is_machined_part
from freecad.menuiserie.features.shaped_part import is_timber

__all__ = ["FrontDetails", "front_details", "global_shape"]


@dataclass(frozen=True)
class FrontDetails:
    """Points de la chaîne de cotes en largeur (X) et en hauteur (Z), en mm réels, et angles des
    pièces en biais : (angle en degrés, centre global de la pièce)."""

    xs: tuple[float, ...]
    zs: tuple[float, ...]
    angles: tuple[tuple[float, Any], ...]


def global_shape(obj: DocumentObject) -> Any:
    """Forme de ``obj`` (copie) placée dans le repère global du document, conteneurs compris."""
    shape = Part.getShape(obj)
    if not shape.isNull():
        outer = obj.getGlobalPlacement().multiply(obj.Placement.inverse())
        shape.Placement = outer.multiply(shape.Placement)
    return shape


def _timber(obj: DocumentObject) -> DocumentObject | None:
    """Pièce de bois brute d'un objet dessiné (la pièce usinée en donne sa brute)."""
    if is_machined_part(obj):
        return blank_of(obj)
    return obj if is_timber(obj) else None


def _angle(blank: DocumentObject) -> float | None:
    """Angle avec l'horizontale de la face de l'axe de ``blank`` qui s'y voit le mieux."""
    rotation = blank.getGlobalPlacement().Rotation
    axes = [rotation.multVec(App.Vector(1, 0, 0)), rotation.multVec(App.Vector(0, 1, 0))]
    best = max(axes, key=lambda axis: axis.x**2 + axis.z**2)
    return slant_angle(best.x, best.z)


def front_details(sources: Sequence[DocumentObject]) -> FrontDetails:
    """Points des chaînes de cotes et angles de la face pour les objets dessinés ``sources``."""
    xs: list[float] = []
    zs: list[float] = []
    angles: list[tuple[float, Any]] = []
    for obj in sources:
        shape = global_shape(obj)
        if shape.isNull():
            continue
        box = shape.BoundBox
        xs += [box.XMin, box.XMax]
        zs += [box.ZMin, box.ZMax]
        blank = _timber(obj)
        angle = _angle(blank) if blank is not None else None
        if angle is not None:
            angles.append((angle, box.Center))
    return FrontDetails(tuple(xs), tuple(zs), tuple(angles))
