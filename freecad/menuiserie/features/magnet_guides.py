# SPDX-License-Identifier: LGPL-2.1-or-later
"""Formes des objets voisins lues en guides d'aimantation (SM-b, B1, ADR 0021, spec § 4.4).

``collect_guides`` est appelé une fois au début d'un glissement : les sommets, faces planes et
arêtes droites des objets **visibles** du conteneur (tout atelier, lus par ``Part.getShape``,
rien n'est modifié) sont exprimés dans le repère de la pièce et rendus sous forme de
:class:`~freecad.menuiserie.core.magnet.Guide`. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Box, Vec3
from freecad.menuiserie.core.magnet import Guide, GuideKind
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import is_joint
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.snap_geometry import ERRORS, is_straight, to_vec3

__all__ = ["MAX_GUIDES", "collect_guides"]

MAX_GUIDES: Final = 5000  # borne de lecture d'un gros document (spec § 4.8)
_GROUPS: Final = ("App::Part", "App::DocumentObjectGroup")
_PARALLEL: Final = 1e-6  # composante (relative) hors axe en deçà de laquelle une arête est droite


def _excluded(part: DocumentObject) -> set[str]:
    """Noms des objets qui ne guident pas la pièce : elle-même, sa pièce usinée, ses assemblages."""
    names = {part.Name}
    machined = machined_part_of(part)
    if machined is not None:
        names.add(machined.Name)
    names.update(parent.Name for parent in part.InList if is_joint(parent))
    return names


def _leaves(objects: list[DocumentObject], seen: set[str]) -> Iterator[DocumentObject]:
    """Objets feuilles (hors groupes ``App::Part`` et ``App::DocumentObjectGroup``, parcourus)."""
    for obj in objects:
        if obj.Name in seen:
            continue
        seen.add(obj.Name)
        if obj.TypeId in _GROUPS:
            yield from _leaves(list(obj.Group), seen)
        else:
            yield obj


def _global_shape(obj: DocumentObject) -> Any:
    """Forme de ``obj`` en coordonnées globales (tout atelier), ``None`` si absente ou nulle."""
    try:
        if hasattr(obj, "Shape"):
            shape = Part.getShape(obj, "", transform=False)
            if shape is None or shape.isNull():
                return None
            shape = shape.copy()
            shape.Placement = obj.getGlobalPlacement()
            return shape
        shape = Part.getShape(obj, "")  # lien : son propre placement est appliqué
        if shape is None or shape.isNull():
            return None
        parent = obj.getParentGeoFeatureGroup()
        if parent is not None:
            shape = shape.copy()
            shape.transformShape(parent.getGlobalPlacement().toMatrix())
        return shape
    except ERRORS:
        return None


def _gap(low_a: float, high_a: float, low_b: float, high_b: float) -> float:
    return max(0.0, low_b - high_a, low_a - high_b)


def _distance(a: Any, b: Any) -> float:
    """Distance entre deux boîtes englobantes (0 si elles se recoupent)."""
    return math.sqrt(
        _gap(a.XMin, a.XMax, b.XMin, b.XMax) ** 2
        + _gap(a.YMin, a.YMax, b.YMin, b.YMax) ** 2
        + _gap(a.ZMin, a.ZMax, b.ZMin, b.ZMax) ** 2
    )


def _axis_of(vector: App.Vector) -> int | None:
    """Axe du repère auquel ``vector`` est parallèle, ``None`` s'il est oblique ou nul."""
    length = vector.Length
    if length <= ANGLE_TOLERANCE:
        return None
    parts = (abs(vector.x), abs(vector.y), abs(vector.z))
    axis = parts.index(max(parts))
    others = sum(parts) - parts[axis]
    return axis if others <= _PARALLEL * length else None


def _flat(values: tuple[float, float, float], axis: int, value: float) -> Vec3:
    found = list(values)
    found[axis] = value
    return Vec3.of(found)


def _plane_guides(local: Any) -> Iterator[Guide]:
    for face in local.Faces:
        if not isinstance(face.Surface, Part.Plane):
            continue
        u, v = face.Surface.parameter(face.CenterOfMass)
        normal = face.normalAt(u, v)
        axis = _axis_of(normal)
        if axis is None:
            continue
        box = face.BoundBox
        low = (box.XMin, box.YMin, box.ZMin)
        high = (box.XMax, box.YMax, box.ZMax)
        level = (low[axis] + high[axis]) / 2
        extent = Box(_flat(low, axis, level), _flat(high, axis, level))
        yield Guide(GuideKind.PLANE, extent, axis, 1 if to_vec3(normal).component(axis) > 0 else -1)


def _line_guides(local: Any) -> Iterator[Guide]:
    for edge in local.Edges:
        if not is_straight(edge) or len(edge.Vertexes) != 2:
            continue
        start, end = edge.Vertexes[0].Point, edge.Vertexes[1].Point
        axis = _axis_of(end - start)
        if axis is None:
            continue
        first, last = to_vec3(start), to_vec3(end)
        flat = [first.component(i) for i in range(3)]
        low, high = list(flat), list(flat)
        low[axis] = min(first.component(axis), last.component(axis))
        high[axis] = max(first.component(axis), last.component(axis))
        yield Guide(GuideKind.LINE, Box(Vec3.of(low), Vec3.of(high)), axis)


def _point_guides(local: Any) -> Iterator[Guide]:
    for vertex in local.Vertexes:
        point = to_vec3(vertex.Point)
        yield Guide(GuideKind.POINT, Box(point, point))


def _guides_of(shape: Any, inverse: App.Placement) -> list[Guide]:
    """Guides de ``shape`` (coordonnées globales) dans le repère de ``inverse``⁻¹."""
    local = shape.copy()
    local.transformShape(inverse.toMatrix())
    try:
        return [*_plane_guides(local), *_line_guides(local), *_point_guides(local)]
    except (*ERRORS, AttributeError):
        return []


def collect_guides(part: DocumentObject, container: DocumentObject | None) -> tuple[Guide, ...]:
    """Guides d'aimantation de la pièce brute ``part`` (B1), dans son repère.

    Objets du Std Part ``container`` (``None`` : racine du document) qui sont visibles, de
    tout atelier ; la pièce, sa pièce usinée et ses assemblages sont exclus. Plans : faces
    planes normales à un axe de la pièce ; droites : arêtes droites parallèles à un axe ;
    points : tous les sommets. Les objets les plus proches de la pièce viennent d'abord ;
    au plus :data:`MAX_GUIDES` guides. Un objet illisible est ignoré."""
    origin = part.getGlobalPlacement()
    try:
        own = _global_shape(part)
        reference = own.BoundBox if own is not None else None
    except ERRORS:
        reference = None
    roots = list(container.Group) if container is not None else list(part.Document.RootObjects)
    skip = _excluded(part)
    found: list[tuple[float, int, Any]] = []
    for index, obj in enumerate(_leaves(roots, set())):
        if obj.Name in skip or not obj.Visibility:
            continue
        shape = _global_shape(obj)
        if shape is None:
            continue
        distance = 0.0 if reference is None else _distance(reference, shape.BoundBox)
        found.append((distance, index, shape))
    guides: list[Guide] = []
    inverse = origin.inverse()
    for _, _, shape in sorted(found, key=lambda item: item[:2]):
        guides.extend(_guides_of(shape, inverse))
        if len(guides) >= MAX_GUIDES:
            break
    return tuple(guides[:MAX_GUIDES])
