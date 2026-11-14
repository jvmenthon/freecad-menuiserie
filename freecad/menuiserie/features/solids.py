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

from freecad.menuiserie.core._polyhedron import PlanSolid, Polyhedron, SlantedCylinder
from freecad.menuiserie.core.geometry import Box, Cylinder, Prism, RigidTransform
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.vectors import norm
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "box_shape",
    "grown_shape",
    "inserts_shape",
    "machined_shape",
    "rigid_transform",
    "solid_shape",
]

_BOOLEAN_FAILED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinage impossible : le calcul de la forme a échoué ({reason})."
)
_OFFSET_TOLERANCE: Final = 1e-6
_SHARP_JOIN: Final = 2  # jonction « intersection » de ``makeOffsetShape`` : angles vifs
_INVALID_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinage impossible : la forme obtenue n'est pas un solide valide."
)
# Étiquettes (``Tag``) des formes d'entrée de l'usinage (ADR 0056) : FreeCAD 1.1 ne tient la carte
# des éléments d'une booléenne que si ses entrées sont étiquetées. Plage au-delà des identifiants
# d'objets d'un document (jamais de collision avec l'historique d'une forme dessinée), sous 2³¹
# (``long`` de 32 bits sous Windows). Étiquettes fixées par la position : deux usinages égaux
# donnent la même forme et les mêmes noms (cache des formes usinées) ; une plage par groupe
# (parties retirées, ajouts, enlèvements), pour qu'un ajout ne renomme pas les enlèvements.
_BASE_TAG: Final = 1 << 30
_GROUP_TAGS: Final = 1 << 20  # au plus 2^20 - 1 solides par groupe : 2^30 + 3 * 2^20 < 2^31
_TOO_MANY_TOOLS: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Usinage impossible : trop d'usinages d'un même genre sur la pièce ({count})."
)


def rigid_transform(placement: Any) -> RigidTransform:
    """Transformation de ``core`` équivalente au ``Placement`` FreeCAD ``placement``."""
    values = placement.toMatrix().A
    return RigidTransform.from_matrix([values[row * 4 : row * 4 + 4] for row in range(4)])


def _vector(x: float, y: float, z: float) -> Any:
    return App.Vector(x, y, z)


def solid_shape(solid: PlanSolid) -> Any:
    """Solide ``Part`` d'une boîte, d'un cylindre, d'un prisme ou d'un polyèdre, dans le repère
    où ils sont exprimés."""
    if isinstance(solid, Polyhedron):
        return _polyhedron_shape(solid)
    if isinstance(solid, Box):
        low = solid.min
        return Part.makeBox(
            solid.size(0), solid.size(1), solid.size(2), _vector(low.x, low.y, low.z)
        )
    if isinstance(solid, Prism):
        return _prism_shape(solid)
    if isinstance(solid, SlantedCylinder):
        return Part.makeCylinder(
            solid.radius,
            solid.height,
            _vector(solid.base.x, solid.base.y, solid.base.z),
            _vector(solid.direction.x, solid.direction.y, solid.direction.z),
        )
    return _cylinder_shape(solid)


def _matrix(transform: RigidTransform) -> Any:
    """Matrice FreeCAD équivalente à une transformation rigide de ``core``."""
    rows = transform.rotation
    shift = transform.translation
    return App.Matrix(
        rows[0][0], rows[0][1], rows[0][2], shift.x,
        rows[1][0], rows[1][1], rows[1][2], shift.y,
        rows[2][0], rows[2][1], rows[2][2], shift.z,
        0.0, 0.0, 0.0, 1.0,
    )  # fmt: skip


def _polyhedron_shape(polyhedron: Polyhedron) -> Any:
    """Boîte posée dans son repère, puis amputée de chaque demi-espace retiré (booléennes de
    faces planes : robustes et sans couture, spécification AB, § 4.5). Résultat contrôlé comme
    les autres usinages (``ValueError`` traduite si ce n'est pas un solide valide)."""
    box = polyhedron.box
    low = box.min
    shape = Part.makeBox(box.size(0), box.size(1), box.size(2), _vector(low.x, low.y, low.z))
    shape.transformShape(_matrix(polyhedron.frame))
    centre = polyhedron.frame.apply(low + (box.max - low).scaled(0.5))
    radius = norm(box.max - low) / 2
    try:
        for plane in polyhedron.planes:
            size = norm(centre - plane.point) + radius + 1.0
            cutter = Part.makeBox(2 * size, 2 * size, size, _vector(-size, -size, 0.0))
            normal = plane.normal
            rotation = App.Rotation(_vector(0.0, 0.0, 1.0), _vector(normal.x, normal.y, normal.z))
            point = plane.point
            cutter.transformShape(
                App.Placement(_vector(point.x, point.y, point.z), rotation).toMatrix()
            )
            shape = shape.cut(cutter)
    except Part.OCCError as error:
        raise ValueError(translated(_BOOLEAN_FAILED, {"reason": str(error)})) from error
    if shape.isNull() or not shape.Solids or not shape.isValid():
        raise ValueError(translated(_INVALID_SHAPE))
    return shape


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


def box_shape(dimensions: Dimensions) -> Any:
    """Boîte d'une pièce de bois dans son repère (coin minimal à l'origine)."""
    return Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)


def grown_shape(shape: Any, margin: float) -> Any:
    """``shape`` épaissie de ``margin`` mm (angles vifs) ; ``shape`` elle-même si le noyau
    géométrique ne sait pas la calculer."""
    try:
        grown = shape.makeOffsetShape(margin, _OFFSET_TOLERANCE, False, False, 0, _SHARP_JOIN)
    except Part.OCCError:
        return shape
    return shape if grown.isNull() else grown


def machined_shape(
    base: Any,
    additions: Sequence[PlanSolid],
    cuts: Sequence[PlanSolid],
    trims: Sequence[PlanSolid] = (),
) -> Any:
    """Forme de base de la pièce (sa boîte pour une pièce de bois, sa forme dessinée pour une
    pièce en bois, dans son repère) moins ``trims`` (pièce raccourcie au contact, ADR 0016),
    plus ``additions``, moins ``cuts``, faces coplanaires fusionnées, avec une carte des éléments
    (ADR 0056 ; ``base`` n'est pas modifiée). ``ValueError`` traduite si OCC échoue ou si le
    résultat n'est pas un solide valide (jamais de forme partielle)."""
    shape = base
    try:
        if not shape.Tag:  # boîte, ou forme sans étiquette ; une étiquette existante est gardée
            shape = base.copy()  # jamais d'écriture dans la forme reçue
            shape.Tag = _BASE_TAG
        trim_tools, addition_tools, cut_tools = _tagged_tools((trims, additions, cuts))
        if trim_tools:
            shape = shape.cut(trim_tools)
        if addition_tools:
            shape = shape.fuse(addition_tools)
        if cut_tools:
            shape = shape.cut(cut_tools)
        shape = shape.removeSplitter()
    except Part.OCCError as error:
        raise ValueError(translated(_BOOLEAN_FAILED, {"reason": str(error)})) from error
    oblique = any(isinstance(s, Polyhedron) for s in (*trims, *additions, *cuts))
    if shape.isNull() or not shape.Solids or not shape.isValid():
        raise ValueError(translated(_INVALID_SHAPE))
    if oblique and len(shape.Solids) != 1:  # un enlèvement en biais ne doit pas couper la pièce
        raise ValueError(translated(_INVALID_SHAPE))
    return shape


def _tagged_tools(groups: Sequence[Sequence[PlanSolid]]) -> list[list[Any]]:
    """Solides ``Part`` de chaque groupe, étiquetés selon leur groupe et leur rang, pour que la
    pièce usinée ait une carte des éléments (ADR 0056). ``ValueError`` traduite si un groupe
    dépasse sa plage d'étiquettes (deux outils auraient la même)."""
    tagged: list[list[Any]] = []
    for number, group in enumerate(groups):
        if len(group) >= _GROUP_TAGS:
            raise ValueError(translated(_TOO_MANY_TOOLS, {"count": str(len(group))}))
        shapes = []
        for rank, solid in enumerate(group, start=1):
            shape = solid_shape(solid)
            shape.Tag = _BASE_TAG + number * _GROUP_TAGS + rank
            shapes.append(shape)
        tagged.append(shapes)
    return tagged


def inserts_shape(inserts: Sequence[PlanSolid]) -> Any:
    """Pièces rapportées (tourillons) réunies en un composé ; forme vide s'il n'y en a pas."""
    if not inserts:
        return Part.Shape()
    return Part.makeCompound([solid_shape(solid) for solid in inserts])
