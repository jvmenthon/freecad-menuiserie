# SPDX-License-Identifier: LGPL-2.1-or-later
"""Taille initiale d'une nouvelle pièce limitée par la collision avec les autres pièces.

À l'ouverture du panneau de création, les cotes par défaut (ou étirées par l'accrochage) sont
ramenées au jeu libre avant les autres pièces de bois du document (:func:`limit_initial_size`) ;
ensuite le menuisier saisit ce qu'il veut. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from typing import Any

import Part

from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import limit_dimensions, snap
from freecad.menuiserie.features.freecad_types import DocumentObject, has_expression
from freecad.menuiserie.features.placement import SnapSession, snap_part, to_placement
from freecad.menuiserie.features.shaped_part import is_timber
from freecad.menuiserie.features.snap_geometry import ERRORS, global_shape
from freecad.menuiserie.features.snap_targets import OVERLAP_MM3
from freecad.menuiserie.features.wood_part import dimensions_of

__all__ = ["limit_initial_size"]


def limit_initial_size(obj: DocumentObject, session: SnapSession) -> bool:
    """Ramène les cotes de la nouvelle pièce ``obj`` au jeu libre avant les autres pièces de bois
    (aucune cote écrite si elle est pilotée par une expression), puis la repose. Vrai si une cote
    a changé."""
    others = _other_shapes(obj)
    if not others:
        return False
    current = dimensions_of(obj)

    def is_free(dimensions: Dimensions) -> bool:
        result = snap(
            dimensions,
            session.orientation,
            session.targets,
            stretch=False,
            is_free=session.free,
        )
        box = Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)
        box.Placement = to_placement(result.placement)
        return not any(_overlaps(box, shape) for shape in others)

    limited = limit_dimensions(current, is_free)
    if limited == current:
        return False
    changed = False
    for prop in ("Length", "Width", "Thickness"):
        value = getattr(limited, prop.lower())
        if not has_expression(obj, prop) and getattr(obj, prop).Value != value:
            setattr(obj, prop, value)
            changed = True
    if changed:
        snap_part(obj, session)
    return changed


def _other_shapes(obj: DocumentObject) -> list[Any]:
    """Formes (repère du document) des autres pièces de bois du document."""
    shapes = []
    for other in obj.Document.Objects:
        if other is not obj and is_timber(other) and not other.Shape.isNull():
            shapes.append(global_shape(other))
    return shapes


def _overlaps(box: Any, shape: Any) -> bool:
    """Vrai si ``box`` et ``shape`` ont un volume commun d'au moins ``OVERLAP_MM3``."""
    if not box.BoundBox.intersect(shape.BoundBox):
        return False
    try:
        return bool(box.common(shape).Volume >= OVERLAP_MM3)
    except ERRORS:
        return False
