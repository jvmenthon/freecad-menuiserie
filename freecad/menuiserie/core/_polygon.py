# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contrôles d'un prisme (polygone plan extrudé) sur des coordonnées brutes (J4f).

Module privé : seul :class:`~.geometry.Prism` l'utilise. Longueurs en mm.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

__all__ = ["check_prism"]

TOLERANCE: Final = 1e-9  # mm : sommets confondus, alignés ou hors du plan

Point3 = tuple[float, float, float]
Point2 = tuple[float, float]  # sommet projeté sur un plan de coordonnées


def _minus(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Point3, b: Point3) -> Point3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a: Point3) -> float:
    return math.sqrt(_dot(a, a))


def check_prism(points: Sequence[Point3], extrusion: Point3) -> None:
    """``ValueError`` si ``points`` ne forment pas un polygone plan simple d'au moins 3 sommets
    distincts non alignés, ou si ``extrusion`` est nulle ou parallèle à son plan."""
    if len(points) < 3:
        raise ValueError("prisme : au moins 3 sommets")
    normal = _polygon_normal(points)
    if any(abs(_dot(_minus(p, points[0]), normal)) > TOLERANCE for p in points):
        raise ValueError("prisme : sommets non coplanaires")
    if abs(_dot(extrusion, normal)) <= TOLERANCE:
        raise ValueError("prisme : extrusion nulle ou parallèle au plan du polygone")
    if not _is_simple(points, normal):
        raise ValueError("prisme : polygone qui se recoupe")


def _polygon_normal(points: Sequence[Point3]) -> Point3:
    """Normale unitaire du plan des sommets (``ValueError`` s'ils sont confondus ou alignés)."""
    for i, point in enumerate(points):
        if any(_norm(_minus(point, other)) <= TOLERANCE for other in points[i + 1 :]):
            raise ValueError("prisme : sommets confondus")
    origin = points[0]
    for i in range(1, len(points)):
        for j in range(i + 1, len(points)):
            normal = _cross(_minus(points[i], origin), _minus(points[j], origin))
            length = _norm(normal)
            if length > TOLERANCE:
                return (normal[0] / length, normal[1] / length, normal[2] / length)
    raise ValueError("prisme : sommets alignés")


def _is_simple(points: Sequence[Point3], normal: Point3) -> bool:
    """Vrai si aucun côté du polygone n'en coupe un autre (côtés voisins : pas de retour)."""
    drop = max(range(3), key=lambda i: abs(normal[i]))
    kept = [i for i in range(3) if i != drop]
    flat = [(p[kept[0]], p[kept[1]]) for p in points]
    count = len(flat)
    edges = [(flat[i], flat[(i + 1) % count]) for i in range(count)]
    for i in range(count):
        for j in range(i + 1, count):
            if j == i + 1 or (i == 0 and j == count - 1):
                pair = (edges[i], edges[j]) if j == i + 1 else (edges[j], edges[i])
                if _folds_back(*pair):
                    return False
            elif _segments_meet(*edges[i], *edges[j]):
                return False
    return True


def _orientation(a: Point2, b: Point2, c: Point2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point2, b: Point2, p: Point2) -> bool:
    """Vrai si ``p``, aligné sur [a, b], est entre ``a`` et ``b``."""
    return all(min(a[i], b[i]) - TOLERANCE <= p[i] <= max(a[i], b[i]) + TOLERANCE for i in range(2))


def _segments_meet(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Vrai si les segments [a, b] et [c, d] ont un point commun."""
    d1, d2 = _orientation(c, d, a), _orientation(c, d, b)
    d3, d4 = _orientation(a, b, c), _orientation(a, b, d)
    if min(abs(d1), abs(d2), abs(d3), abs(d4)) > TOLERANCE:
        return d1 * d2 < 0 and d3 * d4 < 0
    ends = ((c, d, a, d1), (c, d, b, d2), (a, b, c, d3), (a, b, d, d4))
    return any(abs(o) <= TOLERANCE and _on_segment(p, q, r) for p, q, r, o in ends)


def _folds_back(first: tuple[Point2, Point2], second: tuple[Point2, Point2]) -> bool:
    """Vrai si deux côtés voisins (``first`` puis ``second``) repartent l'un sur l'autre."""
    (a, b), (_b, c) = first, second
    collinear = abs(_orientation(a, b, c)) <= TOLERANCE
    backwards = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0
    return collinear and backwards
