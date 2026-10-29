# SPDX-License-Identifier: LGPL-2.1-or-later
"""Anneaux de rotation autour de la pièce : géométrie et angle parcouru (A4, ADR 0025)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from freecad.menuiserie.core.magnet import Ray
from freecad.menuiserie.core.rotation._turn import check_axis
from freecad.menuiserie.core.snap._vec import cross, dot, is_finite, norm, sub

MIN_RING_RADIUS_MM: Final = 20.0
MAX_RING_RADIUS_MM: Final = 10_000.0  # plafond de sécurité : pièce démesurée (ADR 0025)
EDGE_ON_DEGREES: Final = 5.0  # en dessous, le rayon rase le plan de l'anneau
_MARGIN: Final = 1.15
_SIN_EDGE_ON: Final = math.sin(math.radians(EDGE_ON_DEGREES))


@dataclass(frozen=True)
class Ring:
    """Cercle de centre ``center`` (mm), de normale ``normal`` (axe fixe du document, unitaire)."""

    center: Vec3
    normal: Vec3
    radius: float
    axis: int

    def __post_init__(self) -> None:
        check_axis("Ring", self.axis)
        if not (is_finite(self.center) and is_finite(self.normal)):
            raise ValueError("Ring : coordonnées non finies")
        if not math.isfinite(self.radius) or self.radius <= 0:
            raise ValueError("Ring.radius : rayon strictement positif attendu")


def ring_of(box: Box, rotation: RigidTransform, axis: int) -> Ring:
    """Anneau autour de l'axe fixe ``axis`` du document, centré sur le centre de ``box``.

    ``box`` est la boîte de la brute dans le repère de la pièce et ``rotation`` son placement
    (pièce → document). Rayon : 1,15 fois la demi-diagonale de ``box``, borné à [20 mm, 10 m].
    """
    check_axis("ring_of", axis)
    local = Vec3(box.center(0), box.center(1), box.center(2))
    half_diagonal = norm(Vec3(box.size(0), box.size(1), box.size(2))) / 2
    radius = min(max(_MARGIN * half_diagonal, MIN_RING_RADIUS_MM), MAX_RING_RADIUS_MM)
    normal = Vec3(0.0, 0.0, 0.0).with_component(axis, 1.0)
    return Ring(rotation.apply(local), normal, radius, axis)


def _plane_point(ray: Ray, ring: Ring) -> Vec3 | None:
    """Point où le rayon coupe le plan de l'anneau ; ``None`` si le rayon rase ce plan (moins
    de 5°) ou si le plan est derrière l'origine."""
    slope = dot(ray.direction, ring.normal)
    if abs(slope) < _SIN_EDGE_ON:
        return None
    ahead = dot(sub(ring.center, ray.origin), ring.normal) / slope
    if ahead < 0:
        return None
    d = ray.direction
    o = ray.origin
    return Vec3(o.x + d.x * ahead, o.y + d.y * ahead, o.z + d.z * ahead)


def ring_hit(ray: Ray, ring: Ring, tolerance: float) -> bool:
    """Vrai si le rayon touche l'anneau à ``tolerance`` mm près (dans le plan de l'anneau).

    Faux pour un anneau vu par la tranche (moins de 5° : voir :func:`ring_angle`).
    """
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("ring_hit.tolerance : tolérance finie positive attendue")
    point = _plane_point(ray, ring)
    if point is None:
        return False
    return abs(norm(sub(point, ring.center)) - ring.radius) <= tolerance


def ring_angle(ray: Ray, ring: Ring, start: Ray) -> float | None:
    """Angle signé (degrés, sens direct autour de la normale, dans ]-180, 180]) entre les points
    où ``start`` (rayon au début du geste) et ``ray`` coupent le plan de l'anneau.

    ``None`` si l'un des deux rayons est à moins de 5° du plan, ou passe par le centre.
    """
    first = _plane_point(start, ring)
    last = _plane_point(ray, ring)
    if first is None or last is None:
        return None
    u = sub(first, ring.center)
    v = sub(last, ring.center)
    if norm(u) <= 1e-9 or norm(v) <= 1e-9:
        return None
    return math.degrees(math.atan2(dot(ring.normal, cross(u, v)), dot(u, v))) + 0.0
