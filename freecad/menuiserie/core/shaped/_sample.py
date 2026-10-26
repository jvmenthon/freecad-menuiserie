# SPDX-License-Identifier: LGPL-2.1-or-later
"""Échantillon d'une forme : ce que ``features/`` en extrait pour trouver son repère (PD-a).

Objet valeur gelé et validé. Une forme peut venir d'un STEP hostile (spécification § 4.9) : au-delà
des plafonds ci-dessous, l'échantillon n'est **pas** examiné élément par élément (aucune boucle sur
des données non bornées) ; il se déclare ``exceeds_limits`` et l'appelant retombe sur les axes de
la source avec un avertissement (:func:`.principal_axes` le fait de lui-même).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.shaped._vec import is_finite, norm

MAX_FACES: Final = 5_000
MAX_EDGES: Final = 5_000
MAX_POINTS: Final = 20_000
MAX_COORDINATE_MM: Final = 1.0e7

PlanarFace = tuple[Vec3, float]  # (normale non nulle, aire > 0)
StraightEdge = tuple[Vec3, float]  # (direction non nulle, longueur > 0)


def _check_vector(field: str, vector: Vec3, limit: float) -> None:
    if not is_finite(vector):
        raise ValueError(f"{field} : coordonnées non finies")
    if max(abs(vector.x), abs(vector.y), abs(vector.z)) > limit:
        raise ValueError(f"{field} : coordonnée hors limites")


def _check_oriented(field: str, items: tuple[tuple[Vec3, float], ...], label: str) -> None:
    for index, (direction, amount) in enumerate(items):
        name = f"{field}[{index}]"
        _check_vector(name, direction, math.inf)
        if norm(direction) == 0.0:
            raise ValueError(f"{name} : direction nulle")
        if not math.isfinite(amount) or amount <= 0.0:
            raise ValueError(f"{name} : {label} doit être finie et > 0")


@dataclass(frozen=True)
class ShapeSample:
    """Points (sommets et maillage grossier), faces planes et arêtes droites d'une forme.

    ``planar_faces`` : ``(normale, aire)`` ; ``straight_edges`` : ``(direction, longueur)``, en mm
    et mm². Les points sont exprimés dans le repère de la source. ``ValueError`` citant le champ
    si une valeur n'est pas finie, une normale ou une direction est nulle, une aire ou une
    longueur n'est pas > 0, ou s'il n'y a aucun point. Un échantillon qui dépasse un plafond
    (``MAX_FACES``, ``MAX_EDGES``, ``MAX_POINTS``) n'est pas validé élément par élément.
    """

    points: tuple[Vec3, ...]
    planar_faces: tuple[PlanarFace, ...] = ()
    straight_edges: tuple[StraightEdge, ...] = ()

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("points : au moins un point est attendu")
        if self.exceeds_limits:
            return
        for index, point in enumerate(self.points):
            _check_vector(f"points[{index}]", point, MAX_COORDINATE_MM)
        _check_oriented("planar_faces", self.planar_faces, "l'aire")
        _check_oriented("straight_edges", self.straight_edges, "la longueur")

    @property
    def exceeds_limits(self) -> bool:
        """Vrai si un plafond de taille est dépassé : le repère automatique n'est pas calculé."""
        return (
            len(self.points) > MAX_POINTS
            or len(self.planar_faces) > MAX_FACES
            or len(self.straight_edges) > MAX_EDGES
        )
