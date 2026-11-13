# SPDX-License-Identifier: LGPL-2.1-or-later
"""Face sous le clic (#136) : cible d'une face limitée à la tranche cliquée, face d'un objet entier
cliqué dans la vue 3D. Formes Part en coordonnées globales, jamais modifiées ; aucun import de
``FreeCADGui``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import Part

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Vec3
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

__all__ = ["face_under_click", "inward_axes", "local_face_target"]


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


def local_face_target(reading: TargetReading, face: Any | None = None) -> FaceTarget | None:
    """Cible de l'unique face lue **à l'endroit du clic** : le rectangle est celui de la tranche de
    la face qui traverse le point cliqué (selon les axes de la cible d'origine), non celui de
    toute la face ; repère d'appui au coin le plus proche du clic. ``None`` sans point cliqué, sans
    face plane ou si la tranche ne se calcule pas : l'appelant garde la cible d'origine. ``face`` :
    forme à trancher à la place de la face lue (la face de la pièce brute, sans usinages)."""
    if len(reading.targets) != 1 or not reading.shapes or not reading.elements:
        return None
    target, point = reading.targets[0], reading.elements[0].point
    face = face if face is not None else reading.shapes[0]
    if point is None or not isinstance(target, FaceTarget) or not target.planar or face is None:
        return None
    try:
        return _local_target(target, face, point)
    except (ValueError, *ERRORS):  # repère nul ou calcul OCC en échec : cible d'origine
        return None


def _local_target(target: FaceTarget, face: Any, click: Vec3) -> FaceTarget | None:
    """Corps de :func:`local_face_target` (cible d'origine ``target``, clic ``click``)."""
    normal = to_vector(target.frame.z)
    clicked = to_vector(click)
    point = clicked - normal * (clicked - to_vector(target.frame.origin)).dot(normal)
    x, y = to_vector(target.frame.x), to_vector(target.frame.y)
    x_span, y_span = _span_through(face, point, x), _span_through(face, point, y)
    if x_span is None or y_span is None:
        return None
    low_x, low_y = abs(x_span[0]) <= abs(x_span[1]), abs(y_span[0]) <= abs(y_span[1])
    corner = point + x * x_span[0 if low_x else 1] + y * y_span[0 if low_y else 1]
    sizes = (x_span[1] - x_span[0], y_span[1] - y_span[0])
    axis_x, axis_y, extent = inward_axes(x, y, low_x, low_y, sizes)
    frame = Frame(to_vec3(corner), to_vec3(axis_x), to_vec3(axis_y), to_vec3(normal))
    return FaceTarget(target.name, frame, extent, planar=True)


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
