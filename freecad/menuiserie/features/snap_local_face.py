# SPDX-License-Identifier: LGPL-2.1-or-later
"""Face sous le clic (#136) : cible d'une face limitée à la tranche cliquée, face d'un objet entier
cliqué dans la vue 3D. Formes Part en coordonnées globales, jamais modifiées ; aucun import de
``FreeCADGui``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import Part

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Vec3
from freecad.menuiserie.core.part_model import MIN_DIMENSION_MM
from freecad.menuiserie.core.snap import FaceTarget, Frame
from freecad.menuiserie.features.picked import PickedElement
from freecad.menuiserie.features.snap_geometry import (
    EPSILON,
    ERRORS,
    OFFSET_MM,
    Vector,
    owner_shape,
    to_vec3,
    to_vector,
)

if TYPE_CHECKING:
    from freecad.menuiserie.features.snap_targets import TargetReading

_PROBE_INSET_MM: Final = 1e-4  # recul des sondes de l'épaisseur, au delà de la tolérance d'OCC

__all__ = [
    "NoRoomError",
    "face_under_click",
    "fit_to_footprint",
    "inward_axes",
    "local_face_target",
]


def inward_axes(
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


def _span_through(face: Any, point: Vector, axis: Vector) -> tuple[float, float] | None:
    """Étendue (mini, maxi) de ``face`` le long de ``axis`` autour de ``point`` (sur la face) : le
    segment de la droite qui traverse la face au point, ``None`` si le calcul échoue ou si le
    segment est nul (point sur un sommet isolé)."""
    marks: list[float] = []
    try:
        reach = face.BoundBox.DiagonalLength + 1.0
        common = Part.makeLine(point - axis * reach, point + axis * reach).common(face)
        for edge in common.Edges:
            if edge.distToShape(Part.Vertex(point))[0] <= CONTACT_TOLERANCE_MM:
                marks.extend((vertex.Point - point).dot(axis) for vertex in edge.Vertexes)
    except ERRORS:
        return None
    if not marks or max(marks) - min(marks) <= EPSILON:
        return None
    return min(marks), max(marks)


def _clipped(
    span: tuple[float, float], solid: Any, point: Vector, plane: tuple[Vector, Vector], axis: Vector
) -> tuple[float, float]:
    """``span`` (autour de ``point``, le long de ``axis``) bornée à l'étendue réelle de ``solid`` :
    sommets de la pièce usinée situés dans le plan de la face extérieure ``plane`` (un sommet de
    cette couche, ``(point, normale)``). Sans sommet dans ce plan, ``span`` inchangée."""
    origin, normal = plane
    marks = [
        (vertex.Point - point).dot(axis)
        for vertex in solid.Vertexes
        if abs((vertex.Point - origin).dot(normal)) <= CONTACT_TOLERANCE_MM
    ]
    if not marks:
        return span
    low, high = max(span[0], min(marks)), min(span[1], max(marks))
    return (low, high) if high - low > EPSILON else span


def local_face_target(
    reading: TargetReading, face: Any | None = None, solid: Any | None = None
) -> FaceTarget | None:
    """Cible de l'unique face lue **à l'endroit du clic** : le rectangle est celui de la tranche de
    la face qui traverse le point cliqué (selon les axes de la cible d'origine), non celui de
    toute la face ; repère d'appui au coin le plus proche du clic. ``None`` sans point cliqué, sans
    face plane ou si la tranche ne se calcule pas : l'appelant garde la cible d'origine. ``face`` :
    forme à trancher à la place de la face lue (la face de la pièce brute, sans usinages) ;
    ``solid`` : pièce usinée dont l'étendue réelle borne la tranche (arête plus courte)."""
    if len(reading.targets) != 1 or not reading.shapes or not reading.elements:
        return None
    target, point = reading.targets[0], reading.elements[0].point
    face = face if face is not None else reading.shapes[0]
    if point is None or not isinstance(target, FaceTarget) or not target.planar or face is None:
        return None
    try:
        return _local_target(target, face, point, solid)
    except (ValueError, *ERRORS):  # repère nul ou calcul OCC en échec : cible d'origine
        return None


def _local_target(
    target: FaceTarget, face: Any, click: Vec3, solid: Any | None = None
) -> FaceTarget | None:
    """Corps de :func:`local_face_target` (cible d'origine ``target``, clic ``click``)."""
    normal = to_vector(target.frame.z)
    clicked = to_vector(click)
    point = clicked - normal * (clicked - to_vector(target.frame.origin)).dot(normal)
    x, y = to_vector(target.frame.x), to_vector(target.frame.y)
    # La face tranchée peut être dans un autre plan que la face lue (face extérieure de la brute) :
    # on tranche au point ramené dans son plan, le repère reste dans le plan de la face lue.
    sliced = point + normal * (face.CenterOfMass - point).dot(normal)
    x_span, y_span = _span_through(face, sliced, x), _span_through(face, sliced, y)
    if x_span is None or y_span is None:
        return None
    if solid is not None:
        plane = (face.CenterOfMass, normal)
        x_span = _clipped(x_span, solid, sliced, plane, x)
        y_span = _clipped(y_span, solid, sliced, plane, y)
    low_x, low_y = abs(x_span[0]) <= abs(x_span[1]), abs(y_span[0]) <= abs(y_span[1])
    corner = point + x * x_span[0 if low_x else 1] + y * y_span[0 if low_y else 1]
    sizes = (x_span[1] - x_span[0], y_span[1] - y_span[0])
    axis_x, axis_y, extent = inward_axes(x, y, low_x, low_y, sizes)
    frame = Frame(to_vec3(corner), to_vec3(axis_x), to_vec3(axis_y), to_vec3(normal))
    return FaceTarget(target.name, frame, extent, planar=True)


class NoRoomError(Exception):
    """Pas assez de place dans la face (pointe aiguë) pour poser la pièce."""


def fit_to_footprint(
    target: FaceTarget, face: Any, sizes: tuple[float, float]
) -> FaceTarget | None:
    """``target`` resserré pour qu'une pièce d'emprise ``sizes`` (selon ses deux axes), posée dans
    son coin, reste dans ``face`` : une arête oblique coupe la face avant la fin de la tranche
    mesurée au clic. L'étendue est l'intersection des tranches prises sur toute l'épaisseur de
    la pièce ; le coin glisse jusqu'au bord. ``None`` si rien ne change ou si le calcul échoue ;
    :class:`NoRoomError` s'il ne reste pas la place d'une pièce."""
    frame = target.frame
    extent = list(target.extent)
    try:
        origin, normal = to_vector(frame.origin), to_vector(frame.z)
        axes = (to_vector(frame.x), to_vector(frame.y))
        # d'abord l'axe où la pièce remplit l'étendue (le moins de marge) : celui que l'arête coupe
        for row in sorted((0, 1), key=lambda r: extent[r] - sizes[r]):
            along, across = axes[row], axes[1 - row]
            depth, length = min(sizes[1 - row], extent[1 - row]), extent[row]
            low, high = 0.0, length
            inset = min(_PROBE_INSET_MM, depth / 4.0)  # sondes un peu à l'intérieur des bords
            for offset in (inset, depth / 2.0, depth - inset):
                start = origin + across * offset + along * (length / 2.0)
                start += normal * (face.CenterOfMass - start).dot(normal)
                span = _span_through(face, start, along)
                if span is not None:
                    low, high = max(low, length / 2.0 + span[0]), min(high, length / 2.0 + span[1])
            if not high - low >= MIN_DIMENSION_MM:  # aussi vrai pour NaN
                raise NoRoomError(f"{high - low:.3f} mm de place le long de l'arête")
            origin, extent[row] = origin + along * low, high - low
    except ERRORS:
        return None
    if all(abs(new - old) <= EPSILON for new, old in zip(extent, target.extent, strict=True)):
        return None
    moved = Frame(to_vec3(origin), frame.x, frame.y, frame.z)
    return FaceTarget(target.name, moved, (extent[0], extent[1]), planar=True)


def face_under_click(element: PickedElement) -> PickedElement:
    """Face de l'objet entier sélectionné qui porte le point cliqué : l'élément ``FaceN`` le plus
    proche du point (à ``OFFSET_MM`` près). ``element`` lui-même s'il est déjà un sous-élément,
    sans point cliqué (sélection dans l'arbre, par script), sans forme ou si le point est loin
    de toute face."""
    if element.is_subelement() or element.point is None:
        return element
    shape = owner_shape(element)
    if shape is None or not shape.Faces:
        return element
    try:
        vertex = Part.Vertex(to_vector(element.point))
        gaps = [face.distToShape(vertex)[0] for face in shape.Faces]
    except ERRORS:
        return element
    best = min(range(len(gaps)), key=gaps.__getitem__)
    if gaps[best] > OFFSET_MM:
        return element
    return PickedElement(element.root, f"{element.subname}Face{best + 1}", element.point)
