# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repères candidats tirés des faces planes et des arêtes droites d'une forme (critère A2).

Chaque candidat est un couple ``(x, normale)`` de vecteurs unitaires orthogonaux ; le repère
complet s'en déduit (y = normale puis x, produit vectoriel). L'ordre est figé, indépendant de
l'ordre des faces :
familles de faces parallèles par aire décroissante, puis arêtes de la famille par longueur
décroissante. Le nombre de candidats est borné (``MAX_FAMILIES`` x ``MAX_DIRECTIONS``).
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.shaped._sample import ShapeSample, StraightEdge
from freecad.menuiserie.core.shaped._vec import added, dot, scaled, subtracted, unit

MAX_FAMILIES: Final = 6
MAX_DIRECTIONS: Final = 6
KEY_DIGITS: Final = 5  # arrondi du regroupement des directions parallèles
PERPENDICULAR_TOLERANCE: Final = 1e-3  # cosinus toléré entre une arête et la normale de sa face

Key = tuple[float, float, float]


def _canonical(vector: Vec3) -> tuple[Vec3, Key]:
    """Vecteur unitaire de signe fixé (première coordonnée non nulle > 0) et sa clé arrondie."""
    direction = unit(vector)
    if direction is None:
        raise ValueError("direction nulle")  # exclu par la validation de ShapeSample
    key = tuple(round(c, KEY_DIGITS) + 0.0 for c in (direction.x, direction.y, direction.z))
    if next((c for c in key if c != 0.0), 1.0) < 0.0:
        direction, key = scaled(direction, -1.0), tuple(-c + 0.0 for c in key)
    return direction, (key[0], key[1], key[2])


def face_families(faces: Sequence[tuple[Vec3, float]]) -> list[tuple[Vec3, float]]:
    """Familles de faces parallèles : ``(normale unitaire, aire totale)``, aire décroissante."""
    keyed = sorted(((_canonical(n), area) for n, area in faces), key=lambda t: (t[0][1], t[1]))
    sums: dict[Key, tuple[Vec3, float]] = {}
    for (normal, key), area in keyed:
        total, total_area = sums.get(key, (Vec3(0.0, 0.0, 0.0), 0.0))
        sums[key] = (added(total, scaled(normal, area)), total_area + area)
    families = [(unit(total), area, key) for key, (total, area) in sums.items()]
    families.sort(key=lambda f: (-f[1], f[2]))
    return [(normal, area) for normal, area, _ in families if normal is not None]


def edge_directions(edges: Sequence[StraightEdge]) -> list[Vec3]:
    """Directions d'arêtes distinctes (signe fixé), longueur cumulée décroissante."""
    lengths: dict[Key, tuple[Vec3, float]] = {}
    for direction, length in edges:
        vector, key = _canonical(direction)
        lengths[key] = (vector, lengths.get(key, (vector, 0.0))[1] + length)
    ordered = sorted(lengths.items(), key=lambda item: (-item[1][1], item[0]))
    return [vector for _, (vector, _) in ordered]


def _in_plane(vector: Vec3, normal: Vec3) -> Vec3 | None:
    """Projection de ``vector`` dans le plan de normale ``normal``, normée (ou ``None``)."""
    return unit(subtracted(vector, scaled(normal, dot(vector, normal))), PERPENDICULAR_TOLERANCE)


def _face_directions(
    normal: Vec3, edges: Sequence[Vec3], source_axes: Sequence[Vec3]
) -> list[Vec3]:
    """Directions du plan de la face : ses arêtes, à défaut les axes de la source projetés."""
    found = [d for d in edges if abs(dot(d, normal)) <= PERPENDICULAR_TOLERANCE]
    projected = [_in_plane(d, normal) for d in found]
    directions = [d for d in projected if d is not None][:MAX_DIRECTIONS]
    if directions:
        return directions
    fallback = [_in_plane(axis, normal) for axis in source_axes]
    return [d for d in fallback if d is not None][:1]


def frame_candidates(
    sample: ShapeSample, source_axes: Sequence[Vec3]
) -> Iterator[tuple[Vec3, Vec3]]:
    """Couples ``(x, normale)`` candidats, dans l'ordre figé du critère A2."""
    edges = edge_directions(sample.straight_edges)
    for normal, _ in face_families(sample.planar_faces)[:MAX_FAMILIES]:
        for direction in _face_directions(normal, edges, source_axes):
            yield direction, normal
