# SPDX-License-Identifier: LGPL-2.1-or-later
"""Arêtes natives d'une forme FreeCAD lues en nombres pour les profils (ADR 0063).

Seul module des profils qui lit la topologie d'une forme ``Part`` : il rend, pour une arête
désignée par son nom (``"Edge7"``), un :class:`~freecad.menuiserie.core.edges.EdgeFrame` (arête
droite entre deux faces planes) ou la raison traduite pour laquelle l'arête ne peut pas recevoir
de profil. Le calcul de la coupe reste en Python pur dans ``core/edges``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final

import Part

from freecad.menuiserie.core.edges import EdgeFrame
from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.vectors import cross, dot, unit_or_none
from freecad.menuiserie.features.i18n import translated

__all__ = [
    "MAX_NATIVE_EDGES",
    "NativeEdge",
    "edge_index",
    "edge_label",
    "edge_name",
    "face_edge_names",
    "has_element_map",
    "native_edge",
    "tangent_chain",
]

MAX_NATIVE_EDGES: Final = 64  # arêtes d'un même profil (spécification § 4.7)
_NAME: Final = re.compile(r"Edge([1-9][0-9]{0,5})")
_FACE_NAME: Final = re.compile(r"Face([1-9][0-9]{0,5})")
_PROBE_MM: Final = 0.05  # pas des points d'essai autour de l'arête
_INSIDE_TOLERANCE: Final = 1e-4
_TANGENT_COS: Final = 0.9999  # arêtes enchaînées « tangentes » à ce cosinus près (≈ 0,8°)

_CURVED: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Arête {edge} courbe : seules les arêtes droites reçoivent un profil."
)
_NOT_TWO_FACES: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Arête {edge} : elle doit séparer exactement deux faces de la pièce."
)
_NOT_PLANAR: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Arête {edge} entre des faces courbes : seules les faces planes sont prises."
)
_UNREADABLE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Arête {edge} : sa position par rapport aux faces n'a pas pu être lue."
)
_EDGE_LABEL: Final = QT_TRANSLATE_NOOP("Menuiserie", "n° {index}")


@dataclass(frozen=True)
class NativeEdge:
    """Arête lue : son repère, ou la raison traduite de son refus (``frame`` vaut alors
    ``None``). ``length`` en mm, même pour une arête refusée."""

    index: int
    length: float
    frame: EdgeFrame | None
    refusal: str | None


def edge_index(name: object) -> int | None:
    """Rang (1..n) de l'arête nommée ``"EdgeN"`` ; ``None`` pour tout autre texte (nom perdu
    ``"?Edge3"``, nom cartographié, face…). Le texte n'est jamais interprété autrement."""
    if not isinstance(name, str) or len(name) > 12:
        return None
    match = _NAME.fullmatch(name)
    return int(match.group(1)) if match else None


def edge_name(index: int) -> str:
    """Nom FreeCAD de l'arête de rang ``index`` (``"Edge7"``)."""
    return f"Edge{index}"


def edge_label(index: int) -> str:
    """Nom affiché d'une arête dans les messages (« n° 7 »)."""
    return translated(_EDGE_LABEL, {"index": str(index)})


def has_element_map(shape: Any) -> bool:
    """Vrai si ``shape`` a une carte d'éléments : sans elle, un lien vers une arête garde son
    numéro et peut désigner une autre arête après une modification (ADR 0063, décision 2)."""
    try:
        return int(getattr(shape, "ElementMapSize", 0)) > 0
    except (TypeError, ValueError):
        return False


def _vec(vector: Any) -> Vec3:
    return Vec3(float(vector.x), float(vector.y), float(vector.z))


def _app_vector(point: Vec3) -> Any:
    import FreeCAD as App  # pylint: disable=import-outside-toplevel

    return App.Vector(point.x, point.y, point.z)


def _faces_of(shape: Any, edge: Any) -> list[Any]:
    faces: list[Any] = []
    for face in shape.ancestorsOfType(edge, Part.Face):
        if not any(face.isSame(known) for known in faces):
            faces.append(face)
    return faces


def _into_face(face: Any, middle: Vec3, along: Vec3) -> Vec3 | None:
    """Direction unitaire, perpendiculaire à l'arête, qui part de ``middle`` dans ``face``."""
    u, v = face.Surface.parameter(_app_vector(middle))
    normal = unit_or_none(_vec(face.normalAt(u, v)))
    if normal is None:
        return None
    candidate = unit_or_none(cross(normal, along))
    if candidate is None:
        return None
    for direction in (candidate, candidate.scaled(-1.0)):
        probe = middle + direction.scaled(_PROBE_MM)
        if face.isInside(_app_vector(probe), _INSIDE_TOLERANCE, True):
            return direction
    return None


def _room(face: Any, start: Vec3, direction: Vec3) -> float:
    """Largeur de ``face`` mesurée perpendiculairement à l'arête, depuis l'arête."""
    return max(
        (dot(_vec(vertex.Point) - start, direction) for vertex in face.Vertexes), default=0.0
    )


def _inside(shape: Any, point: Vec3) -> bool:
    return bool(shape.isInside(_app_vector(point), _INSIDE_TOLERANCE, False))


def native_edge(shape: Any, index: int) -> NativeEdge:
    """Arête de rang ``index`` (1..n) de la forme ``shape`` (un solide, dans le repère de la
    pièce), lue en repère de profil. ``IndexError`` si ``index`` est hors de la forme."""
    if not 1 <= index <= len(shape.Edges):
        raise IndexError(index)
    edge = shape.Edges[index - 1]
    label = edge_label(index)
    length = float(edge.Length)

    def refused(key: str) -> NativeEdge:
        return NativeEdge(index, length, None, translated(key, {"edge": label}))

    if not isinstance(edge.Curve, Part.Line) or len(edge.Vertexes) != 2:
        return refused(_CURVED)
    faces = _faces_of(shape, edge)
    if len(faces) != 2:
        return refused(_NOT_TWO_FACES)
    if not all(isinstance(face.Surface, Part.Plane) for face in faces):
        return refused(_NOT_PLANAR)
    start, end = (_vec(vertex.Point) for vertex in edge.Vertexes)
    along = unit_or_none(end - start)
    if along is None:
        return refused(_UNREADABLE)
    middle = start + along.scaled(length / 2)
    first = _into_face(faces[0], middle, along)
    second = _into_face(faces[1], middle, along)
    if first is None or second is None:
        return refused(_UNREADABLE)
    bisector = unit_or_none(first + second)
    convex = bisector is not None and _inside(shape, middle + bisector.scaled(_PROBE_MM))
    # Point d'essai au-delà d'un bout, dans l'angle de la coupe : s'il est dans la matière, un
    # dépassement entamerait la face voisine (spécification B5).
    inward = Vec3(0.0, 0.0, 0.0) if bisector is None else bisector.scaled(_PROBE_MM)
    frame = EdgeFrame(
        name=label,
        start=start,
        direction=along,
        length=length,
        first=first,
        second=second,
        convex=convex,
        room_first=_room(faces[0], start, first),
        room_second=_room(faces[1], start, second),
        extend_start=not _inside(shape, start - along.scaled(_PROBE_MM) + inward),
        extend_end=not _inside(shape, end + along.scaled(_PROBE_MM) + inward),
    )
    return NativeEdge(index, length, frame, None)


def face_edge_names(shape: Any, face_name: str) -> list[str]:
    """Noms des arêtes de la face ``face_name`` (``"Face3"``) de ``shape`` : tout son contour,
    extérieur et intérieurs (spécification C6), au plus :data:`MAX_NATIVE_EDGES`. Vide si le nom
    n'est pas une face de la forme."""
    match = _FACE_NAME.fullmatch(face_name) if len(face_name) <= 12 else None
    if match is None or int(match.group(1)) > len(shape.Faces):
        return []
    face = shape.Faces[int(match.group(1)) - 1]
    wanted = face.Edges[: 2 * MAX_NATIVE_EDGES]  # une arête de couture peut y figurer deux fois
    names: list[str] = []
    for index, candidate in enumerate(shape.Edges, start=1):
        if any(candidate.isSame(edge) for edge in wanted):
            names.append(edge_name(index))
            if len(names) == MAX_NATIVE_EDGES:
                break
    return names


def _ends(edge: Any) -> list[tuple[Vec3, Vec3]]:
    """Bouts de l'arête avec la tangente sortante en chacun d'eux."""
    first, last = edge.FirstParameter, edge.LastParameter
    out = []
    for parameter, sign in ((first, -1.0), (last, 1.0)):
        tangent = unit_or_none(_vec(edge.tangentAt(parameter)))
        if tangent is not None:
            out.append((_vec(edge.valueAt(parameter)), tangent.scaled(sign)))
    return out


def _point_key(point: Vec3) -> tuple[float, float, float]:
    return (round(point.x, 5), round(point.y, 5), round(point.z, 5))


def tangent_chain(shape: Any, index: int) -> list[int]:
    """Rangs des arêtes enchaînées à l'arête ``index`` sans cassure (tangentes l'une à l'autre),
    elle comprise, dans l'ordre des rangs : un clic sur une arête prend ainsi le tour arrondi
    d'un plateau (spécification Q4). Au plus :data:`MAX_NATIVE_EDGES` arêtes. Les bouts de
    chaque arête sont lus une seule fois et rangés par point : coût proportionnel au nombre
    d'arêtes de la forme."""
    edges = shape.Edges
    ends = [_ends(edge) for edge in edges]
    at_point: dict[tuple[float, float, float], list[tuple[int, Vec3]]] = {}
    for rank, edge_ends in enumerate(ends, start=1):
        for point, outward in edge_ends:
            at_point.setdefault(_point_key(point), []).append((rank, outward))
    chain = {index}
    todo = [index]
    while todo and len(chain) < MAX_NATIVE_EDGES:
        current = todo.pop()
        for point, outward in ends[current - 1]:
            for other, other_out in at_point.get(_point_key(point), []):
                if other in chain or dot(outward, other_out) >= -_TANGENT_COS:
                    continue
                chain.add(other)
                todo.append(other)
                if len(chain) == MAX_NATIVE_EDGES:
                    return sorted(chain)
    return sorted(chain)
