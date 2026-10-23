# SPDX-License-Identifier: LGPL-2.1-or-later
"""Conversion entre la géométrie pure de ``core`` et les formes et placements de FreeCAD.

``Box``, ``Cylinder`` et ``Prism`` (repère local d'une pièce) deviennent des solides ``Part`` ; un
``Placement`` devient une :class:`RigidTransform`. Les erreurs du noyau géométrique (OCC) sont
converties en ``ValueError`` au message traduit : ``execute()`` ne laisse jamais passer
d'exception OCC (spécification J3, § 4.8).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.geometry import Box, Cylinder, Prism, RigidTransform, Solid
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.features.i18n import translated

__all__ = ["inserts_shape", "machined_shape", "rigid_transform", "solid_shape"]

_BOOLEAN_FAILED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinage impossible : le calcul de la forme a échoué ({reason})."
)
_INVALID_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinage impossible : la forme obtenue n'est pas un solide valide."
)


def rigid_transform(placement: Any) -> RigidTransform:
    """Transformation de ``core`` équivalente au ``Placement`` FreeCAD ``placement``."""
    values = placement.toMatrix().A
    return RigidTransform.from_matrix([values[row * 4 : row * 4 + 4] for row in range(4)])


def _vector(x: float, y: float, z: float) -> Any:
    return App.Vector(x, y, z)


def solid_shape(solid: Solid) -> Any:
    """Solide ``Part`` d'une boîte, d'un cylindre ou d'un prisme, dans le repère où ils sont
    exprimés."""
    if isinstance(solid, Box):
        low = solid.min
        return Part.makeBox(
            solid.size(0), solid.size(1), solid.size(2), _vector(low.x, low.y, low.z)
        )
    if isinstance(solid, Prism):
        return _prism_shape(solid)
    return _cylinder_shape(solid)


def _prism_shape(prism: Prism) -> Any:
    """Polygone fermé → face plane → extrusion."""
    points = [_vector(p.x, p.y, p.z) for p in prism.points]
    face = Part.Face(Part.makePolygon([*points, points[0]]))
    extrusion = prism.extrusion
    return face.extrude(_vector(extrusion.x, extrusion.y, extrusion.z))


def _cylinder_shape(cylinder: Cylinder) -> Any:
    base = cylinder.base
    unit = cylinder.axis.unit()
    return Part.makeCylinder(
        cylinder.radius,
        cylinder.height,
        _vector(base.x, base.y, base.z),
        _vector(unit.x, unit.y, unit.z),
    )


def machined_shape(
    dimensions: Dimensions,
    additions: Sequence[Solid],
    cuts: Sequence[Solid],
    trims: Sequence[Solid] = (),
) -> Any:
    """Boîte de la pièce moins ``trims`` (pièce raccourcie au contact, ADR 0016), plus
    ``additions``, moins ``cuts``, faces coplanaires fusionnées, dans le repère local de la
    pièce. ``ValueError`` traduite si OCC échoue ou si le résultat n'est pas un solide valide
    (jamais de forme partielle)."""
    shape = Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)
    try:
        if trims:
            shape = shape.cut([solid_shape(solid) for solid in trims])
        if additions:
            shape = shape.fuse([solid_shape(solid) for solid in additions])
        if cuts:
            shape = shape.cut([solid_shape(solid) for solid in cuts])
        shape = shape.removeSplitter()
    except Part.OCCError as error:
        raise ValueError(translated(_BOOLEAN_FAILED, {"reason": str(error)})) from error
    if shape.isNull() or not shape.Solids or not shape.isValid():
        raise ValueError(translated(_INVALID_SHAPE))
    return shape


def inserts_shape(inserts: Sequence[Solid]) -> Any:
    """Pièces rapportées (tourillons) réunies en un composé ; forme vide s'il n'y en a pas."""
    if not inserts:
        return Part.Shape()
    return Part.makeCompound([solid_shape(solid) for solid in inserts])
