# SPDX-License-Identifier: LGPL-2.1-or-later
"""Géométrie pure des anneaux de rotation dans la vue 3D (RO-d, ADR 0025, spécification § 4.3).

Les règles de l'anneau (centre, rayon, touche, angle parcouru) viennent de ``core/rotation`` ;
ce module y ajoute ce que la vue demande : clés des anneaux, polylignes et secteur à dessiner,
rayon de la souris remis devant le plan de l'anneau, angle cumulé sur plusieurs tours et son
texte. Aucun import de FreeCAD, de Qt ni de pivy.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from freecad.menuiserie.core.geometry import Box, RigidTransform, Vec3
from freecad.menuiserie.core.magnet import Ray
from freecad.menuiserie.core.rotation import Ring, plane_point, ring_of

__all__ = [
    "MIN_RING_SCREEN_PX",
    "RING_PX",
    "RING_SEGMENTS",
    "Sweep",
    "advance",
    "angle_label",
    "build_rings",
    "circle",
    "ring_axis",
    "ring_basis",
    "ring_key",
    "ring_ray",
    "ring_under",
    "screen_distance",
    "sector",
]

RING_PX: Final = 8.0  # tolérance de saisie d'un anneau à l'écran, en pixels
MIN_RING_SCREEN_PX: Final = 2 * RING_PX  # en dessous, l'anneau est trop petit pour être proposé
PICK_SEGMENTS: Final = 48  # côtés du cercle projeté pour mesurer la distance à l'écran
RING_SEGMENTS: Final = 96  # côtés du cercle dessiné
_FAR: Final = 1000.0  # le rayon est reculé de ce nombre de rayons d'anneau devant le plan
_FULL_TURN: Final = 360.0

Point = tuple[float, float]


def ring_key(axis: int) -> str:
    """Clé de l'anneau de l'axe ``axis`` (0, 1 ou 2)."""
    return f"ring{axis}"


def ring_axis(key: str | None) -> int | None:
    """Axe (0, 1 ou 2) de l'anneau désigné par ``key``, ``None`` si ``key`` n'est pas un anneau
    (flèche, poignée, absente)."""
    if key is not None and key.startswith("ring") and key[4:] in ("0", "1", "2"):
        return int(key[4:])
    return None


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def _plus(a: Vec3, b: Vec3, factor: float = 1.0) -> Vec3:
    return Vec3(a.x + b.x * factor, a.y + b.y * factor, a.z + b.z * factor)


def _length(a: Vec3) -> float:
    return math.sqrt(a.x**2 + a.y**2 + a.z**2)


def _unit(a: Vec3) -> Vec3:
    length = _length(a)
    return Vec3(a.x / length, a.y / length, a.z / length)


def ring_basis(normal: Vec3) -> tuple[Vec3, Vec3]:
    """Deux vecteurs unitaires ``(u, v)`` du plan de normale ``normal`` (unitaire), tels que
    ``u x v = normal`` : l'angle positif va de ``u`` vers ``v`` (sens direct autour de la normale,
    celui de ``ring_angle``)."""
    helper = Vec3(1.0, 0.0, 0.0) if abs(normal.x) < 0.9 else Vec3(0.0, 1.0, 0.0)
    u = _unit(_cross(normal, helper))
    return u, _cross(normal, u)


def _turned(vector: Vec3, normal: Vec3, degrees: float) -> Vec3:
    """``vector`` (perpendiculaire à ``normal``) tourné de ``degrees`` autour de ``normal``."""
    angle = math.radians(degrees)
    return _plus(
        Vec3(vector.x * math.cos(angle), vector.y * math.cos(angle), vector.z * math.cos(angle)),
        _cross(normal, vector),
        math.sin(angle),
    )


def circle(ring: Ring, segments: int = RING_SEGMENTS) -> tuple[Vec3, ...]:
    """Polyligne fermée (``segments`` côtés, premier point répété) du cercle de l'anneau."""
    u, _ = ring_basis(ring.normal)
    start = Vec3(u.x * ring.radius, u.y * ring.radius, u.z * ring.radius)
    step = _FULL_TURN / segments
    return tuple(
        _plus(ring.center, _turned(start, ring.normal, step * i)) for i in range(segments + 1)
    )


def build_rings(box: Box, local: RigidTransform, container: RigidTransform) -> tuple[Ring, ...]:
    """Les trois anneaux d'une pièce de boîte ``box`` (repère de la pièce), de placement
    ``local`` (pièce → repère de son conteneur) ; ``container`` (conteneur → document, l'identité
    hors conteneur) les porte dans le document : les anneaux suivent les axes du conteneur (B5)."""
    rings = []
    for axis in range(3):
        ring = ring_of(box, local, axis)
        rings.append(
            Ring(container.apply(ring.center), container.rotate(ring.normal), ring.radius, axis)
        )
    return tuple(rings)


def ring_ray(ray: Ray, ring: Ring) -> Ray:
    """Même droite que ``ray``, son origine reculée jusqu'avant le plan de l'anneau.

    ``core/rotation`` ignore un plan situé derrière l'origine du rayon ; or en caméra orthogonale
    l'origine est un point du plan focal, qui peut se trouver au-delà d'un anneau.
    """
    d = ray.direction
    offset = Vec3(
        ring.center.x - ray.origin.x, ring.center.y - ray.origin.y, ring.center.z - ray.origin.z
    )
    ahead = offset.x * d.x + offset.y * d.y + offset.z * d.z
    return Ray(_plus(ray.origin, d, min(0.0, ahead) - _FAR * ring.radius), d)


def _segment_distance(p: Point, a: Point, b: Point) -> float:
    """Distance (pixels) du point ``p`` au segment ``a`` - ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = (
        0.0
        if length2 == 0
        else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    )
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def screen_distance(ring: Ring, project: Callable[[Vec3], Point], point: Point) -> float | None:
    """Distance (pixels) entre le pixel ``point`` et l'ellipse que dessine l'anneau à l'écran ;
    ``None`` si son rayon à l'écran (demi-grand axe) est inférieur à :data:`MIN_RING_SCREEN_PX` :
    dézoomé, un anneau minuscule ne doit pas happer les clics sur la pièce."""
    outline = [project(p) for p in circle(ring, PICK_SEGMENTS)]
    cx, cy = project(ring.center)
    if max(math.hypot(x - cx, y - cy) for x, y in outline) < MIN_RING_SCREEN_PX:
        return None
    return min(_segment_distance(point, a, b) for a, b in pairwise(outline))


def ring_under(
    rings: tuple[Ring, ...],
    ray: Ray,
    project: Callable[[Vec3], Point],
    point: Point,
    tolerance_px: float = RING_PX,
) -> str | None:
    """Clé de l'anneau (X, Y, Z) le plus proche du pixel ``point`` à ``tolerance_px`` pixels près,
    mesurés sur l'ellipse projetée (la bande garde la même largeur vue de biais) ; ``ray`` est le
    rayon de la souris. Pas d'anneau vu par la tranche (D5) ni plus petit que
    :data:`MIN_RING_SCREEN_PX` à l'écran."""
    best: tuple[float, str] | None = None
    for ring in rings:
        if plane_point(ring_ray(ray, ring), ring) is None:
            continue
        gap = screen_distance(ring, project, point)
        if gap is not None and gap <= tolerance_px and (best is None or gap < best[0]):
            best = (gap, ring_key(ring.axis))
    return None if best is None else best[1]


def advance(total: float, last: float, now: float) -> float:
    """Angle cumulé (degrés) après que l'angle lu est passé de ``last`` à ``now`` (chacun dans
    ]-180, 180]) : le plus petit saut compte, donc le geste peut dépasser un demi-tour."""
    delta = now - last
    return total + delta - _FULL_TURN * round(delta / _FULL_TURN)


def angle_label(angle: float) -> str:
    """Texte de l'angle affiché près de la souris : virgule décimale, un seul chiffre après elle
    (« 37,5° », « 15° », « -30° »)."""
    text = f"{abs(angle):.1f}".removesuffix(".0")
    sign = "-" if angle < 0 and text != "0" else ""
    return f"{sign}{text.replace('.', ',')}°"


@dataclass(frozen=True)
class Sweep:
    """Ce qu'un geste de rotation montre : l'anneau tourné, le vecteur ``start`` (du centre au
    point saisi, dans le plan de l'anneau), l'angle ``angle`` parcouru (degrés, aimanté ou libre)
    et le point ``anchor`` près duquel écrire cet angle."""

    ring: Ring
    start: Vec3
    angle: float
    anchor: Vec3


def sector(sweep: Sweep) -> tuple[tuple[Vec3, ...], ...]:
    """Secteur parcouru, en triangles (centre, deux points de l'anneau) ; vide si l'angle est
    nul. Au-delà d'un tour, un tour plein."""
    ring = sweep.ring
    angle = max(-_FULL_TURN, min(_FULL_TURN, sweep.angle))
    if abs(angle) < 1e-9:
        return ()
    factor = ring.radius / _length(sweep.start)
    start = Vec3(sweep.start.x * factor, sweep.start.y * factor, sweep.start.z * factor)
    count = max(1, math.ceil(abs(angle) / (_FULL_TURN / RING_SEGMENTS)))
    edge = [
        _plus(ring.center, _turned(start, ring.normal, angle * i / count)) for i in range(count + 1)
    ]
    return tuple((ring.center, edge[i], edge[i + 1]) for i in range(count))
