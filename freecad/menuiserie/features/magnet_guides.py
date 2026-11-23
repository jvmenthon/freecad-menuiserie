# SPDX-License-Identifier: LGPL-2.1-or-later
"""Formes des objets voisins lues en guides d'aimantation (SM-b, B1, ADR 0021, spec § 4.4).

``collect_guides`` est appelé une fois au début d'un glissement : les sommets, faces planes et
arêtes droites des objets **visibles** du conteneur (tout atelier, lus par ``Part.getShape``,
rien n'est modifié) sont exprimés dans le repère de la pièce et rendus sous forme de
:class:`~freecad.menuiserie.core.magnet.Guide`. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Box, Matrix3, Vec3
from freecad.menuiserie.core.joints import JointError, JointKind
from freecad.menuiserie.core.joints.shelf_pins import opposite_values, pin_rests
from freecad.menuiserie.core.magnet import Guide, GuideKind
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.joints.base import is_joint, placed_blank, resolved_for
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.snap_geometry import ERRORS, is_straight, to_vec3
from freecad.menuiserie.features.solids import rigid_transform

__all__ = [
    "MAX_GUIDES",
    "MAX_ORIENTATIONS",
    "collect_guides",
    "neighbor_planes",
    "neighbor_rotations",
    "own_names",
    "plane_guides",
]

MAX_GUIDES: Final = 5000  # borne de lecture d'un gros document (spec § 4.8)
MAX_ORIENTATIONS: Final = 16  # orientations voisines au plus pour aimanter une rotation
_GROUPS: Final = ("App::Part", "App::DocumentObjectGroup")
_PARALLEL: Final = 1e-6  # composante (relative) hors axe en deçà de laquelle une arête est droite


def _excluded(part: DocumentObject) -> set[str]:
    """Noms des objets qui ne guident pas la pièce : elle-même, sa pièce usinée, ses assemblages
    (ceux qui la citent seulement comme voisine, tels les taquets sous une tablette, la guident)."""
    names = {part.Name}
    machined = machined_part_of(part)
    if machined is not None:
        names.add(machined.Name)
    names.update(
        parent.Name
        for parent in part.InList
        if is_joint(parent) and part in (parent.HostPart, parent.GuestPart)
    )
    return names


def _roots(doc: Any) -> list[DocumentObject]:
    """Objets du document qui ne sont dans aucun groupe ni Std Part, dans l'ordre du document.

    Pas ``Document.RootObjects`` : ce sont les objets que **rien ne cite** (liste ``InList``
    vide). Un membre d'ensemble cité par une expression d'un autre membre (épaisseur) ou par un
    assemblage en serait absent, et n'aimanterait plus ses voisins (bogue EN-e, E6)."""
    return [
        obj
        for obj in doc.Objects
        if obj.getParentGroup() is None and obj.getParentGeoFeatureGroup() is None
    ]


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


def _pin_rests_shape(obj: DocumentObject) -> Any:
    """Appuis de tablette d'un perçage LR32 (dessus de taquet à chaque rang, sur le côté et le
    montant opposé), en coordonnées globales ; ``None`` pour un autre objet ou un perçage
    impossible."""
    if not is_joint(obj) or obj.Proxy.KIND is not JointKind.SHELF_PINS:
        return None
    try:
        host = placed_blank(obj.HostPart)
        values: Any = resolved_for(obj)
        sides = [(obj.HostPart, pin_rests(host, values))]
        guest = obj.GuestPart
        if guest is not None and guest != obj.HostPart:
            other = opposite_values(
                host, placed_blank(guest, frame_of=obj.HostPart), obj.Proxy.params(obj)
            )
            if other is not None:
                sides.append((guest, pin_rests(placed_blank(guest, frame_of=obj.HostPart), other)))
    except (*ERRORS, ValueError, JointError):
        return None
    shapes = []
    for part, rests in sides:
        if not rests:
            continue
        boxes = [
            Part.makeBox(
                *(rest.size(i) for i in range(3)), App.Vector(rest.min.x, rest.min.y, rest.min.z)
            )
            for rest in rests
        ]
        shape = Part.makeCompound(boxes)
        shape.transformShape(part.getGlobalPlacement().toMatrix())  # repère du document
        shapes.append(shape)
    return Part.makeCompound(shapes) if shapes else None


def _neighbor_shapes(roots: list[DocumentObject], skipped: set[str], reference: Any) -> list[Any]:
    """Formes globales des objets visibles de ``roots`` (groupes parcourus) hors ``skipped``, les
    plus proches de ``reference`` (``App.BoundBox``, ``None`` : ordre du document) d'abord."""
    found: list[tuple[float, int, Any]] = []
    for index, obj in enumerate(_leaves(roots, set(skipped))):
        if obj.Name in skipped or not obj.Visibility:
            continue
        rests = _pin_rests_shape(obj)  # dessus de taquet de chaque rang de trous
        if rests is not None:
            # Seul le dessus du taquet attire la tablette : ni le dessous, ni les arêtes, ni
            # la forme du perçage lui-même (haut du trou).
            found.append((0.0, index, rests))
            continue
        shape = _global_shape(obj)
        if shape is None:
            continue
        distance = 0.0 if reference is None else _distance(reference, shape.BoundBox)
        found.append((distance, index, shape))
    return [shape for _, _, shape in sorted(found, key=lambda item: item[:2])]


def _roots_of(container: DocumentObject | None, doc: Any) -> list[DocumentObject]:
    """Objets du Std Part ``container``, ou de la racine du document ``doc`` sans conteneur."""
    return list(container.Group) if container is not None else _roots(doc)


def collect_guides(
    part: DocumentObject,
    container: DocumentObject | None,
    *,
    origin: App.Placement | None = None,
    skip: Iterable[str] = (),
    reference: Any = None,
) -> tuple[Guide, ...]:
    """Guides d'aimantation de la pièce brute ``part`` (B1), dans son repère.

    Objets du Std Part ``container`` (``None`` : racine du document) qui sont visibles, de
    tout atelier ; la pièce, sa pièce usinée et ses assemblages sont exclus. Plans : faces
    planes normales à un axe de la pièce ; droites : arêtes droites parallèles à un axe ;
    points : tous les sommets. Les objets les plus proches de la pièce viennent d'abord ;
    au plus :data:`MAX_GUIDES` guides. Un objet illisible est ignoré.

    Un ensemble (sans forme) donne son repère par ``origin`` (placement global de son Std Part),
    l'étendue de sa boîte par ``reference`` (``App.BoundBox``) et les noms de ses propres objets,
    Std Part compris, par ``skip`` : ses pièces ne guident pas l'ensemble (EN-c)."""
    placement = origin if origin is not None else part.getGlobalPlacement()
    if reference is None:
        try:
            own = _global_shape(part)
            reference = own.BoundBox if own is not None else None
        except ERRORS:
            reference = None
    roots = _roots_of(container, part.Document)
    guides: list[Guide] = []
    inverse = placement.inverse()
    for shape in _neighbor_shapes(roots, _excluded(part) | set(skip), reference):
        guides.extend(_guides_of(shape, inverse))
        if len(guides) >= MAX_GUIDES:
            break
    return tuple(guides[:MAX_GUIDES])


def own_names(part: DocumentObject) -> set[str]:
    """Noms des objets qui font corps avec ``part`` : elle-même, sa pièce usinée et ses
    assemblages (ceux dont elle est l'hôte ou l'invitée)."""
    return _excluded(part)


def _planes(guides: Iterable[Guide]) -> list[Guide]:
    """Seuls les plans de ``guides``."""
    return [guide for guide in guides if guide.kind is GuideKind.PLANE]


def plane_guides(objects: Iterable[DocumentObject], origin: App.Placement) -> tuple[Guide, ...]:
    """Faces planes des objets ``objects`` normales à un axe du repère ``origin`` (placement
    global), dans ce repère ; un objet illisible est ignoré (ADR 0058)."""
    inverse = origin.inverse()
    found: list[Guide] = []
    for obj in objects:
        shape = _global_shape(obj)
        if shape is not None:
            found.extend(_planes(_guides_of(shape, inverse)))
    return tuple(found)


def neighbor_planes(
    doc: Any, container: DocumentObject | None, origin: App.Placement, skip: Iterable[str]
) -> tuple[Guide, ...]:
    """Faces planes des objets visibles du Std Part ``container`` (``None`` : racine du document
    ``doc``) hors ``skip``, normales à un axe du repère ``origin``, dans ce repère ; au plus
    :data:`MAX_GUIDES` (ADR 0058, aperçu de la répétition)."""
    inverse = origin.inverse()
    found: list[Guide] = []
    for shape in _neighbor_shapes(_roots_of(container, doc), set(skip), None):
        found.extend(_planes(_guides_of(shape, inverse)))
        if len(found) >= MAX_GUIDES:
            break
    return tuple(found[:MAX_GUIDES])


def neighbor_rotations(
    part: DocumentObject,
    container: DocumentObject | None,
    *,
    skip: Iterable[str] = (),
    reference: Any = None,
) -> tuple[Matrix3, ...]:
    """Rotations globales des objets voisins de ``part`` qui ont une forme, sans doublon : sert à
    aimanter l'angle d'une rotation (ADR 0025, complément).

    Mêmes voisins que :func:`collect_guides` (visibles, même conteneur, mêmes exclusions, même
    ``skip`` et ``reference`` pour un ensemble), les plus proches d'abord ; au plus
    :data:`MAX_ORIENTATIONS` orientations, sinon la rotation colle à tous les angles. Un objet
    sans forme (origine, esquisse vide, FeaturePython) ou sans placement global est ignoré."""
    if reference is None:
        own = _global_shape(part)
        reference = own.BoundBox if own is not None else None
    roots = _roots_of(container, part.Document)
    skipped = _excluded(part) | set(skip)
    found: list[tuple[float, int, Matrix3]] = []
    for index, obj in enumerate(_leaves(roots, set(skipped))):
        if obj.Name in skipped or not obj.Visibility:
            continue
        if not hasattr(obj, "getGlobalPlacement"):
            continue
        shape = _global_shape(obj)
        if shape is None:
            continue
        try:
            rotation = rigid_transform(obj.getGlobalPlacement()).rotation
        except ERRORS:
            continue
        distance = 0.0 if reference is None else _distance(reference, shape.BoundBox)
        found.append((distance, index, rotation))
    kept: dict[tuple[float, ...], Matrix3] = {}
    for _, _, rotation in sorted(found, key=lambda item: item[:2]):
        kept.setdefault(tuple(round(value, 4) for row in rotation for value in row), rotation)
        if len(kept) >= MAX_ORIENTATIONS:
            break
    return tuple(kept.values())
