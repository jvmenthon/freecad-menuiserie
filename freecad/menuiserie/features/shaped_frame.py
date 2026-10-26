# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère d'une pièce en bois : axes automatiques, forme locale et encombrement (ADR 0020).

Pont entre les formes de FreeCAD et ``core/shaped`` : :func:`sample_of` extrait d'une forme
l'échantillon (sommets, points d'un maillage grossier, faces planes, arêtes droites) dont
:func:`automatic_axes` tire le repère ; :func:`local_form` exprime la forme dans ce repère, origine
au coin minimal de l'encombrement (X = longueur, Y = largeur, Z = épaisseur), et mesure les cotes.
Les formes lues ici sont dans le repère propre de leur source (placement défait) ; au-delà des
plafonds de taille de ``core/shaped`` (spécification § 4.9), rien n'est examiné élément par élément.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.geometry import RigidTransform, Vec3
from freecad.menuiserie.core.shaped import (
    MAX_EDGES,
    MAX_FACES,
    MAX_POINTS,
    Axes,
    ShapeSample,
    measure_points,
    ordered,
    principal_axes,
)
from freecad.menuiserie.features.placement import to_placement
from freecad.menuiserie.features.snap_geometry import ERRORS, is_straight, to_vec3
from freecad.menuiserie.features.solids import rigid_transform

__all__ = [
    "LocalForm",
    "automatic_axes",
    "axes_placement",
    "local_form",
    "placement_axes",
    "sample_of",
]

EXTENT_DECIMALS: Final = 2  # cotes d'encombrement arrondies au centième de mm
MESH_DIVISIONS: Final = 200.0  # tolérance du maillage grossier = diagonale / 200 ...
MIN_MESH_TOLERANCE_MM: Final = 0.1  # ... bornée ...
MAX_MESH_TOLERANCE_MM: Final = 50.0  # ... des deux côtés
_ORIGIN: Final = Vec3(0.0, 0.0, 0.0)


@dataclass(frozen=True)
class LocalForm:
    """Forme dans le repère de la pièce.

    ``shape`` : solide dont l'encombrement occupe [0, L] x [0, l] x [0, e] ; ``frame`` : repère de
    la pièce exprimé dans le repère de la forme d'origine (``Placement`` : le point ``p`` de la
    pièce est le point ``frame · p`` de la forme d'origine) ; ``extents`` : (L, l, e) en mm,
    arrondis au centième, mesurés sur l'encombrement exact de ``shape``."""

    shape: Any
    frame: Any
    extents: tuple[float, float, float]


def axes_placement(axes: Axes) -> Any:
    """``Placement`` d'origine nulle dont la rotation a pour colonnes les axes X, Y, Z."""
    x, y, z = axes.vectors()
    rows = ((x.x, y.x, z.x), (x.y, y.y, z.y), (x.z, y.z, z.z))
    return to_placement(RigidTransform(rows, _ORIGIN))


def placement_axes(placement: Any) -> Axes:
    """Axes lus dans la rotation de ``placement`` (colonnes). ``ValueError`` citant le champ si
    la rotation n'est pas un repère direct d'équerre."""
    rotation = rigid_transform(placement).rotation
    columns = [
        Vec3(rotation[0][column], rotation[1][column], rotation[2][column]) for column in range(3)
    ]
    return Axes(*columns)


def local_form(raw: Any, axes: Axes) -> LocalForm:
    """Forme ``raw`` (repère de la source, placement défait) exprimée dans le repère de ``axes``.

    La forme est tournée puis translatée pour que le coin minimal de son encombrement exact
    (``optimalBoundingBox``, sans triangulation ni tolérance) soit l'origine. La transformation
    est inscrite dans la géométrie (copie) : ``Placement`` de l'objet reste libre."""
    inverse_rotation = axes_placement(axes).inverse()
    turned = raw.copy()
    turned.Placement = inverse_rotation
    low = turned.optimalBoundingBox(False, False)
    shift = App.Placement(App.Vector(-low.XMin, -low.YMin, -low.ZMin), App.Rotation())
    to_local = shift.multiply(inverse_rotation)
    shape = raw.copy()
    shape.transformShape(to_local.toMatrix(), True)
    box = shape.optimalBoundingBox(False, False)
    extents = (
        round(box.XLength, EXTENT_DECIMALS),
        round(box.YLength, EXTENT_DECIMALS),
        round(box.ZLength, EXTENT_DECIMALS),
    )
    return LocalForm(shape, to_local.inverse(), extents)


def sample_of(shape: Any) -> ShapeSample | None:
    """Échantillon de ``shape`` pour le repère automatique : sommets et points d'un maillage
    grossier (tolérance bornée), faces planes et arêtes droites. ``None`` si la forme dépasse un
    plafond de ``core/shaped`` (faces, arêtes ou points) ou ne donne pas un échantillon valide."""
    if len(shape.Faces) > MAX_FACES or len(shape.Edges) > MAX_EDGES:
        return None
    tolerance = min(
        max(shape.BoundBox.DiagonalLength / MESH_DIVISIONS, MIN_MESH_TOLERANCE_MM),
        MAX_MESH_TOLERANCE_MM,
    )
    try:
        mesh_points, _facets = shape.tessellate(tolerance)
        points = [to_vec3(vertex.Point) for vertex in shape.Vertexes]
        if len(points) + len(mesh_points) > MAX_POINTS:
            return None
        points.extend(to_vec3(point) for point in mesh_points)
        return ShapeSample(tuple(points), _planar_faces(shape), _straight_edges(shape))
    except (*ERRORS, AttributeError):
        return None


def _planar_faces(shape: Any) -> tuple[tuple[Vec3, float], ...]:
    """``(normale, aire)`` des faces planes de ``shape``, hors faces dégénérées."""
    faces = []
    for face in shape.Faces:
        if isinstance(face.Surface, Part.Plane) and face.Area > 0.0:
            faces.append((to_vec3(face.Surface.Axis), float(face.Area)))
    return tuple(faces)


def _straight_edges(shape: Any) -> tuple[tuple[Vec3, float], ...]:
    """``(direction, longueur)`` des arêtes droites de ``shape``, hors arêtes dégénérées."""
    edges = []
    for edge in shape.Edges:
        if is_straight(edge) and edge.Length > 0.0 and len(edge.Vertexes) >= 2:
            direction = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
            edges.append((to_vec3(direction), float(edge.Length)))
    return tuple(edges)


def automatic_axes(shape: Any) -> tuple[Axes, bool]:
    """Repère automatique de ``shape`` : le repère d'équerre de plus petite boîte, ordonné (X =
    plus grande étendue, Z = plus petite). Le second résultat est vrai si la forme dépasse les
    plafonds de taille : les axes de la source (ordonnés d'après l'encombrement de la forme) sont
    alors rendus sans autre calcul, et l'appelant en avertit."""
    sample = sample_of(shape)
    if sample is None or sample.exceeds_limits:
        box = shape.optimalBoundingBox(False, False)
        extents = (box.XLength, box.YLength, box.ZLength)
        return ordered(Axes.identity(), extents), True
    axes = principal_axes(sample)
    return ordered(axes, measure_points(axes, sample.points).extents), False
