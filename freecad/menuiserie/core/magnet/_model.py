# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets valeur du glissement à la souris (SM-a, ADR 0021) : rayon, flèches, guides, poignées.

Les boîtes et les guides de l'aimantation sont exprimés dans le **repère de la pièce** (mm) ;
les flèches et le rayon sont en coordonnées globales. Objets immuables, validés à la
construction (``ValueError`` citant le champ fautif).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core.geometry import ANGLE_TOLERANCE, Box, Vec3

THICKNESS_AXIS: Final = 2  # Z du repère de la pièce : poignée d'épaisseur du massif seulement (Q4)
MIN_SIZE_MM: Final = 1.0  # cote minimale d'une pièce redimensionnée (A6)


def _finite(owner: str, field: str, vector: Vec3) -> None:
    if not all(math.isfinite(value) for value in (vector.x, vector.y, vector.z)):
        raise ValueError(f"{owner}.{field} : coordonnées non finies")


def _length(vector: Vec3) -> float:
    return math.sqrt(vector.x**2 + vector.y**2 + vector.z**2)


def _check_axis(owner: str, axis: int) -> None:
    if axis not in (0, 1, 2):
        raise ValueError(f"{owner}.axis : 0 (X), 1 (Y) ou 2 (Z) attendu")


@dataclass(frozen=True)
class Ray:
    """Droite orientée (rayon de la souris ou axe d'une flèche) ; ``direction`` est normée."""

    origin: Vec3
    direction: Vec3

    def __post_init__(self) -> None:
        _finite("Ray", "origin", self.origin)
        _finite("Ray", "direction", self.direction)
        length = _length(self.direction)
        if length <= ANGLE_TOLERANCE:
            raise ValueError("Ray.direction : vecteur nul")
        d = self.direction
        object.__setattr__(self, "direction", Vec3(d.x / length, d.y / length, d.z / length))


@dataclass(frozen=True)
class Arrow:
    """Flèche d'un axe de la pièce : de ``start`` (centre) à ``end``, en coordonnées globales."""

    axis: int
    start: Vec3
    end: Vec3

    def __post_init__(self) -> None:
        _check_axis("Arrow", self.axis)
        _finite("Arrow", "start", self.start)
        _finite("Arrow", "end", self.end)

    def line(self) -> Ray:
        """Droite portée par la flèche, orientée dans le sens positif de l'axe."""
        s, e = self.start, self.end
        return Ray(s, Vec3(e.x - s.x, e.y - s.y, e.z - s.z))


class GuideKind(Enum):
    """Nature d'un guide : face plane, arête droite ou sommet d'un objet voisin."""

    PLANE = "plane"
    LINE = "line"
    POINT = "point"


class MagnetKind(Enum):
    """Nature d'une aimantation : normales opposées (contact) ou de même sens (affleurement)."""

    CONTACT = "contact"
    FLUSH = "flush"


@dataclass(frozen=True)
class Guide:
    """Élément voisin sur lequel la pièce s'aimante, dans le repère de la pièce.

    ``extent`` donne l'étendue du guide : aplatie sur ``axis`` pour un plan (``axis`` = axe de sa
    normale, ``sign`` = ±1 sens de la normale sortante), aplatie sur les deux autres axes pour une
    droite (``axis`` = son axe), réduite à un point pour un sommet (``axis`` = ``None``).
    """

    kind: GuideKind
    extent: Box
    axis: int | None = None
    sign: int = 0

    def __post_init__(self) -> None:
        flat = {i for i in range(3) if self.extent.size(i) <= ANGLE_TOLERANCE}
        if self.kind is GuideKind.POINT:
            self._check(self.axis is None and self.sign == 0, "un point n'a ni axe ni sens")
            self._check(flat == {0, 1, 2}, "un point a une étendue nulle")
            return
        if self.axis is None:
            raise ValueError("Guide.axis : axe obligatoire pour un plan ou une droite")
        _check_axis("Guide", self.axis)
        if self.kind is GuideKind.PLANE:
            self._check(self.sign in (-1, 1), "un plan a un sens +1 ou -1")
            self._check(self.axis in flat, "un plan est aplati sur son axe")
        else:
            self._check(self.sign == 0, "une droite n'a pas de sens")
            self._check(flat >= {0, 1, 2} - {self.axis}, "une droite est aplatie hors de son axe")

    def _check(self, condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(f"Guide : {message}")

    def position(self, axis: int) -> float:
        """Position du guide sur l'axe ``axis`` (début de son étendue)."""
        return self.extent.lo(axis)

    def magnetic_axes(self) -> tuple[int, ...]:
        """Axes sur lesquels il aimante : son axe (plan), les deux autres (droite), tous (point)."""
        if self.kind is GuideKind.PLANE:
            return () if self.axis is None else (self.axis,)
        if self.kind is GuideKind.LINE:
            return tuple(i for i in range(3) if i != self.axis)
        return (0, 1, 2)


@dataclass(frozen=True)
class MagnetHit:
    """Aimantation obtenue sur un axe, pour l'affichage du guide et de la face collée."""

    axis: int
    guide: int  # indice dans la liste de guides donnée
    at_end: bool  # face de fin (True) ou de début (False) de la boîte
    kind: MagnetKind
    position: float  # position de la face après aimantation, sur ``axis``


@dataclass(frozen=True)
class Handle:
    """Poignée de redimensionnement : face de début ou de fin d'un axe de la pièce."""

    axis: int
    at_end: bool

    def __post_init__(self) -> None:
        _check_axis("Handle", self.axis)


@dataclass(frozen=True)
class DragResult:
    """Déplacement aimanté (repère de la pièce) et aimantations obtenues, au plus une par axe."""

    delta: Vec3
    hits: tuple[MagnetHit, ...] = ()


@dataclass(frozen=True)
class ResizeResult:
    """Redimensionnement : cote nouvelle sur l'axe de la poignée, translation de l'origine
    (non nulle pour une poignée de début) et aimantation éventuelle."""

    size: float
    origin_shift: Vec3
    hit: MagnetHit | None = None


@dataclass(frozen=True)
class PixelTarget:
    """Cible saisissable à l'écran, en pixels : poignée (``end`` absent) ou flèche (segment)."""

    key: str
    start: tuple[float, float]
    end: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("PixelTarget.key : clé vide")
        points = (self.start,) if self.end is None else (self.start, self.end)
        if not all(math.isfinite(v) for point in points for v in point):
            raise ValueError("PixelTarget : coordonnées non finies")

    @property
    def is_handle(self) -> bool:
        """Vrai pour une poignée (un point), faux pour une flèche (un segment)."""
        return self.end is None
