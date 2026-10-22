# SPDX-License-Identifier: LGPL-2.1-or-later
"""Outils géométriques de la lecture des éléments sélectionnés (J6d) : vecteurs ``App.Vector``,
formes lues par ``Part.getShape`` en coordonnées globales, côté extérieur d'une face.

Aucune forme n'est modifiée. Aucun import de ``FreeCADGui``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

import FreeCAD as App
import Part

from freecad.menuiserie.core.geometry import CONTACT_TOLERANCE_MM, Vec3
from freecad.menuiserie.features.freecad_types import DocumentObject
from freecad.menuiserie.features.picked import PickedElement

__all__ = [
    "ERRORS",
    "OFFSET_MM",
    "Request",
    "Vector",
    "element_shape",
    "global_shape",
    "is_straight",
    "nearest_on",
    "outward_normal",
    "owner_shape",
    "perpendicular",
    "to_vec3",
    "to_vector",
    "unit",
    "without",
]

OFFSET_MM: Final = 1.0  # décalage du point testé par ``isInside`` (côté extérieur d'une face)
ERRORS: Final = (RuntimeError, ValueError, TypeError, App.Base.FreeCADError, Part.OCCError)
Vector = Any


@dataclass(frozen=True)
class Request:
    """Point cliqué (``None`` : centre de masse) et direction vers l'observateur."""

    point: Vector | None
    toward_observer: Vector


def to_vec3(vector: Vector) -> Vec3:
    """Vecteur de ``core`` équivalent à ``vector`` (``App.Vector``)."""
    return Vec3(float(vector.x), float(vector.y), float(vector.z))


def to_vector(vec: Vec3) -> Vector:
    """``App.Vector`` équivalent à ``vec``."""
    return App.Vector(vec.x, vec.y, vec.z)


def unit(vector: Vector) -> Vector:
    """``vector`` normé."""
    length = vector.Length
    return App.Vector(vector.x / length, vector.y / length, vector.z / length)


def without(vector: Vector, axis: Vector) -> Vector:
    """``vector`` privé de sa composante selon ``axis`` (unitaire)."""
    return vector - axis * vector.dot(axis)


def perpendicular(axis: Vector) -> Vector:
    """Un vecteur unitaire perpendiculaire à ``axis`` (unitaire)."""
    hint = App.Vector(0, 0, 1) if abs(axis.z) < 0.9 else App.Vector(1, 0, 0)
    return unit(without(hint, axis))


def global_shape(obj: DocumentObject) -> Any:
    """Copie de la forme de ``obj`` placée dans le repère du document (y compris dans un Std
    Part), pour la comparer aux éléments sélectionnés."""
    shape = obj.Shape.copy()
    shape.Placement = obj.getGlobalPlacement()
    return shape


def element_shape(element: PickedElement) -> Any:
    """Sous-forme (face, arête, sommet) de ``element`` en coordonnées globales, ``None`` si
    nulle."""
    shape = Part.getShape(element.root, element.subname, needSubElement=True)
    return None if shape is None or shape.isNull() else shape


def owner_shape(element: PickedElement) -> Any:
    """Forme entière de l'objet qui porte ``element`` en coordonnées globales, ``None`` si nulle."""
    try:
        shape = Part.getShape(element.root, element.owner_subname)
    except ERRORS:
        return None
    return None if shape is None or shape.isNull() else shape


def nearest_on(face: Any, point: Vector) -> tuple[Vector, Vector]:
    """Point de ``face`` le plus proche de ``point`` et normale de la face (orientée par la
    forme) en ce point."""
    _distance, pairs, _info = face.distToShape(Part.Vertex(point))
    nearest = pairs[0][0]
    u, v = face.Surface.parameter(nearest)
    return nearest, face.normalAt(u, v)


def outward_normal(normal: Vector, point: Vector, owner: Any, toward_observer: Vector) -> Vector:
    """Normale tournée vers l'extérieur de la matière : ``isInside`` sur un point décalé de
    ``OFFSET_MM`` ; face sans solide (esquisse, plan) : côté de l'observateur."""
    direction = unit(normal)
    solids = owner.Solids if owner is not None else []
    if solids:
        probe = point + direction * OFFSET_MM
        inside = any(solid.isInside(probe, CONTACT_TOLERANCE_MM / 10, True) for solid in solids)
        return direction * -1.0 if inside else direction
    return direction if direction.dot(toward_observer) >= 0 else direction * -1.0


def is_straight(edge: Any) -> bool:
    """Vrai si ``edge`` est un segment de droite."""
    return isinstance(edge.Curve, (Part.Line, Part.LineSegment))
