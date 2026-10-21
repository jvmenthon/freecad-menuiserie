# SPDX-License-Identifier: LGPL-2.1-or-later
"""Géométrie pure des assemblages : repères, boîtes, cylindres, prismes et position relative
(J3a, J4f).

Toutes les longueurs sont en mm. Le repère local d'une pièce est celui de ``part_model`` :
X = longueur, Y = largeur, Z = épaisseur. Les calculs se font dans le repère local de l'hôte,
après y avoir exprimé l'invitée : seule la rotation **relative** doit être d'équerre. La
position relative de deux pièces (contact, chevauchement) est dans :mod:`.contact`.
``features/`` convertit ``Placement`` en :class:`RigidTransform` par ``Placement.toMatrix()``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from freecad.menuiserie.core._polygon import check_prism
from freecad.menuiserie.core.i18n import QT_TRANSLATE_NOOP, TemplatedError
from freecad.menuiserie.core.part_model import Dimensions

__all__ = [
    "ANGLE_TOLERANCE",
    "CONTACT_TOLERANCE_MM",
    "CUT_OVERRUN_MM",
    "NOT_SQUARE",
    "Axis",
    "Box",
    "Cylinder",
    "JointError",
    "PlacedBlock",
    "Prism",
    "RigidTransform",
    "Solid",
    "Vec3",
    "moved",
    "moved_axis",
    "moved_box",
    "relative_axes",
    "relative_transform",
]

CONTACT_TOLERANCE_MM: Final = 0.01
ANGLE_TOLERANCE: Final = 1e-6  # écart toléré des coefficients de la matrice à {-1, 0, 1}
# Prolongement hors de la matière d'un enlèvement en prisme qui débouche (le volume enlevé dans
# la pièce ne change pas ; les booléennes d'OCC évitent les faces confondues).
CUT_OVERRUN_MM: Final = 0.1

NOT_SQUARE: Final = QT_TRANSLATE_NOOP(
    "Menuiserie", "Les deux pièces doivent être d'équerre (angles multiples de 90°)."
)

Row = tuple[float, float, float]
Matrix3 = tuple[Row, Row, Row]


class JointError(TemplatedError):
    """Assemblage impossible ; message = gabarit français (``QT_TRANSLATE_NOOP``) rempli."""


@dataclass(frozen=True)
class Vec3:
    """Point ou vecteur en mm."""

    x: float
    y: float
    z: float

    def component(self, index: int) -> float:
        """Coordonnée d'indice 0 (X), 1 (Y) ou 2 (Z)."""
        return (self.x, self.y, self.z)[index]

    @classmethod
    def of(cls, values: Sequence[float]) -> Vec3:
        """Vecteur construit depuis trois coordonnées."""
        return cls(float(values[0]), float(values[1]), float(values[2]))

    def with_component(self, index: int, value: float) -> Vec3:
        """Même vecteur, coordonnée d'indice ``index`` remplacée par ``value``."""
        values = [self.x, self.y, self.z]
        values[index] = value
        return Vec3.of(values)


class Axis(Enum):
    """Face ou direction signée dans un repère local."""

    X_POS = "+X"
    X_NEG = "-X"
    Y_POS = "+Y"
    Y_NEG = "-Y"
    Z_POS = "+Z"
    Z_NEG = "-Z"

    @property
    def index(self) -> int:
        """Indice de l'axe : 0 (X), 1 (Y) ou 2 (Z)."""
        return "XYZ".index(self.value[1])

    @property
    def sign(self) -> int:
        """+1 ou -1."""
        return 1 if self.value[0] == "+" else -1

    @classmethod
    def of(cls, index: int, sign: float) -> Axis:
        """Axe d'indice ``index`` orienté selon le signe de ``sign``."""
        return cls(("+" if sign > 0 else "-") + "XYZ"[index])

    def opposite(self) -> Axis:
        """Direction opposée."""
        return Axis.of(self.index, -self.sign)

    def unit(self) -> Vec3:
        """Vecteur unitaire de la direction."""
        values = [0.0, 0.0, 0.0]
        values[self.index] = float(self.sign)
        return Vec3.of(values)


def _require_finite(*values: float) -> None:
    if not all(math.isfinite(value) for value in values):
        raise ValueError("coordonnées non finies")


@dataclass(frozen=True)
class Box:
    """Boîte alignée sur les axes d'un repère ; ``min <= max`` sur chaque axe (aplatie permise)."""

    min: Vec3
    max: Vec3

    def __post_init__(self) -> None:
        _require_finite(self.min.x, self.min.y, self.min.z, self.max.x, self.max.y, self.max.z)
        if any(self.lo(i) > self.hi(i) for i in range(3)):
            raise ValueError("boîte inversée : min > max")

    @classmethod
    def from_ranges(cls, ranges: Sequence[tuple[float, float]]) -> Box:
        """Boîte définie par ses intervalles (min, max) sur X, Y et Z."""
        return cls(Vec3.of([r[0] for r in ranges]), Vec3.of([r[1] for r in ranges]))

    def lo(self, index: int) -> float:
        """Borne inférieure sur l'axe ``index``."""
        return self.min.component(index)

    def hi(self, index: int) -> float:
        """Borne supérieure sur l'axe ``index``."""
        return self.max.component(index)

    def size(self, index: int) -> float:
        """Étendue sur l'axe ``index``."""
        return self.hi(index) - self.lo(index)

    def center(self, index: int) -> float:
        """Milieu sur l'axe ``index``."""
        return (self.lo(index) + self.hi(index)) / 2

    def ranges(self) -> list[tuple[float, float]]:
        """Intervalles (min, max) sur X, Y et Z."""
        return [(self.lo(i), self.hi(i)) for i in range(3)]

    def with_range(self, index: int, low: float, high: float) -> Box:
        """Même boîte, intervalle de l'axe ``index`` remplacé."""
        ranges = self.ranges()
        ranges[index] = (low, high)
        return Box.from_ranges(ranges)


@dataclass(frozen=True)
class Cylinder:
    """Cylindre : base au centre d'une face, axe signé, rayon et hauteur > 0."""

    base: Vec3
    axis: Axis
    radius: float
    height: float

    def __post_init__(self) -> None:
        _require_finite(self.base.x, self.base.y, self.base.z, self.radius, self.height)
        if self.radius <= 0 or self.height <= 0:
            raise ValueError("rayon et hauteur du cylindre doivent être > 0")


@dataclass(frozen=True)
class Prism:
    """Polygone plan extrudé : sommets dans un plan, vecteur d'extrusion hors de ce plan.

    Au moins 3 sommets distincts, non tous alignés, coplanaires, formant un polygone simple
    (sans auto-intersection) ; extrusion finie, non nulle et non parallèle au plan.
    ``ValueError`` sinon (:func:`._polygon.check_prism`).
    """

    points: tuple[Vec3, ...]
    extrusion: Vec3

    def __post_init__(self) -> None:
        coordinates = [c for p in (*self.points, self.extrusion) for c in (p.x, p.y, p.z)]
        _require_finite(*coordinates)
        vector = self.extrusion
        check_prism([(p.x, p.y, p.z) for p in self.points], (vector.x, vector.y, vector.z))


Solid = Box | Cylinder | Prism


def _row(values: Sequence[float]) -> Row:
    return (float(values[0]), float(values[1]), float(values[2]))


def _matrix3(values: Sequence[Sequence[float]]) -> Matrix3:
    return (_row(values[0]), _row(values[1]), _row(values[2]))


def _transposed(rows: Matrix3) -> Matrix3:
    return _matrix3([[rows[j][i] for j in range(3)] for i in range(3)])


def _product(left: Matrix3, right: Matrix3) -> Matrix3:
    return _matrix3(
        [[sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    )


@dataclass(frozen=True)
class RigidTransform:
    """Déplacement rigide : ``point ↦ rotation · point + translation``."""

    rotation: Matrix3
    translation: Vec3

    @classmethod
    def identity(cls) -> RigidTransform:
        """Transformation neutre."""
        return cls(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), Vec3(0.0, 0.0, 0.0))

    @classmethod
    def from_matrix(cls, rows: Sequence[Sequence[float]]) -> RigidTransform:
        """Transformation lue sur une matrice 4 x 4 donnée par lignes (``Placement.toMatrix()``)."""
        if len(rows) != 4 or any(len(row) != 4 for row in rows):
            raise ValueError("matrice 4 x 4 attendue")
        values = [float(value) for row in rows for value in row]
        _require_finite(*values)
        return cls(_matrix3(rows), Vec3(values[3], values[7], values[11]))

    def rotate(self, vector: Vec3) -> Vec3:
        """Vecteur tourné, sans translation."""
        return Vec3.of(
            [sum(r * vector.component(j) for j, r in enumerate(row)) for row in self.rotation]
        )

    def apply(self, point: Vec3) -> Vec3:
        """Point transformé."""
        turned = self.rotate(point)
        return Vec3.of([turned.component(i) + self.translation.component(i) for i in range(3)])

    def inverse(self) -> RigidTransform:
        """Transformation réciproque (la rotation est supposée orthonormée)."""
        rotation = _transposed(self.rotation)
        back = RigidTransform(rotation, Vec3(0.0, 0.0, 0.0)).rotate(self.translation)
        return RigidTransform(rotation, Vec3(-back.x, -back.y, -back.z))

    def compose(self, other: RigidTransform) -> RigidTransform:
        """``self ∘ other`` : applique ``other`` puis ``self``."""
        return RigidTransform(
            _product(self.rotation, other.rotation), self.apply(other.translation)
        )


@dataclass(frozen=True)
class PlacedBlock:
    """Pièce brute vue par ``core`` : cotes finies et placement dans le document."""

    dimensions: Dimensions
    placement: RigidTransform

    def local_box(self) -> Box:
        """Boîte [0, L] x [0, l] x [0, e] dans le repère local."""
        size = self.dimensions
        return Box(Vec3(0.0, 0.0, 0.0), Vec3(size.length, size.width, size.thickness))


def _axis_of_column(rotation: Matrix3, column: int) -> Axis:
    values = [rotation[row][column] for row in range(3)]
    major = max(range(3), key=lambda i: abs(values[i]))
    exact = all(
        abs(abs(value) - (1.0 if i == major else 0.0)) <= ANGLE_TOLERANCE
        for i, value in enumerate(values)
    )
    if not exact:
        raise JointError(NOT_SQUARE, {})
    return Axis.of(major, values[major])


def relative_axes(host: PlacedBlock, guest: PlacedBlock) -> tuple[Axis, Axis, Axis]:
    """Directions, dans le repère de l'hôte, des axes +X, +Y et +Z de l'invitée.

    Lève :class:`JointError` si la rotation relative n'est pas un multiple de 90° par axe.
    """
    return _square_axes(host.placement.inverse().compose(guest.placement).rotation)


def _square_axes(rotation: Matrix3) -> tuple[Axis, Axis, Axis]:
    """Images des axes +X, +Y et +Z par ``rotation`` ; :class:`JointError` si elle n'est pas
    d'équerre."""
    axes = (
        _axis_of_column(rotation, 0),
        _axis_of_column(rotation, 1),
        _axis_of_column(rotation, 2),
    )
    if len({axis.index for axis in axes}) != 3:
        raise JointError(NOT_SQUARE, {})
    return axes


def relative_transform(host: PlacedBlock, guest: PlacedBlock) -> RigidTransform:
    """Repère de l'invitée → repère de l'hôte, rotation arrondie à la permutation exacte."""
    relative = host.placement.inverse().compose(guest.placement)
    rows = [[0.0, 0.0, 0.0] for _ in range(3)]
    for column, axis in enumerate(_square_axes(relative.rotation)):
        rows[axis.index][column] = float(axis.sign)
    return RigidTransform(_matrix3(rows), relative.translation)


def moved_axis(transform: RigidTransform, axis: Axis) -> Axis:
    """Direction ``axis`` exprimée dans un autre repère (rotation d'équerre)."""
    turned = transform.rotate(axis.unit())
    major = max(range(3), key=lambda i: abs(turned.component(i)))
    return Axis.of(major, turned.component(major))


def moved_box(box: Box, transform: RigidTransform) -> Box:
    """Boîte exprimée dans un autre repère (rotation d'équerre)."""
    first, second = transform.apply(box.min), transform.apply(box.max)
    pairs = [sorted((first.component(i), second.component(i))) for i in range(3)]
    return Box.from_ranges([(pair[0], pair[1]) for pair in pairs])


def moved(solid: Solid, transform: RigidTransform) -> Solid:
    """Solide exprimé dans un autre repère (rotation d'équerre pour une boîte ou un cylindre,
    quelconque pour un prisme : sommets et vecteur d'extrusion transformés)."""
    if isinstance(solid, Cylinder):
        base = transform.apply(solid.base)
        return Cylinder(base, moved_axis(transform, solid.axis), solid.radius, solid.height)
    if isinstance(solid, Prism):
        points = tuple(transform.apply(point) for point in solid.points)
        return Prism(points, transform.rotate(solid.extrusion))
    return moved_box(solid, transform)
