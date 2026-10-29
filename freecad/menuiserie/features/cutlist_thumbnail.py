# SPDX-License-Identifier: LGPL-2.1-or-later
"""Miniatures de la liste de débit : forme usinée de la première pièce de chaque groupe (J2, § 10,
demande de jv du 2026-10-22).

Lecture seule, sans rendu 3D ni écran : la forme usinée (tenons, queues d'aronde, rainures…) est
discrétisée par OpenCascade (``Face.tessellate``, ``Edge.discretize``), puis projetée en isométrie
et dessinée en SVG par ``core.cutlist`` (module pur). Une pièce en bois montre sa propre forme
dans son repère (L, l, e), ou celle de sa pièce usinée. Repli : boîte de débit L x l x e quand la
pièce n'est plus dans le document, n'a pas de forme usinée utilisable (absente, invalide, à
recalculer) ou que la forme est trop fine pour une miniature. Une miniature par groupe (ligne),
clé ``CutLine.source``, couleur du matériau.
"""

from __future__ import annotations

from typing import Any, Final

from freecad.menuiserie.core.cutlist import (
    DEFAULT_COLOR,
    CutLine,
    CutList,
    Point3,
    ThumbFace,
    box_faces,
    thumbnail_svg,
)
from freecad.menuiserie.features.cutlist_parts import local_shape
from freecad.menuiserie.features.freecad_types import Document, DocumentObject
from freecad.menuiserie.features.library import get_library
from freecad.menuiserie.features.machined_part import machined_part_of
from freecad.menuiserie.features.shaped_part import is_shaped_part

__all__ = ["MAX_TRIANGLES", "shape_faces", "thumbnail_of", "thumbnails_of"]

MAX_TRIANGLES: Final = 20_000  # au-delà, la forme est trop fine : repli sur la boîte
_DEFLECTION_RATIO: Final = 150.0  # écart de discrétisation : diagonale / 150 (miniature de 120 px)
_MIN_DEFLECTION_MM: Final = 0.01
# Erreurs d'OpenCascade (``Part.OCCError`` est une ``RuntimeError``) et de forme dégénérée.
_SHAPE_ERRORS: Final = (RuntimeError, ValueError, TypeError, AttributeError, ArithmeticError)


class TooFineError(ValueError):
    """La forme donne trop de triangles pour une miniature."""


def _point(vector: Any) -> Point3:
    return (float(vector.x), float(vector.y), float(vector.z))


def _edge_points(edge: Any, deflection: float) -> tuple[Point3, ...]:
    """Polyligne d'une arête, vide si elle est dégénérée (arête de couture, point)."""
    try:
        return tuple(_point(p) for p in edge.discretize(Deflection=deflection))
    except _SHAPE_ERRORS:
        return ()


def _face(face: Any, deflection: float) -> ThumbFace:
    vertices, indices = face.tessellate(deflection)
    points = [_point(vertex) for vertex in vertices]
    triangles = tuple((points[a], points[b], points[c]) for a, b, c in indices)
    edges = tuple(p for p in (_edge_points(edge, deflection) for edge in face.Edges) if len(p) > 1)
    return ThumbFace(triangles, edges)


def shape_faces(shape: Any) -> tuple[ThumbFace, ...]:
    """Faces discrétisées de ``shape`` (``Part.Shape`` dans le repère de la pièce), triangles
    orientés vers l'extérieur de la matière. ``ValueError`` si la forme donne plus de
    ``MAX_TRIANGLES`` triangles ; les erreurs d'OpenCascade (forme invalide) sont celles de
    ``RuntimeError`` et de ses proches."""
    deflection = max(float(shape.BoundBox.DiagonalLength) / _DEFLECTION_RATIO, _MIN_DEFLECTION_MM)
    faces: list[ThumbFace] = []
    count = 0
    for face in shape.Faces:
        built = _face(face, deflection)
        count += len(built.triangles)
        if count > MAX_TRIANGLES:
            raise TooFineError(count)
        faces.append(built)
    return tuple(faces)


def _color_of(line: CutLine) -> tuple[int, int, int]:
    """Couleur du matériau de la ligne dans la bibliothèque, ``DEFAULT_COLOR`` s'il est inconnu."""
    material = get_library().find(line.material_id)
    return DEFAULT_COLOR if material is None else material.color


def _shape_holder(blank: DocumentObject | None) -> DocumentObject | None:
    """Objet dont la forme est dessinée : la pièce usinée de ``blank`` si elle existe, sinon la
    pièce en bois elle-même (sa forme est déjà dans son repère L, l, e, ADR 0020) ; ``None`` pour
    une brute sans pièce usinée, qui reste une boîte."""
    if blank is None:
        return None
    machined = machined_part_of(blank)
    return machined if machined is not None else (blank if is_shaped_part(blank) else None)


def _machined_faces(doc: Document, line: CutLine) -> tuple[ThumbFace, ...] | None:
    """Faces de la forme de la première pièce de ``line`` (usinée, ou celle d'une pièce en bois),
    ``None`` sans forme utilisable (pièce absente, brute jamais usinée, forme invalide ou à
    recalculer, ou trop fine)."""
    blank: DocumentObject | None = doc.getObject(line.source) if line.source else None
    holder = _shape_holder(blank)
    shape = None if holder is None else local_shape(holder)
    if shape is None:
        return None
    try:
        return shape_faces(shape)
    except (*_SHAPE_ERRORS, TooFineError):
        return None


def thumbnail_of(doc: Document, line: CutLine) -> str:
    """SVG isométrique de la pièce de ``line`` : sa forme usinée, ou celle de la pièce en bois dans
    son repère (L, l, e), ou à défaut sa boîte (cotes de débit L x l x e ; cotes finies, donc
    l'encombrement, pour une pièce en bois dont la forme est illisible)."""
    box = line.finished if line.shape is not None else line.rough
    faces = _machined_faces(doc, line)
    if not faces:
        faces = box_faces(box.length, box.width, box.thickness)
    return thumbnail_svg(faces, _color_of(line))


def thumbnails_of(doc: Document, cut_list: CutList) -> dict[str, str]:
    """Miniature SVG de chaque ligne de ``cut_list`` (clé ``CutLine.source``), prête pour
    ``core.cutlist.to_html``. Lecture seule ; les lignes sans clé n'ont pas de miniature."""
    return {line.source: thumbnail_of(doc, line) for line in cut_list.lines if line.source}
