# SPDX-License-Identifier: LGPL-2.1-or-later
"""Repère d'une forme dessinée : axes principaux, mise en ordre et quarts de tour (A1 à A4).

Le repère d'une pièce en bois est X = longueur, Y = largeur, Z = épaisseur (``part_model``). Une
forme dessinée avec Sketcher / PartDesign n'a pas de tel repère : on cherche d'abord le repère
d'équerre dont la boîte englobante est la plus petite (:func:`principal_axes`), puis on l'ordonne
par étendue (:func:`ordered`). Python pur : ``features/`` fournit l'échantillon et lit le résultat.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from freecad.menuiserie.core._validation import MIN_DIMENSION_MM
from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Vec3
from freecad.menuiserie.core.shaped._candidates import frame_candidates
from freecad.menuiserie.core.shaped._sample import ShapeSample
from freecad.menuiserie.core.shaped._vec import added, cross, dot, is_finite, norm, scaled, unit
from freecad.menuiserie.core.snap import Turn

VOLUME_TIE: Final = 1e-3  # volumes égaux à 0,1 % près : l'ordre figé des candidats tranche
EXTENT_DIGITS: Final = 6  # arrondi (mm) des étendues pour départager les égalités


@dataclass(frozen=True)
class Axes:
    """Trois vecteurs unitaires orthogonaux direct (le produit vectoriel de x et y donne z).

    Les écarts de norme, d'orthogonalité et de sens inférieurs à ``ANGLE_TOLERANCE`` sont
    absorbés (les vecteurs sont renormalisés) ; au-delà, ``ValueError`` citant le champ.
    """

    x: Vec3
    y: Vec3
    z: Vec3

    def __post_init__(self) -> None:
        for field in ("x", "y", "z"):
            vector = getattr(self, field)
            if not is_finite(vector) or abs(norm(vector) - 1.0) > ANGLE_TOLERANCE:
                raise ValueError(f"{field} : vecteur unitaire attendu")
        for first, second in (("x", "y"), ("x", "z"), ("y", "z")):
            if abs(dot(getattr(self, first), getattr(self, second))) > ANGLE_TOLERANCE:
                raise ValueError(f"{second} : non orthogonal à {first}")
        if dot(cross(self.x, self.y), self.z) < 1.0 - ANGLE_TOLERANCE:
            raise ValueError("z : repère indirect")
        for field in ("x", "y", "z"):
            object.__setattr__(self, field, unit(getattr(self, field)))

    @classmethod
    def identity(cls) -> Axes:
        """Axes du document : X, Y, Z."""
        return cls(Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0), Vec3(0.0, 0.0, 1.0))

    def vectors(self) -> tuple[Vec3, Vec3, Vec3]:
        """Les trois axes, dans l'ordre X, Y, Z."""
        return (self.x, self.y, self.z)

    def coordinates(self, point: Vec3) -> Vec3:
        """Coordonnées de ``point`` le long de ces axes."""
        return Vec3(dot(point, self.x), dot(point, self.y), dot(point, self.z))


@dataclass(frozen=True)
class Bounds:
    """Boîte englobante d'un nuage de points dans un repère : étendues et coin minimal.

    ``extents`` = (L, l, e) le long de X, Y, Z du repère ; ``minimum`` = coordonnées du coin
    minimal le long de ces axes (l'origine de la forme dans le repère de la pièce est
    ``minimum`` : ``coordonnées locales = coordonnées - minimum``).
    """

    extents: tuple[float, float, float]
    minimum: Vec3


def measure_points(axes: Sequence[Vec3] | Axes, points: Sequence[Vec3]) -> Bounds:
    """Étendues et coin minimal de ``points`` dans le repère ``axes`` (au moins un point)."""
    if not points:
        raise ValueError("points : au moins un point est attendu")
    vectors = axes.vectors() if isinstance(axes, Axes) else tuple(axes)
    low = [math.inf] * 3
    high = [-math.inf] * 3
    for point in points:
        for index, vector in enumerate(vectors):
            value = dot(point, vector)
            low[index] = min(low[index], value)
            high[index] = max(high[index], value)
    extents = (high[0] - low[0], high[1] - low[1], high[2] - low[2])
    return Bounds(extents, Vec3(low[0], low[1], low[2]))


def _volume(vectors: Sequence[Vec3], points: Sequence[Vec3]) -> float:
    """Volume de la boîte englobante, étendues planchées à ``MIN_DIMENSION_MM`` (forme plate)."""
    extents = measure_points(vectors, points).extents
    return math.prod(max(extent, MIN_DIMENSION_MM) for extent in extents)


def principal_axes(sample: ShapeSample, source: Axes | None = None) -> Axes:
    """Repère d'équerre dont la boîte englobante des points a le plus petit volume (A2).

    Candidats, dans l'ordre : ``source`` (défaut : axes du document), puis pour chaque famille de
    faces planes parallèles (aire décroissante) sa normale avec chacune des arêtes droites de ces
    faces. À volume égal à 0,1 % près, le premier candidat l'emporte : résultat déterministe,
    indépendant de l'ordre des faces. Si l'échantillon dépasse un plafond de taille
    (``ShapeSample.exceeds_limits``), renvoie ``source`` sans rien calculer : à l'appelant d'en
    avertir. L'ordre X / Y / Z du résultat est ensuite fixé par :func:`ordered`.
    """
    base = source or Axes.identity()
    if sample.exceeds_limits:
        return base
    best, best_volume = base, _volume(base.vectors(), sample.points)
    for direction, normal in frame_candidates(sample, base.vectors()):
        vectors = (direction, cross(normal, direction), normal)
        volume = _volume(vectors, sample.points)
        if volume < best_volume * (1.0 - VOLUME_TIE):
            best, best_volume = Axes(*vectors), volume
    return best


def ordered(axes: Axes, extents: Sequence[float]) -> Axes:
    """Axes ordonnés par étendue (A3) : X = la plus grande, Z = la plus petite, Y déduit.

    ``extents`` : étendue de la forme le long de chacun des axes de ``axes``. À étendues égales
    (au micromètre près), l'ordre d'origine des axes est conservé. Le résultat est direct.
    """
    if len(extents) != 3 or not all(math.isfinite(e) and e >= 0.0 for e in extents):
        raise ValueError("extents : trois étendues finies et >= 0 attendues")
    rank = sorted(range(3), key=lambda i: (-round(extents[i], EXTENT_DIGITS), i))
    vectors = axes.vectors()
    long_axis, thin_axis = vectors[rank[0]], vectors[rank[2]]
    return Axes(long_axis, cross(thin_axis, long_axis), thin_axis)


def turned_axes(axes: Axes, turn: Turn) -> Axes:
    """Axes après un quart de tour direct autour de leur axe X, Y ou Z (A4, boutons de J6).

    Le quart de tour change quel axe de la forme est la longueur, la largeur ou l'épaisseur ;
    quatre quarts de tour autour du même axe reviennent au départ, et les trois rotations
    engendrent les 24 orientations d'équerre.
    """
    matrix = turn.matrix
    vectors = axes.vectors()
    columns = []
    for column in range(3):
        total = Vec3(0.0, 0.0, 0.0)
        for row in range(3):
            total = added(total, scaled(vectors[row], matrix[row][column]))
        columns.append(total)
    return Axes(*columns)
