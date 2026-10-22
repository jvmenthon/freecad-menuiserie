# SPDX-License-Identifier: LGPL-2.1-or-later
"""Formes Part des éléments sélectionnés → cibles d'accrochage de ``core/snap`` (J6d, ADR 0011).

Toute forme Part, de n'importe quel atelier, peut servir de cible : les formes sont lues par
``Part.getShape`` en coordonnées **globales** et ne sont jamais modifiées. Une Strategy par type
de sous-forme (face, arête, sommet) fournit la cible ; le côté extérieur d'une face est celui où
la matière n'est pas (``isInside`` sur un point décalé), sinon celui de l'observateur.
Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, RigidTransform, Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap import (
    EdgeTarget,
    FaceTarget,
    Frame,
    FreeTest,
    Target,
    VertexTarget,
    initial_orientation,
    tangent_frame,
)
from freecad.menuiserie.features.i18n import translated
from freecad.menuiserie.features.picked import PickedElement, container_of, furniture_candidate
from freecad.menuiserie.features.placement import SnapSession, to_placement
from freecad.menuiserie.features.snap_geometry import (
    EPSILON,
    ERRORS,
    Request,
    Vector,
    element_shape,
    is_straight,
    nearest_on,
    outward_normal,
    owner_shape,
    perpendicular,
    to_vec3,
    to_vector,
    unit,
    without,
)

__all__ = [
    "TargetReading",
    "free_test",
    "new_session",
    "read_targets",
    "target_of",
    "touches",
]

SAMPLES: Final = 16  # points relevés sur une arête courbe pour le rectangle englobant
OVERLAP_MM3: Final = 1.0  # volume commun au-delà duquel la pièce « chevauche » l'objet
_NOT_AN_ELEMENT: Final = QT_TRANSLATE_NOOP(
    "Menuiserie",
    "« {label} » : sélectionnez une face, une arête ou un sommet ; l'objet entier est ignoré.",
)
_NO_SHAPE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "« {label} » n'a pas de forme utilisable : élément ignoré."
)


@dataclass(frozen=True)
class TargetReading:
    """Cibles retenues (même ordre que ``elements``), messages des éléments ignorés et forme de
    l'objet du premier élément retenu (pour départager les octants d'un sommet)."""

    targets: tuple[Target, ...] = ()
    elements: tuple[PickedElement, ...] = ()
    ignored: tuple[str, ...] = ()
    shapes: tuple[Any, ...] = ()
    owner_shape: Any = None


# --- Formes ------------------------------------------------------------------------------------


def _longest_direction(face: Any, normal: Vector) -> Vector | None:
    """Direction de la plus longue arête droite de ``face`` (dans son plan), ``None`` sinon."""
    straight = [edge for edge in face.Edges if is_straight(edge) and edge.Length > EPSILON]
    if not straight:
        return None
    edge = max(straight, key=operator.attrgetter("Length"))
    direction = without(
        edge.valueAt(edge.LastParameter) - edge.valueAt(edge.FirstParameter), normal
    )
    return unit(direction) if direction.Length > EPSILON else None


def _outline(face: Any) -> list[Vector]:
    """Sommets de ``face`` et points relevés sur ses arêtes courbes."""
    points = [vertex.Point for vertex in face.Vertexes]
    for edge in face.Edges:
        if not is_straight(edge):
            points.extend(edge.discretize(Number=SAMPLES))
    return points


@dataclass(frozen=True)
class _Rectangle:
    """Rectangle englobant d'une face plane dans la base (``x``, ``y``) d'origine ``origin``."""

    x_range: tuple[float, float]
    y_range: tuple[float, float]


def _rectangle(points: Sequence[Vector], origin: Vector, x: Vector, y: Vector) -> _Rectangle:
    xs = [(point - origin).dot(x) for point in points]
    ys = [(point - origin).dot(y) for point in points]
    return _Rectangle((min(xs), max(xs)), (min(ys), max(ys)))


def _plane_target(name: str, face: Any, nearest: Vector, normal: Vector) -> FaceTarget:
    """Face plane : repère d'appui au coin du rectangle englobant le plus proche du point cliqué,
    axes dirigés vers l'intérieur de la face (axe x le long de la plus longue arête quand le coin
    le permet), ``z`` = normale sortante."""
    x = _longest_direction(face, normal)
    if x is None:
        x = to_vector(tangent_frame(to_vec3(nearest), to_vec3(normal)).x)
    y = normal.cross(x)
    box = _rectangle(_outline(face), nearest, x, y)
    # (sens sur x0, sens sur y0) du coin le plus proche : la base tournée pointe vers l'intérieur.
    low_x = abs(box.x_range[0]) <= abs(box.x_range[1])
    low_y = abs(box.y_range[0]) <= abs(box.y_range[1])
    corner = nearest + x * box.x_range[0 if low_x else 1] + y * box.y_range[0 if low_y else 1]
    width, height = box.x_range[1] - box.x_range[0], box.y_range[1] - box.y_range[0]
    axis_x, axis_y, extent = _inward_axes(x, y, low_x, low_y, (width, height))
    frame = Frame(to_vec3(corner), to_vec3(axis_x), to_vec3(axis_y), to_vec3(normal))
    return FaceTarget(name, frame, extent, planar=width > EPSILON and height > EPSILON)


def _inward_axes(
    x: Vector, y: Vector, low_x: bool, low_y: bool, sizes: tuple[float, float]
) -> tuple[Vector, Vector, tuple[float, float]]:
    """Axes (x, y) du repère d'appui d'après le coin choisi : rotation de 0, 90, 180 ou 270°
    autour de la normale pour que la pièce parte vers l'intérieur de la face."""
    width, height = sizes
    if low_x and low_y:
        return x, y, (width, height)
    if not low_x and low_y:
        return y, x * -1.0, (height, width)
    if not low_x and not low_y:
        return x * -1.0, y * -1.0, (width, height)
    return y * -1.0, x, (height, width)


def _face_target(name: str, face: Any, owner: Any, request: Request) -> FaceTarget:
    point = request.point if request.point is not None else face.CenterOfMass
    nearest, normal = nearest_on(face, point)
    normal = outward_normal(normal, nearest, owner, request.toward_observer)
    if isinstance(face.Surface, Part.Plane):
        return _plane_target(name, face, nearest, normal)
    frame = tangent_frame(to_vec3(nearest), to_vec3(normal))
    return FaceTarget(name, frame, (0.0, 0.0), planar=False)


# --- Arêtes ------------------------------------------------------------------------------------


def _edge_line(edge: Any, point: Vector) -> tuple[Vector, Vector]:
    """(début, fin) : une arête droite part de son extrémité la plus proche de ``point`` ; sur une
    arête courbe, la tangente au point le plus proche donne la direction."""
    first, last = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
    if is_straight(edge):
        return (first, last) if (point - first).Length <= (point - last).Length else (last, first)
    _distance, pairs, _info = edge.distToShape(Part.Vertex(point))
    start = pairs[0][0]
    parameter = edge.Curve.parameter(start)
    return start, start + unit(edge.tangentAt(parameter))


def _support_of(edge: Any, owner: Any, axis: Vector, request: Request) -> tuple[Vector, Vector]:
    """(normale sortante, vers l'intérieur) de la face d'appui d'une arête : parmi les faces
    adjacentes, la plus tournée vers l'observateur ; arête libre : le plan qui la contient et
    fait face à l'observateur."""
    faces = _adjacent_faces(edge, owner)
    middle = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2)
    best: tuple[float, Vector, Vector] | None = None
    for face in faces:
        _nearest_point, raw = nearest_on(face, middle)
        normal = outward_normal(raw, _nearest_point, owner, request.toward_observer)
        support = without(normal, axis)
        if support.Length < EPSILON:
            continue
        support = unit(support)
        score = support.dot(request.toward_observer)
        if best is None or score > best[0]:
            best = (score, support, _toward_inside(face, middle, axis, support))
    if best is not None:
        return best[1], best[2]
    free = without(request.toward_observer, axis)
    support = unit(free) if free.Length > EPSILON else perpendicular(axis)
    return support, unit(support.cross(axis))


def _adjacent_faces(edge: Any, owner: Any) -> list[Any]:
    if owner is None:
        return []
    try:
        return list(owner.ancestorsOfType(edge, Part.Face))
    except ERRORS:
        return []


def _toward_inside(face: Any, middle: Vector, axis: Vector, support: Vector) -> Vector:
    """Direction, dans la face, perpendiculaire à l'arête, qui pénètre dans la face."""
    inward = without(without(face.CenterOfMass - middle, axis), support)
    if inward.Length > EPSILON:
        return unit(inward)
    return unit(support.cross(axis))


def _edge_target(name: str, edge: Any, owner: Any, request: Request) -> EdgeTarget:
    point = request.point if request.point is not None else edge.CenterOfMass
    start, end = _edge_line(edge, point)
    axis = unit(end - start)
    support, inward = _support_of(edge, owner, axis, request)
    return EdgeTarget(name, to_vec3(start), to_vec3(end), to_vec3(support), to_vec3(inward))


# --- Sommets et lecture ------------------------------------------------------------------------


def _vertex_target(name: str, vertex: Any, owner: Any, _request: Request) -> Target:
    """Sommet : repère de l'objet sélectionné (celui du document sans ``Placement`` tourné)."""
    rotation = owner.Placement.Rotation if owner is not None else App.Rotation()
    unit_axes = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    axes = [to_vec3(rotation.multVec(App.Vector(*axis))) for axis in unit_axes]
    point = to_vec3(vertex.Point)
    return VertexTarget(name, point, Frame(point, axes[0], axes[1], axes[2]))


BUILDERS: Final[Mapping[str, Callable[[str, Any, Any, Request], Target]]] = MappingProxyType(
    {"Face": _face_target, "Edge": _edge_target, "Vertex": _vertex_target}
)


def target_of(element: PickedElement, toward_observer: Vec3) -> Target | None:
    """Cible de l'élément sélectionné, ``None`` s'il n'a pas de forme utilisable.

    ``toward_observer`` : direction de la scène vers l'observateur (+Z en ``freecadcmd``), qui
    donne le côté d'une face sans solide et la face d'appui d'une arête libre."""
    if not element.is_subelement():
        return None
    try:
        shape = element_shape(element)
        if shape is None:
            return None
        kind = element.element.rstrip("0123456789")
        point = to_vector(element.point) if element.point is not None else None
        request = Request(point, to_vector(toward_observer))
        return BUILDERS[kind](element.label(), shape, owner_shape(element), request)
    except ERRORS:
        return None


def read_targets(elements: Sequence[PickedElement], toward_observer: Vec3) -> TargetReading:
    """Cibles des ``elements`` dans l'ordre de sélection ; les éléments sans forme utilisable
    (objet entier, maillage, page TechDraw, forme nulle) sont ignorés avec un message traduit."""
    kept: list[tuple[PickedElement, Target]] = []
    ignored: list[str] = []
    for element in elements:
        target = target_of(element, toward_observer)
        if target is not None:
            kept.append((element, target))
            continue
        template = _NO_SHAPE if element.is_subelement() else _NOT_AN_ELEMENT
        ignored.append(translated(template, {"label": str(element.owner().Label)}))
    first = kept[0][0] if kept else None
    return TargetReading(
        targets=tuple(target for _element, target in kept),
        elements=tuple(element for element, _target in kept),
        ignored=tuple(ignored),
        shapes=tuple(element_shape(element) for element, _target in kept),
        owner_shape=owner_shape(first) if first is not None else None,
    )


# --- Contrôles ---------------------------------------------------------------------------------


def touches(part_shape: Any, target_shape: Any) -> bool:
    """Vrai si la pièce touche l'élément : distance ≤ ``CONTACT_TOLERANCE_MM`` (T3)."""
    try:
        distance = part_shape.distToShape(target_shape)[0]
    except ERRORS:
        return False
    return bool(distance <= CONTACT_TOLERANCE_MM)


def free_test(shape: Any) -> FreeTest:
    """``is_free`` de ``core/snap`` : la pièce posée en ``transform`` ne chevauche pas ``shape``
    (volume commun inférieur à ``OVERLAP_MM3``) ; vrai si le calcul échoue."""

    def is_free(transform: RigidTransform, dimensions: Dimensions) -> bool:
        box = Part.makeBox(dimensions.length, dimensions.width, dimensions.thickness)
        box.Placement = to_placement(transform)
        try:
            return bool(box.common(shape).Volume < OVERLAP_MM3)
        except ERRORS:
            return True

    return is_free


def new_session(reading: TargetReading, dimensions: Dimensions) -> SnapSession:
    """Session d'accrochage d'une pièce de cotes ``dimensions`` d'après ``reading`` : orientation
    de départ (celle qui permet l'étirement entre deux faces en vis-à-vis), Std Part qui reçoit
    la pièce et ensemble candidat, tous deux d'après le **premier** élément (T4, T5)."""
    first = reading.elements[0] if reading.elements else None
    is_vertex = bool(reading.targets) and isinstance(reading.targets[0], VertexTarget)
    free = free_test(reading.owner_shape) if is_vertex and reading.owner_shape is not None else None
    return SnapSession(
        targets=reading.targets,
        orientation=initial_orientation(dimensions, reading.targets, is_free=free),
        container=container_of(first) if first is not None else None,
        furniture=furniture_candidate(first) if first is not None else None,
        free=free,
        shapes=reading.shapes,
        ignored=reading.ignored,
    )
