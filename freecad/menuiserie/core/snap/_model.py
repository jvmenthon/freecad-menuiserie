# SPDX-License-Identifier: LGPL-2.1-or-later
"""Objets valeur de l'accrochage (J6a) : repère, cibles, orientation, notices et résultat.

Tout est exprimé en coordonnées globales du document (mm). Les objets sont immuables et validés
à la construction : ``ValueError`` citant le champ fautif.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final

from freecad.menuiserie.core._validation import MAX_DIMENSION_MM, MIN_DIMENSION_MM
from freecad.menuiserie.core.geometry import (
    ANGLE_TOLERANCE,
    CONTACT_TOLERANCE_MM,
    Matrix3,
    RigidTransform,
    Vec3,
)
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP
from freecad.menuiserie.core.part_model import Dimensions
from freecad.menuiserie.core.snap._vec import cross, dot, is_finite, norm, scale, sub, unit

_ZERO: Final = Vec3(0.0, 0.0, 0.0)
_TILTS: Final = 3
_PIVOTS: Final = 4
# Quart de tour autour de Z, et permutation circulaire des axes (Y vers Z, Z vers X, X vers Y) :
# la bascule « à plat → sur chant → en bout » est la puissance 0, 1 ou 2 de cette dernière.
QUARTER_TURN_Z: Final[Matrix3] = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
AXIS_CYCLE: Final[Matrix3] = ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
IDENTITY: Final[Matrix3] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def product(left: Matrix3, right: Matrix3) -> Matrix3:
    """Produit de deux rotations ``left · right``."""
    composed = RigidTransform(left, _ZERO).compose(RigidTransform(right, _ZERO))
    return composed.rotation


def _check_vector(owner: str, field: str, vector: Vec3) -> None:
    if not is_finite(vector):
        raise ValueError(f"{owner}.{field} : coordonnées non finies")


def _unit_axis(field: str, vector: Vec3) -> Vec3:
    _check_vector("Frame", field, vector)
    if abs(norm(vector) - 1.0) > ANGLE_TOLERANCE:
        raise ValueError(f"Frame.{field} : le vecteur doit être unitaire")
    return vector


@dataclass(frozen=True)
class Frame:
    """Repère orthonormé direct ; ``z`` est la normale sortante de la matière.

    Les axes sont renormalisés à la construction (Gram-Schmidt) : ``z = x ∧ y`` exactement.
    """

    origin: Vec3
    x: Vec3
    y: Vec3
    z: Vec3

    def __post_init__(self) -> None:
        _check_vector("Frame", "origin", self.origin)
        x, y, z = _unit_axis("x", self.x), _unit_axis("y", self.y), _unit_axis("z", self.z)
        if max(abs(dot(x, y)), abs(dot(y, z)), abs(dot(x, z))) > ANGLE_TOLERANCE:
            raise ValueError("Frame : les axes x, y et z doivent être orthogonaux")
        if dot(cross(x, y), z) < 1.0 - ANGLE_TOLERANCE:
            raise ValueError("Frame.z : le repère doit être direct (z = x ∧ y)")
        y = unit(sub(y, scale(x, dot(x, y))))
        object.__setattr__(self, "x", unit(x))
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "z", cross(self.x, y))

    def to_transform(self) -> RigidTransform:
        """Transformation repère de l'élément → repère global."""
        x, y, z = self.x, self.y, self.z
        return RigidTransform(((x.x, y.x, z.x), (x.y, y.y, z.y), (x.z, y.z, z.z)), self.origin)


def _check_name(owner: str, name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{owner}.name : nom vide")


@dataclass(frozen=True)
class FaceTarget:
    """Face choisie : repère d'appui au coin du rectangle englobant le plus proche du clic."""

    name: str
    frame: Frame
    extent: tuple[float, float]
    planar: bool

    def __post_init__(self) -> None:
        _check_name("FaceTarget", self.name)
        if len(self.extent) != 2 or not all(math.isfinite(v) and v >= 0 for v in self.extent):
            raise ValueError("FaceTarget.extent : deux étendues finies et positives attendues")
        if self.planar and not all(v > 0 for v in self.extent):
            raise ValueError("FaceTarget.extent : une face plane a une étendue non nulle")


@dataclass(frozen=True)
class EdgeTarget:
    """Arête choisie, avec sa face d'appui (normale sortante ``support``, ``inward``)."""

    name: str
    start: Vec3
    end: Vec3
    support: Vec3
    inward: Vec3

    def __post_init__(self) -> None:
        _check_name("EdgeTarget", self.name)
        for field in ("start", "end", "support", "inward"):
            _check_vector("EdgeTarget", field, getattr(self, field))
        direction = sub(self.end, self.start)
        if norm(direction) <= CONTACT_TOLERANCE_MM:
            raise ValueError("EdgeTarget.end : extrémités confondues")
        support, inward = self._unit("support", self.support), self._unit("inward", self.inward)
        axis = unit(direction)
        if abs(dot(support, axis)) > ANGLE_TOLERANCE:
            raise ValueError("EdgeTarget.support : doit être perpendiculaire à l'arête")
        if abs(dot(inward, axis)) > ANGLE_TOLERANCE:
            raise ValueError("EdgeTarget.inward : doit être perpendiculaire à l'arête")
        if abs(dot(inward, support)) > ANGLE_TOLERANCE:
            raise ValueError("EdgeTarget.inward : doit être perpendiculaire à support")
        object.__setattr__(self, "support", support)
        object.__setattr__(self, "inward", inward)

    @staticmethod
    def _unit(field: str, vector: Vec3) -> Vec3:
        if abs(norm(vector) - 1.0) > ANGLE_TOLERANCE:
            raise ValueError(f"EdgeTarget.{field} : le vecteur doit être unitaire")
        return unit(vector)


@dataclass(frozen=True)
class VertexTarget:
    """Sommet choisi ; ``axes`` est le repère de l'objet sélectionné (son origine est ignorée)."""

    name: str
    point: Vec3
    axes: Frame

    def __post_init__(self) -> None:
        _check_name("VertexTarget", self.name)
        _check_vector("VertexTarget", "point", self.point)


Target = FaceTarget | EdgeTarget | VertexTarget


class Turn(Enum):
    """Rotation demandée par un bouton du panneau."""

    PIVOT = "Pivot"  # quart de tour autour de z du repère d'appui
    TILT = "Tilt"  # à plat → sur chant → en bout → à plat


@dataclass(frozen=True)
class Orientation:
    """Orientation de la pièce dans le repère d'appui.

    ``tilt`` : 0 à plat (épaisseur selon z), 1 sur chant (largeur selon z), 2 en bout (longueur
    selon z). ``pivot`` : nombre de quarts de tour autour de z, de 0 à 3.
    """

    tilt: int = 0
    pivot: int = 0

    def __post_init__(self) -> None:
        for field, value, count in (("tilt", self.tilt, _TILTS), ("pivot", self.pivot, _PIVOTS)):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < count:
                raise ValueError(f"Orientation.{field} : entier de 0 à {count - 1} attendu")

    def turned(self, turn: Turn) -> Orientation:
        """Orientation après un appui sur le bouton ``turn``."""
        if turn is Turn.PIVOT:
            return Orientation(self.tilt, (self.pivot + 1) % _PIVOTS)
        return Orientation((self.tilt + 1) % _TILTS, self.pivot)

    def rotation(self) -> Matrix3:
        """Rotation repère local de la pièce → repère d'appui (matrice de permutation signée)."""
        matrix = IDENTITY
        for _ in range(self.tilt):
            matrix = product(AXIS_CYCLE, matrix)
        for _ in range(self.pivot):
            matrix = product(QUARTER_TURN_Z, matrix)
        return matrix


class SnapNoticeKind(Enum):
    """Cause d'un élément ignoré ou d'une règle appliquée."""

    THICKNESS_GAP = "ThicknessGap"
    GAP_OUT_OF_RANGE = "GapOutOfRange"
    NOT_SQUARE = "NotSquare"
    TOO_MANY = "TooMany"
    CONFLICT = "Conflict"


_TEMPLATES: Final[Mapping[SnapNoticeKind, str]] = MappingProxyType(
    {
        SnapNoticeKind.THICKNESS_GAP: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "L'épaisseur de la pièce n'est jamais modifiée : « {target} » est ignoré.",
        ),
        SnapNoticeKind.GAP_OUT_OF_RANGE: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "L'écart avec « {target} » doit être compris entre {min} et {max} mm : élément ignoré.",
        ),
        SnapNoticeKind.NOT_SQUARE: QT_TRANSLATE_NOOP(
            "Menuiserie",
            "« {target} » n'est ni parallèle ni perpendiculaire à la pièce : élément ignoré.",
        ),
        SnapNoticeKind.TOO_MANY: QT_TRANSLATE_NOOP(
            "Menuiserie", "Trois éléments au plus sont pris en compte : « {target} » est ignoré."
        ),
        SnapNoticeKind.CONFLICT: QT_TRANSLATE_NOOP(
            "Menuiserie", "« {target} » remplace un autre élément posé du même côté."
        ),
    }
)


@dataclass(frozen=True)
class SnapNotice:
    """Avis non bloquant : ``template`` est le gabarit traduisible, ``message`` le texte rempli."""

    kind: SnapNoticeKind
    target: str

    @property
    def template(self) -> str:
        """Gabarit français (``QT_TRANSLATE_NOOP``) ; paramètres : :attr:`params`."""
        return _TEMPLATES[self.kind]

    @property
    def params(self) -> Mapping[str, str]:
        """Paramètres du gabarit."""
        return MappingProxyType(
            {"target": self.target, "min": f"{MIN_DIMENSION_MM:g}", "max": f"{MAX_DIMENSION_MM:g}"}
        )

    @property
    def message(self) -> str:
        """Texte français rempli (non traduit)."""
        return self.template.format_map(self.params)


@dataclass(frozen=True)
class SnapResult:
    """Placement global de la pièce, cotes (une cote étirée au plus), cibles retenues, avis."""

    placement: RigidTransform
    dimensions: Dimensions
    used: tuple[str, ...]
    notices: tuple[SnapNotice, ...]


FreeTest = Callable[[RigidTransform, Dimensions], bool]
